"""API REST (FastAPI). El controlador es delgado: busca, delega en Order y traduce
excepciones de dominio a códigos HTTP. No contiene reglas de negocio."""
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cargar_csv import load_fixture, rows
from app.domain import (
    DomainException, InvalidOrderData, InvalidOrderTransition,
    Money, OrderItem, OrderItemLimitExceeded, Order,
)
from app.specifications import discount_amount, discount_rate

app = FastAPI(title="TechStore U4", version="1.0.0",
              description="Núcleo de negocio TechStore: pedidos, descuentos y estados.")

# Repositorio en memoria (se pierde al cerrar el programa).
orders: dict[str, Order] = load_fixture()
catalog: dict[str, Decimal] = {x["sku"]: Decimal(x["precio_mxn"]) for x in rows("productos.csv")}


def reset() -> None:
    """Recarga los fixtures (útil para pruebas y demostraciones)."""
    orders.clear()
    orders.update(load_fixture())


# ------------------------------------------------------------------ DTOs
class ShipRequest(BaseModel):
    tracking_number: str = ""


class CancelRequest(BaseModel):
    reason: str = ""


class ItemRequest(BaseModel):
    sku: str
    quantity: int


class CreateOrderRequest(BaseModel):
    id: str
    customer_id: str
    has_promotion: bool = False


def to_dto(order: Order) -> dict:
    return {
        "id": order.id,
        "customer_id": order.customer.id,
        "status": order.status.value,
        "units": order.units,
        "total": str(order.total.amount),
        "currency": order.total.currency,
        "has_promotion": order.has_promotion,
        "tracking_number": order.tracking_number,
        "cancel_reason": order.cancel_reason,
        "events": [e.name for e in order.events],
    }


def get_order(order_id: str) -> Order:
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"No existe el pedido {order_id}")
    return order


def run(action) -> None:
    """Traduce excepciones de dominio a HTTP semántico."""
    try:
        action()
    except InvalidOrderTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (InvalidOrderData, OrderItemLimitExceeded) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except DomainException as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ------------------------------------------------------------- Endpoints
@app.get("/orders")
def list_orders():
    return [to_dto(o) for o in orders.values()]


@app.get("/orders/{order_id}")
def read_order(order_id: str):
    return to_dto(get_order(order_id))


@app.get("/orders/{order_id}/discount")
def read_discount(order_id: str):
    order = get_order(order_id)
    return {"id": order.id, "rate": str(discount_rate(order)),
            "discount": str(discount_amount(order)), "total": str(order.total.amount)}


@app.post("/orders", status_code=201)
def create_order(body: CreateOrderRequest):
    if body.id in orders:
        raise HTTPException(status_code=409, detail="El pedido ya existe")
    customers = {o.customer.id: o.customer for o in orders.values()}
    customer = customers.get(body.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    order = Order(customer=customer, id=body.id, has_promotion=body.has_promotion)
    orders[order.id] = order
    return to_dto(order)


@app.post("/orders/{order_id}/items")
def add_item(order_id: str, body: ItemRequest):
    order = get_order(order_id)
    price = catalog.get(body.sku)
    if price is None:
        raise HTTPException(status_code=404, detail=f"No existe el SKU {body.sku}")
    run(lambda: order.add_item(OrderItem(body.sku, body.quantity, Money(price))))
    return to_dto(order)


@app.post("/orders/{order_id}/confirm")
def confirm_order(order_id: str):
    order = get_order(order_id)
    run(order.confirm)
    return to_dto(order)


@app.post("/orders/{order_id}/ship")
def ship_order(order_id: str, body: ShipRequest):
    order = get_order(order_id)
    run(lambda: order.ship(body.tracking_number))
    return to_dto(order)


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, body: CancelRequest):
    order = get_order(order_id)
    run(lambda: order.cancel(body.reason))
    return to_dto(order)


@app.post("/orders/{order_id}/deliver")
def deliver_order(order_id: str):
    order = get_order(order_id)
    run(order.deliver)
    return to_dto(order)


@app.post("/orders/{order_id}/return")
def return_order(order_id: str):
    order = get_order(order_id)
    run(order.return_order)
    return to_dto(order)
