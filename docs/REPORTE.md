# Reporte · Actividad 4 · TechStore

## Diagrama de estados
```
DRAFT --confirm--> CONFIRMED --ship(guía)--> SHIPPED --deliver--> DELIVERED
                       |                        |
                  cancel(motivo)             return
                       |                        |
                   CANCELLED                RETURNED
```
Cualquier otra transición lanza `InvalidOrderTransition` (HTTP 409).

## Domain Events
| Evento | Transición | Se registra cuando |
|---|---|---|
| OrderConfirmed | DRAFT → CONFIRMED | hay artículos y el cliente está activo |
| OrderShipped | CONFIRMED → SHIPPED | hay guía no vacía |
| OrderCancelled | CONFIRMED → CANCELLED | hay motivo no vacío |
| OrderDelivered | SHIPPED → DELIVERED | siempre tras validar el estado |
| OrderReturned | SHIPPED → RETURNED | siempre tras validar el estado |

Cada método valida primero, cambia `status` después y agrega el evento al final; una operación fallida no cambia el estado ni emite evento (E03, E06, E11, E12, E13).

## Preguntas del reporte
1. **Decimal vs float:** float representa en binario y acumula errores (0.1+0.2 ≠ 0.3); en dinero eso rompe totales y umbrales como "> 500". Decimal es exacto en base 10.
2. **Renglones vs unidades:** el límite es de 20 unidades. Cinco renglones de 4 piezas son 5 renglones pero 20 unidades; un renglón de 21 piezas ya excede el límite.
3. **Ventaja de Specification:** cada condición tiene nombre, se prueba sola y se combina con &, | y ~ sin repetir `if` anidados; si cambia una política se edita una clase.
4. **Eventos solo tras transición válida:** un evento anuncia un hecho ocurrido; emitirlo antes de validar notificaría (correo, inventario) algo que nunca sucedió.
5. **Reutilización sin FastAPI:** todo `app/domain.py` y `app/specifications.py`, más las pruebas de dominio; solo `api.py` es específico de HTTP.

## Reflexión (borrador: ajústalo con tu experiencia)
- **Umbral estricto:** O010 suma exactamente 500; con `>=` se concedería un descuento indebido. Se usó `>` y hay prueba de frontera.
- **Unidades vs renglones:** contar `len(items)` permitiría pasar de 20 piezas; se corrigió sumando cantidades y validando antes de modificar `items`.
- **Validar antes de mutar:** si el evento o el cambio de estado ocurren antes de validar la guía, queda un pedido SHIPPED sin guía; se reordenó validar → cambiar → registrar evento.
- **Aprendizaje:** las reglas viven en el dominio; la API solo traduce excepciones a 404/409/422.
