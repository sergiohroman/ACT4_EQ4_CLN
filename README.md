# TechStore U4 · Núcleo de negocio

Actividad 4 · Componentes de Lógica de Negocio · FIME-UANL.
Pedidos con Value Objects, Specifications, máquina de estados, Domain Events y API REST (FastAPI). Todo en memoria: al cerrar el programa se pierden los cambios.

## Instalación y ejecución
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python cargar_csv.py               # debe listar 16 pedidos en DRAFT
python ejecutar_escenarios.py      # corre E01-E15 y regenera docs/BITACORA.md
python -m pytest -q                # pruebas de dominio y de API
uvicorn app.api:app --reload       # Swagger: http://127.0.0.1:8000/docs
```

## Estructura
```
app/domain.py          Money, Customer, OrderItem, Order, estados, eventos, excepciones
app/specifications.py  Specification (& | ~), 5 reglas atómicas y reglas de descuento
app/api.py             Controladores delgados FastAPI
tests/                 test_domain.py, test_api.py
datos/                 CSV del paquete
docs/                  BITACORA.md, REPORTE.md, evidencias/
```

## Reglas
- Money: `Decimal`, sin negativos, sin monedas mezcladas; inmutable.
- Máximo 20 **unidades** por pedido (no renglones); solo se agregan artículos en DRAFT.
- Descuento 10 %: VIP, total **> 500**, **>= 4** unidades, sin promoción.
- Descuento 5 %: total **> 5000** y sin promoción. Si ambas se cumplen, aplica 10 %.
- Estados: DRAFT → CONFIRMED → SHIPPED → DELIVERED; CONFIRMED → CANCELLED (con motivo); SHIPPED → RETURNED.
- Confirmar requiere artículos y cliente activo; enviar requiere guía.
- El evento se registra solo después de una transición válida.

## Endpoints
| Método | Ruta | Éxito | Rechazos |
|---|---|---|---|
| GET | /orders, /orders/{id} | 200 | 404 |
| GET | /orders/{id}/discount | 200 | 404 |
| POST | /orders | 201 | 404 cliente, 409 duplicado |
| POST | /orders/{id}/items | 200 | 404, 422 límite/dato inválido, 409 no DRAFT |
| POST | /orders/{id}/confirm | 200 | 404, 409 transición, 422 vacío/inactivo |
| POST | /orders/{id}/ship `{tracking_number}` | 200 | 404, 409, 422 sin guía |
| POST | /orders/{id}/cancel `{reason}` | 200 | 404, 409, 422 sin motivo |
| POST | /orders/{id}/deliver, /return | 200 | 404, 409 |
