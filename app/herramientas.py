"""Herramientas de acción (function calling): leen y escriben gastos reales en SQLite."""
import json
import re
import unicodedata
from datetime import timedelta

from app.db import ahora, ahora_str, db
from app.rag import HERRAMIENTA_GUIA, buscar_en_guia

CATEGORIAS = ["comida", "transporte", "vivienda", "servicios", "salud", "entretenimiento",
              "compras", "educacion", "deudas", "otros"]


def quitar_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def a_monto(valor):
    """Acepta 250, "250", "$1,250.50"; devuelve float o None si no es un monto válido."""
    if isinstance(valor, (int, float)):
        monto = float(valor)
    else:
        limpio = re.sub(r"[^\d.]", "", str(valor).replace(",", ""))
        try:
            monto = float(limpio)
        except ValueError:
            return None
    return monto if 0 < monto < 1_000_000 else None


def normalizar_categoria(categoria):
    c = quitar_acentos(str(categoria or "").lower().strip())
    return c if c in CATEGORIAS else "otros"


def fmt(monto):
    return f"${monto:,.2f}"


# ---------------- Funciones reales ----------------

def registrar_gasto(numero, monto=None, categoria="otros", descripcion=""):
    monto_ok = a_monto(monto)
    if monto_ok is None:
        return "No se registró nada: falta un monto válido. Pide al usuario la cantidad que gastó."
    cat = normalizar_categoria(categoria)
    with db() as con:
        con.execute("INSERT INTO gastos (numero, monto, categoria, descripcion, fecha) VALUES (?, ?, ?, ?, ?)",
                    (numero, monto_ok, cat, (descripcion or "")[:100], ahora_str()))
    return f"Gasto registrado: {fmt(monto_ok)} en {cat}" + (f" ({descripcion})." if descripcion else ".")


def deshacer_ultimo_gasto(numero):
    with db() as con:
        fila = con.execute("SELECT id, monto, categoria FROM gastos WHERE numero = ? ORDER BY id DESC LIMIT 1",
                           (numero,)).fetchone()
        if not fila:
            return "No hay gastos registrados para borrar."
        con.execute("DELETE FROM gastos WHERE id = ?", (fila["id"],))
    return f"Se eliminó el último gasto: {fmt(fila['monto'])} en {fila['categoria']}."


def definir_presupuesto(numero, monto_mensual=None):
    monto_ok = a_monto(monto_mensual)
    if monto_ok is None:
        return "No se guardó el presupuesto: falta un monto mensual válido."
    with db() as con:
        con.execute("INSERT OR REPLACE INTO presupuestos (numero, monto_mensual, actualizado) VALUES (?, ?, ?)",
                    (numero, monto_ok, ahora_str()))
    return f"Presupuesto mensual guardado: {fmt(monto_ok)}."


def inicio_periodo(periodo):
    hoy = ahora().replace(hour=0, minute=0, second=0, microsecond=0)
    if periodo == "hoy":
        return hoy
    if periodo == "semana":
        return hoy - timedelta(days=hoy.weekday())
    return hoy.replace(day=1)


def resumen_gastos(numero, periodo="mes"):
    periodo = periodo if periodo in ("hoy", "semana", "mes") else "mes"
    desde = inicio_periodo(periodo).strftime("%Y-%m-%d %H:%M:%S")
    with db() as con:
        filas = con.execute("""SELECT categoria, SUM(monto) AS total, COUNT(*) AS n FROM gastos
                               WHERE numero = ? AND fecha >= ? GROUP BY categoria ORDER BY total DESC""",
                            (numero, desde)).fetchall()
        pres = con.execute("SELECT monto_mensual FROM presupuestos WHERE numero = ?", (numero,)).fetchone()
    if not filas:
        return f"No hay gastos registrados en el periodo '{periodo}'."
    total = sum(f["total"] for f in filas)
    detalle = ", ".join(f"{f['categoria']} {fmt(f['total'])}" for f in filas)
    texto = (f"Gastos del periodo '{periodo}': total {fmt(total)} en {sum(f['n'] for f in filas)} registros. "
             f"Por categoría: {detalle}.")
    if pres and periodo == "mes":
        presupuesto = pres["monto_mensual"]
        hoy = ahora()
        dias_mes = ((hoy.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
        proyeccion = total / hoy.day * dias_mes
        texto += (f" Presupuesto mensual {fmt(presupuesto)}: usado {total / presupuesto:.0%}, "
                  f"disponible {fmt(presupuesto - total)}. Al ritmo actual cerraría el mes en {fmt(proyeccion)}.")
    elif not pres:
        texto += " El usuario aún no define un presupuesto mensual."
    return texto


# ---------------- Schemas para Llama ----------------

HERRAMIENTAS = [
    {"type": "function", "name": "registrar_gasto",
     "description": "Registra un gasto que el usuario ya hizo. Úsala solo si el usuario menciona una cantidad gastada.",
     "parameters": {"type": "object", "properties": {
         "monto": {"type": "number", "description": "Cantidad gastada en pesos, solo el número."},
         "categoria": {"type": "string", "enum": CATEGORIAS, "description": "Categoría que mejor describe el gasto."},
         "descripcion": {"type": "string", "description": "En qué se gastó, en pocas palabras (ej. 'uber', 'tacos')."}},
         "required": ["monto", "categoria"]}},
    {"type": "function", "name": "deshacer_ultimo_gasto",
     "description": "Elimina el último gasto registrado cuando el usuario dice que se equivocó o pide borrarlo.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"type": "function", "name": "resumen_gastos",
     "description": "Consulta cuánto ha gastado el usuario y cómo va contra su presupuesto.",
     "parameters": {"type": "object", "properties": {
         "periodo": {"type": "string", "enum": ["hoy", "semana", "mes"], "description": "Periodo a consultar."}},
         "required": ["periodo"]}},
    {"type": "function", "name": "definir_presupuesto",
     "description": "Guarda el presupuesto mensual que el usuario quiere gastar como máximo.",
     "parameters": {"type": "object", "properties": {
         "monto_mensual": {"type": "number", "description": "Presupuesto mensual en pesos, solo el número."}},
         "required": ["monto_mensual"]}},
    HERRAMIENTA_GUIA,
]

FUNCIONES_DISPONIBLES = {
    "registrar_gasto": registrar_gasto,
    "deshacer_ultimo_gasto": deshacer_ultimo_gasto,
    "resumen_gastos": resumen_gastos,
    "definir_presupuesto": definir_presupuesto,
    "buscar_en_guia": buscar_en_guia,
}
FUNCIONES_CON_NUMERO = {"registrar_gasto", "deshacer_ultimo_gasto", "resumen_gastos", "definir_presupuesto"}


def ejecutar_herramienta(numero, nombre, argumentos_json):
    """Ejecuta lo que pidió el modelo y SIEMPRE regresa texto (si falla, el modelo puede explicarlo)."""
    if nombre not in FUNCIONES_DISPONIBLES:
        return f"La herramienta {nombre} no existe."
    try:
        argumentos = json.loads(argumentos_json) if argumentos_json else {}
    except json.JSONDecodeError:
        argumentos = {}
    if not isinstance(argumentos, dict):
        argumentos = {}
    argumentos.pop("numero", None)                 # el modelo nunca decide de quién son los datos
    if nombre in FUNCIONES_CON_NUMERO:
        argumentos["numero"] = numero
    try:
        return FUNCIONES_DISPONIBLES[nombre](**argumentos)
    except TypeError as e:
        return f"Argumentos inválidos para {nombre}: {e}"
