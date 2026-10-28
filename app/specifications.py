"""Specification Pattern: reglas de elegibilidad combinables (& | ~).

Una Specification solo EVALÚA; nunca modifica el pedido.
"""
from decimal import Decimal


class Specification:
    def is_satisfied_by(self, order) -> bool:
        raise NotImplementedError

    def __and__(self, other):
        return AndSpec(self, other)

    def __or__(self, other):
        return OrSpec(self, other)

    def __invert__(self):
        return NotSpec(self)


class AndSpec(Specification):
    def __init__(self, left, right):
        self.left, self.right = left, right

    def is_satisfied_by(self, order):
        return self.left.is_satisfied_by(order) and self.right.is_satisfied_by(order)


class OrSpec(Specification):
    def __init__(self, left, right):
        self.left, self.right = left, right

    def is_satisfied_by(self, order):
        return self.left.is_satisfied_by(order) or self.right.is_satisfied_by(order)


class NotSpec(Specification):
    def __init__(self, inner):
        self.inner = inner

    def is_satisfied_by(self, order):
        return not self.inner.is_satisfied_by(order)


# ---- Reglas atómicas -------------------------------------------------------
class MinimumAmountSpec(Specification):
    """Total ESTRICTAMENTE mayor al umbral (>, no >=)."""
    def __init__(self, threshold: Decimal):
        self.threshold = Decimal(threshold)

    def is_satisfied_by(self, order):
        return order.total.amount > self.threshold


class VIPCustomerSpec(Specification):
    def is_satisfied_by(self, order):
        return order.customer.is_vip


class MinimumUnitsSpec(Specification):
    """Al menos N unidades (>=). Cuenta unidades, no renglones."""
    def __init__(self, minimum: int):
        self.minimum = minimum

    def is_satisfied_by(self, order):
        return order.units >= self.minimum


class ActivePromotionSpec(Specification):
    def is_satisfied_by(self, order):
        return order.has_promotion


class ActiveCustomerSpec(Specification):
    """Quinta Specification: el cliente puede confirmar pedidos."""
    def is_satisfied_by(self, order):
        return order.customer.active


# ---- Reglas de descuento compuestas ----------------------------------------
ten_percent = (
    MinimumAmountSpec(Decimal("500"))
    & VIPCustomerSpec()
    & MinimumUnitsSpec(4)
    & ~ActivePromotionSpec()
)
five_percent = MinimumAmountSpec(Decimal("5000")) & ~ActivePromotionSpec()
any_discount = ten_percent | five_percent


def discount_rate(order) -> Decimal:
    """Si ambas reglas se cumplen, aplica primero el 10 %."""
    if ten_percent.is_satisfied_by(order):
        return Decimal("0.10")
    if five_percent.is_satisfied_by(order):
        return Decimal("0.05")
    return Decimal("0")


def discount_amount(order) -> Decimal:
    return (order.total.amount * discount_rate(order)).quantize(Decimal("0.01"))
