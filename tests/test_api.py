import pytest
from fastapi.testclient import TestClient

from app import api


@pytest.fixture()
def client():
    api.reset()                           # estado limpio en cada prueba
    return TestClient(api.app)


def test_get_pedido(client):
    r = client.get("/orders/O001")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "DRAFT" and body["units"] == 4 and body["total"] == "2100.00"


def test_404_pedido_inexistente(client):
    assert client.get("/orders/NOPE").status_code == 404
    assert client.post("/orders/NOPE/confirm").status_code == 404


def test_confirmar_ok(client):
    r = client.post("/orders/O008/confirm")
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMED" and r.json()["events"] == ["OrderConfirmed"]


def test_409_confirmar_dos_veces(client):
    client.post("/orders/O013/confirm")
    r = client.post("/orders/O013/confirm")
    assert r.status_code == 409
    assert client.get("/orders/O013").json()["events"] == ["OrderConfirmed"]


def test_422_confirmar_pedido_vacio(client):
    assert client.post("/orders/O007/confirm").status_code == 422


def test_422_confirmar_cliente_inactivo(client):
    assert client.post("/orders/O003/confirm").status_code == 422


def test_422_enviar_sin_guia(client):
    client.post("/orders/O012/confirm")
    assert client.post("/orders/O012/ship", json={"tracking_number": ""}).status_code == 422
    assert client.post("/orders/O012/ship", json={}).status_code == 422


def test_flujo_completo_entrega(client):
    client.post("/orders/O016/confirm")
    assert client.post("/orders/O016/ship", json={"tracking_number": "G1"}).status_code == 200
    r = client.post("/orders/O016/deliver")
    assert r.status_code == 200 and r.json()["status"] == "DELIVERED"


def test_409_cancelar_desde_shipped(client):
    client.post("/orders/O014/confirm")
    client.post("/orders/O014/ship", json={"tracking_number": "G1"})
    r = client.post("/orders/O014/cancel", json={"reason": "tarde"})
    assert r.status_code == 409
    assert client.get("/orders/O014").json()["status"] == "SHIPPED"


def test_cancelar_confirmado(client):
    client.post("/orders/O014/confirm")
    r = client.post("/orders/O014/cancel", json={"reason": "Ya no lo quiere"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"


def test_devolver(client):
    client.post("/orders/O015/confirm")
    client.post("/orders/O015/ship", json={"tracking_number": "G2"})
    assert client.post("/orders/O015/return").json()["status"] == "RETURNED"


def test_422_limite_20_unidades(client):
    r = client.post("/orders/O009/items", json={"sku": "SKU003", "quantity": 2})
    assert r.status_code == 422
    assert client.get("/orders/O009").json()["units"] == 19


def test_agregar_item_y_sku_inexistente(client):
    assert client.post("/orders/O007/items", json={"sku": "SKU001", "quantity": 1}).status_code == 200
    assert client.post("/orders/O007/items", json={"sku": "XXX", "quantity": 1}).status_code == 404


def test_descuento_endpoint(client):
    assert client.get("/orders/O001/discount").json()["rate"] == "0.10"
    assert client.get("/orders/O006/discount").json()["rate"] == "0.05"
    assert client.get("/orders/O010/discount").json()["rate"] == "0"


def test_crear_pedido(client):
    r = client.post("/orders", json={"id": "O100", "customer_id": "C001"})
    assert r.status_code == 201 and r.json()["status"] == "DRAFT"
    assert client.post("/orders", json={"id": "O100", "customer_id": "C001"}).status_code == 409
    assert client.post("/orders", json={"id": "O101", "customer_id": "ZZ"}).status_code == 404


def test_openapi_documenta_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/orders/{order_id}/confirm" in paths
