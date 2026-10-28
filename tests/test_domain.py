from decimal import Decimal

import pytest

from app.domain import (
    Customer, InvalidOrderData, InvalidOrderTransition, Money, Order,
    OrderItem, OrderItemLimitExceeded, OrderStatus,
)
from app.specifications import (
    ActivePromotionSpec, MinimumAmountSpec, MinimumUnitsSpec, VIPCustomerSpec,
    discount_amount, discount_rate, ten_percent, five_percent,
)
from cargar_csv import load_fixture


def item(sku="SKU001", qty=1, price="100.00"):
    return OrderItem(sku, qty, Money(Decimal(price)))


def make_order(vip=False, active=True, promo=False):
    return Order(customer=Customer("C", vip, active), id="T1", has_promotion=promo)


def shipped_order():
    o = make_order()
    o.add_item(item())
    o.confirm()
    o.ship("GUIA1")
    return o


# ------------------------------------------------------- Value Objects
def test_money_negativo():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("-1"))


def test_money_rechaza_float():
    with pytest.raises(InvalidOrderData):
        Money(10.5)


def test_money_add_devuelve_nuevo_objeto():
    a, b = Money(Decimal("100")), Money(Decimal("50"))
    c = a.add(b)
    assert c.amount == Decimal("150") and a.amount == Decimal("100")


def test_money_monedas_distintas():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("1"), "MXN").add(Money(Decimal("1"), "USD"))


def test_money_es_inmutable():
    m = Money(Decimal("1"))
    with pytest.raises(Exception):
        m.amount = Decimal("2")


def test_money_igualdad_por_valor():
    assert Money(Decimal("100")) == Money(Decimal("100"))


@pytest.mark.parametrize("qty", [0, -1])
def test_item_cantidad_invalida(qty):
    with pytest.raises(InvalidOrderData):
        item(qty=qty)


def test_item_sku_vacio():
    with pytest.raises(InvalidOrderData):
        item(sku="  ")


def test_subtotal_se_calcula():
    assert item(qty=2, price="600.00").subtotal.amount == Decimal("1200.00")


# --------------------------------------------------------------- Fixtures
def test_pedido_o001_inicia_draft():
    orders = load_fixture()
    assert orders["O001"].status.value == "DRAFT"
    assert orders["O001"].units == 4
    assert orders["O001"].total.amount == Decimal("2100.00")


def test_carga_16_pedidos_en_draft():
    orders = load_fixture()
    assert len(orders) == 16
    assert all(o.status == OrderStatus.DRAFT for o in orders.values())


def test_o006_y_o010_manuales():
    orders = load_fixture()
    assert (orders["O006"].units, orders["O006"].total.amount) == (1, Decimal("18000.00"))
    assert (orders["O010"].units, orders["O010"].total.amount) == (2, Decimal("500.00"))


# ------------------------------------------------------------ Límite 20
def test_20_unidades_permitidas():
    o = make_order()
    o.add_item(item(qty=20))
    assert o.units == 20


def test_21_unidades_rechazadas_sin_modificar():
    o = load_fixture()["O009"]            # 19 unidades
    with pytest.raises(OrderItemLimitExceeded):
        o.add_item(item("SKU003", 2, "120.00"))
    assert o.units == 19 and len(o.items) == 1


def test_limite_cuenta_unidades_no_renglones():
    o = make_order()
    for _ in range(5):
        o.add_item(item(qty=4))           # 5 renglones, 20 unidades
    with pytest.raises(OrderItemLimitExceeded):
        o.add_item(item(qty=1))


def test_no_agrega_articulos_si_no_es_draft():
    o = make_order()
    o.add_item(item())
    o.confirm()
    with pytest.raises(InvalidOrderTransition):
        o.add_item(item())


# ------------------------------------------------------- Confirmación
def test_confirmar_pedido_vacio():
    o = load_fixture()["O007"]
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert o.status == OrderStatus.DRAFT and o.events == []


def test_confirmar_cliente_inactivo():
    o = load_fixture()["O003"]
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert o.status == OrderStatus.DRAFT and o.events == []


def test_confirmar_20_unidades_exito():
    o = load_fixture()["O008"]
    o.confirm()
    assert o.status == OrderStatus.CONFIRMED
    assert [e.name for e in o.events] == ["OrderConfirmed"]


def test_confirmacion_doble_no_agrega_evento():
    o = load_fixture()["O013"]
    o.confirm()
    with pytest.raises(InvalidOrderTransition):
        o.confirm()
    assert o.status == OrderStatus.CONFIRMED
    assert len(o.events) == 1


# ------------------------------------------------------------- Envío
def test_enviar_sin_guia():
    o = load_fixture()["O012"]
    o.confirm()
    with pytest.raises(InvalidOrderData):
        o.ship("")
    with pytest.raises(InvalidOrderData):
        o.ship("   ")
    assert o.status == OrderStatus.CONFIRMED
    assert [e.name for e in o.events] == ["OrderConfirmed"]


def test_enviar_desde_draft():
    o = make_order()
    o.add_item(item())
    with pytest.raises(InvalidOrderTransition):
        o.ship("G1")


