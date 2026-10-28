"""Núcleo de dominio TechStore (Unidad 4).

No depende de FastAPI, CSV ni base de datos: se puede ejecutar en memoria.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

MAX_UNITS = 20


# ---------------------------------------------------------------- Excepciones
class DomainException(Exception):
    """Violación de una regla de negocio (no es un error técnico)."""


class InvalidOrderData(DomainException):
    """Datos que no cumplen una invariante (monto, cantidad, cliente, guía...)."""


class InvalidOrderTransition(DomainException):
    """Operación no permitida desde el estado actual del pedido."""


class OrderItemLimitExceeded(DomainException):
    """El pedido superaría el máximo de 20 unidades."""


# --------------------------------------------------------------- Value Objects
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "MXN"

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            raise InvalidOrderData("El monto debe ser Decimal, no float/int")
        if not self.amount.is_finite() or self.amount < 0:
            raise InvalidOrderData("Monto inválido")

    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise InvalidOrderData("Monedas distintas")
        return Money(self.amount + other.amount, self.currency)


@dataclass(frozen=True)
class Customer:
    id: str
    is_vip: bool = False
    active: bool = True


@dataclass(frozen=True)
class OrderItem:
    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self):
        if not self.sku.strip() or self.quantity <= 0:
            raise InvalidOrderData("Artículo inválido")

    @property
    def subtotal(self) -> Money:
        return Money(self.unit_price.amount * self.quantity, self.unit_price.currency)


# ------------------------------------------------------------- Domain Events
@dataclass(frozen=True)
class DomainEvent:
    name: str
    order_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ------------------------------------------------------------------- Entidad
class OrderStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


@dataclass
class Order:
    """Aggregate Root. Todas las transiciones validan primero, cambian el
    estado después y registran el evento al final."""
    customer: Customer
    id: str
    has_promotion: bool = False
    status: OrderStatus = OrderStatus.DRAFT
    items: list[OrderItem] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)
    tracking_number: Optional[str] = None
    cancel_reason: Optional[str] = None

    # -- consultas
    @property
    def units(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def total(self) -> Money:
        amount = sum((x.subtotal.amount for x in self.items), Decimal("0"))
        return Money(amount)

    # -- comandos
    def add_item(self, item: OrderItem) -> None:
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition("Solo DRAFT admite artículos")
        if item.unit_price.currency != "MXN":
            raise InvalidOrderData("Solo MXN")
        if self.units + item.quantity > MAX_UNITS:
            raise OrderItemLimitExceeded(f"Máximo {MAX_UNITS} unidades")
        self.items.append(item)

    def _record(self, name: str) -> None:
        self.events.append(DomainEvent(name, self.id))

    def confirm(self) -> None:
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition("Solo se puede confirmar desde DRAFT")
        if not self.items or not self.customer.active:
            raise InvalidOrderData("Requiere artículos y cliente activo")
        self.status = OrderStatus.CONFIRMED
        self._record("OrderConfirmed")

    def ship(self, tracking_number: str) -> None:
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderTransition("Solo se puede enviar desde CONFIRMED")
        if not tracking_number or not tracking_number.strip():
            raise InvalidOrderData("El envío requiere número de guía")
        self.tracking_number = tracking_number.strip()
        self.status = OrderStatus.SHIPPED
        self._record("OrderShipped")

    def cancel(self, reason: str) -> None:
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderTransition("Solo se puede cancelar desde CONFIRMED")
        if not reason or not reason.strip():
            raise InvalidOrderData("La cancelación requiere motivo")
        self.cancel_reason = reason.strip()
        self.status = OrderStatus.CANCELLED
        self._record("OrderCancelled")

    def deliver(self) -> None:
        if self.status != OrderStatus.SHIPPED:
            raise InvalidOrderTransition("Solo se puede entregar desde SHIPPED")
        self.status = OrderStatus.DELIVERED
        self._record("OrderDelivered")

    def return_order(self) -> None:
        if self.status != OrderStatus.SHIPPED:
            raise InvalidOrderTransition("Solo se puede devolver desde SHIPPED")
        self.status = OrderStatus.RETURNED
        self._record("OrderReturned")
