"""Ejecuta los 15 escenarios E01-E15 y genera docs/BITACORA.md.
Cada escenario usa un pedido recién cargado (load_fixture)."""
from decimal import Decimal
from cargar_csv import load_fixture, rows
from app.domain import DomainException, Money, OrderItem
from app.specifications import discount_rate

PRUEBAS = {
    "E01": "test_descuentos_escenarios[O001-0.10]", "E02": "test_descuentos_escenarios[O002-0]",
    "E03": "test_confirmar_cliente_inactivo", "E04": "test_descuentos_escenarios[O005-0]",
    "E05": "test_descuentos_escenarios[O006-0.05]", "E06": "test_confirmar_pedido_vacio",
    "E07": "test_confirmar_20_unidades_exito", "E08": "test_21_unidades_rechazadas_sin_modificar",
    "E09": "test_umbral_estricto_500; test_descuentos_escenarios[O010-0]",
    "E10": "test_minimo_unidades_es_mayor_o_igual; test_descuentos_escenarios[O011-0]",
    "E11": "test_enviar_sin_guia", "E12": "test_confirmacion_doble_no_agrega_evento",
    "E13": "test_cancelar_desde_shipped", "E14": "test_devolver_desde_shipped",
    "E15": "test_entregar_desde_shipped",
}

def ev(o): return ", ".join(e.name for e in o.events) or "ninguno"

def run_case(c):
    o = load_fixture()[c["pedido_id"]]
    sn = lambda b: "sí" if b else "no"
    ini = (f"Estado {o.status.value}; cliente {o.customer.id} (VIP: {sn(o.customer.is_vip)}, "
           f"activo: {sn(o.customer.active)}); promoción: {sn(o.has_promotion)}; "
           f"{o.units} u; {o.total.amount} MXN")
    a, res, expl = c["accion"], "", ""
    def attempt(label, fn):
        try:
            fn(); return f"{label}: OK"
        except DomainException as e:
            return f"{label}: RECHAZADO {type(e).__name__} - {e}"
    if a == "evaluar_descuento":
        r = discount_rate(o)
        res = f"descuento {int(r*100)}% (= {(o.total.amount*r).quantize(Decimal('0.01'))} MXN)"
        expl = c["pista"]; evento = "no aplica (solo evaluación)"
    elif a == "confirmar":
        res = attempt("confirm()", o.confirm); expl = c["pista"]; evento = ev(o)
    elif a.startswith("agregar"):
        res = attempt("add_item(SKU003 x2)", lambda: o.add_item(OrderItem("SKU003", 2, Money(Decimal("120.00")))))
        expl = c["pista"] + f"; unidades finales: {o.units}"; evento = ev(o)
    elif a == "confirmar y enviar sin guia":
        o.confirm(); res = "confirm(): OK | " + attempt("ship('')", lambda: o.ship("")); expl = c["pista"]; evento = ev(o)
    elif a == "confirmar dos veces":
        o.confirm(); res = "confirm() #1: OK | " + attempt("confirm() #2", o.confirm); expl = c["pista"]; evento = ev(o)
    elif a == "confirmar, enviar y cancelar":
        o.confirm(); o.ship("MX-0001"); res = "confirm(), ship('MX-0001'): OK | " + attempt("cancel('tarde')", lambda: o.cancel("tarde")); expl = c["pista"]; evento = ev(o)
    elif a == "confirmar, enviar y devolver":
        o.confirm(); o.ship("MX-0002"); o.return_order(); res = "termina en " + o.status.value; expl = c["pista"]; evento = ev(o)
    elif a == "confirmar, enviar y entregar":
        o.confirm(); o.ship("MX-0003"); o.deliver(); res = "termina en " + o.status.value; expl = c["pista"]; evento = ev(o)
    fin = o.status.value
    return [c["caso_id"], c["pedido_id"], ini, a, res, fin, evento, expl, PRUEBAS[c["caso_id"]]]

if __name__ == "__main__":
    out = ["# Bitácora de los 15 escenarios (E01–E15)\n",
           "| Caso | Pedido | Precondiciones | Operación | Resultado real | Estado final | Eventos emitidos | Explicación | Prueba pytest |",
           "|---|---|---|---|---|---|---|---|---|"]
    for c in rows("escenarios.csv"):
        r = run_case(c); out.append("| " + " | ".join(x.replace("|", "/") for x in r) + " |"); print(r[0], "->", r[4], "|", r[5], "|", r[6])
    open("docs/BITACORA.md", "w", encoding="utf-8").write("\n".join(out) + "\n")