def test_enviar_con_guia():
    o = load_fixture()["O012"]
    o.confirm()
    o.ship("MX123")
    assert o.status == OrderStatus.SHIPPED and o.tracking_number == "MX123"
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderShipped"]


# ---------------------------------------------------------- Cancelación
def test_cancelar_desde_shipped():
    o = load_fixture()["O014"]
    o.confirm()
    o.ship("G1")
    with pytest.raises(InvalidOrderTransition):
        o.cancel("Cambio de opinión")
    assert o.status == OrderStatus.SHIPPED
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderShipped"]


def test_cancelar_desde_confirmed_con_motivo():
    o = load_fixture()["O014"]
    o.confirm()
    o.cancel("Cliente lo solicitó")
    assert o.status == OrderStatus.CANCELLED
    assert o.events[-1].name == "OrderCancelled"


def test_cancelar_sin_motivo():
    o = load_fixture()["O014"]
    o.confirm()
    with pytest.raises(InvalidOrderData):
        o.cancel(" ")
    assert o.status == OrderStatus.CONFIRMED


def test_cancelar_desde_draft():
    with pytest.raises(InvalidOrderTransition):
        load_fixture()["O014"].cancel("x")


# ------------------------------------------------ Entrega y devolución
def test_entregar_desde_shipped():
    o = load_fixture()["O016"]
    o.confirm(); o.ship("G"); o.deliver()
    assert o.status == OrderStatus.DELIVERED
    assert [e.name for e in o.events][-1] == "OrderDelivered"


def test_devolver_desde_shipped():
    o = load_fixture()["O015"]
    o.confirm(); o.ship("G"); o.return_order()
    assert o.status == OrderStatus.RETURNED
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderShipped", "OrderReturned"]


def test_no_entregar_ni_devolver_desde_confirmed():
    o = make_order(); o.add_item(item()); o.confirm()
    with pytest.raises(InvalidOrderTransition):
        o.deliver()
    with pytest.raises(InvalidOrderTransition):
        o.return_order()


def test_estados_finales_no_aceptan_transiciones():
    o = shipped_order(); o.deliver()
    for op in (o.confirm, o.deliver, o.return_order, lambda: o.ship("G"), lambda: o.cancel("x")):
        with pytest.raises(InvalidOrderTransition):
            op()
    assert len(o.events) == 3


# ------------------------------------------------------ Specifications
def test_umbral_estricto_500():
    o = load_fixture()["O010"]            # total exactamente 500
    assert not MinimumAmountSpec(Decimal("500")).is_satisfied_by(o)
    assert MinimumAmountSpec(Decimal("499.99")).is_satisfied_by(o)


def test_minimo_unidades_es_mayor_o_igual():
    orders = load_fixture()
    assert MinimumUnitsSpec(4).is_satisfied_by(orders["O001"])      # 4
    assert not MinimumUnitsSpec(4).is_satisfied_by(orders["O011"])  # 3


def test_specs_atomicas():
    orders = load_fixture()
    assert VIPCustomerSpec().is_satisfied_by(orders["O001"])
    assert not VIPCustomerSpec().is_satisfied_by(orders["O002"])
    assert ActivePromotionSpec().is_satisfied_by(orders["O005"])


def test_composicion_or_y_not():
    o = load_fixture()["O006"]
    assert (VIPCustomerSpec() | MinimumAmountSpec(Decimal("5000"))).is_satisfied_by(o)
    assert (~VIPCustomerSpec()).is_satisfied_by(o)
    assert not (VIPCustomerSpec() & MinimumAmountSpec(Decimal("5000"))).is_satisfied_by(o)


def test_specification_no_modifica_pedido():
    o = load_fixture()["O001"]
    antes = (o.status, o.units, o.total, list(o.events))
    discount_rate(o); ten_percent.is_satisfied_by(o)
    assert antes == (o.status, o.units, o.total, list(o.events))


@pytest.mark.parametrize("oid,rate", [
    ("O001", "0.10"),   # E01 VIP, 2100, 4 u, sin promo
    ("O002", "0"),      # E02 no VIP
    ("O005", "0"),      # E04 promoción activa
    ("O006", "0.05"),   # E05 total > 5000
    ("O010", "0"),      # E09 total = 500
    ("O011", "0"),      # E10 solo 3 unidades
])
def test_descuentos_escenarios(oid, rate):
    assert discount_rate(load_fixture()[oid]) == Decimal(rate)


def test_importes_de_descuento():
    orders = load_fixture()
    assert discount_amount(orders["O001"]) == Decimal("210.00")
    assert discount_amount(orders["O006"]) == Decimal("900.00")


def test_prioridad_10_sobre_5():
    o = make_order(vip=True)
    o.add_item(item(qty=10, price="600.00"))   # 6000, VIP, 10 unidades
    assert ten_percent.is_satisfied_by(o) and five_percent.is_satisfied_by(o)
    assert discount_rate(o) == Decimal("0.10")


def test_promocion_bloquea_5_por_ciento():
    o = make_order(promo=True)
    o.add_item(item(qty=1, price="6000.00"))
    assert discount_rate(o) == Decimal("0")
