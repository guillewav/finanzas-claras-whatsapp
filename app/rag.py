"""RAG sobre la guía de finanzas personales, expuesto como herramienta de function calling."""
import numpy as np

from app import config

GUIA_FINANCIERA = [
    "Regla 50/30/20: una forma sencilla de repartir el ingreso mensual es destinar 50% a necesidades "
    "(renta, comida, transporte, servicios), 30% a gustos (salidas, suscripciones, ropa) y 20% a ahorro o pago de deudas.",
    "Fondo de emergencia: antes de invertir conviene juntar un fondo equivalente a 3 a 6 meses de gastos básicos, "
    "en un instrumento seguro y disponible de inmediato. Sirve para imprevistos como perder el empleo o una reparación.",
    "Gastos hormiga: son gastos pequeños y frecuentes (café, botanas, comisiones, apps de transporte) que por separado "
    "parecen insignificantes pero al mes pueden sumar más de lo que se ahorra. Registrarlos es el primer paso para reducirlos.",
    "Tarjeta de crédito: pagar el total del periodo (pago para no generar intereses) evita intereses. El pago mínimo "
    "mantiene la cuenta al corriente, pero la deuda crece porque el saldo restante genera intereses.",
    "CAT (Costo Anual Total): indicador que reúne tasa de interés, comisiones y otros costos de un crédito. "
    "Sirve para comparar créditos entre sí: a menor CAT, más barato es el crédito.",
    "Pagar deudas: el método avalancha prioriza la deuda con la tasa más alta (ahorra más intereses); el método bola de "
    "nieve prioriza la deuda más pequeña (da victorias rápidas y motivación). En ambos se paga el mínimo en las demás.",
    "Meses sin intereses: solo conviene si la compra estaba planeada y las mensualidades caben en el presupuesto. "
    "Acumular varias compras a meses compromete el ingreso de los meses siguientes.",
    "Ahorro automático: programar una transferencia a una cuenta de ahorro el mismo día que llega el ingreso "
    "(pagarse primero a uno mismo) funciona mejor que ahorrar lo que sobra al final del mes.",
    "Presupuesto mensual: consiste en definir cuánto se puede gastar en el mes y comparar contra lo gastado. Revisarlo "
    "una vez por semana permite corregir antes del cierre de mes, no después.",
    "Historial crediticio: el Buró de Crédito registra cómo se pagan los créditos. Pagar a tiempo y usar una parte "
    "moderada del límite de la tarjeta ayuda a construir un buen historial.",
    "Inversión para principiantes: después del fondo de emergencia, existen opciones de bajo riesgo como los CETES, "
    "que en cetesdirecto se pueden comprar desde 100 pesos. Toda inversión tiene riesgo; conviene informarse antes.",
    "Ahorro para el retiro: las aportaciones voluntarias a la AFORE incrementan el ahorro para el retiro y algunas son "
    "deducibles de impuestos dentro de los límites que marca la ley.",
]

_modelo = None
_emb_guia = None


def codificar(textos):
    """Texto -> vectores normalizados (384 dim). Carga el modelo la primera vez."""
    global _modelo
    if _modelo is None:
        from sentence_transformers import SentenceTransformer
        _modelo = SentenceTransformer(config.MODELO_EMBEDDINGS)
    return _modelo.encode(textos, normalize_embeddings=True)


def embeddings_guia():
    global _emb_guia
    if _emb_guia is None:
        _emb_guia = np.asarray(codificar(GUIA_FINANCIERA))
    return _emb_guia


def similitudes(pregunta):
    q = np.asarray(codificar([pregunta]))
    return np.dot(embeddings_guia(), q.T).flatten()       # coseno = producto punto (vectores normalizados)


def buscar_en_guia(pregunta, k=2):
    sims = similitudes(pregunta)
    indices = np.argsort(sims)[::-1][:k]
    relevantes = [i for i in indices if sims[i] >= config.UMBRAL_GUIA]
    if not relevantes:
        return "La guía no cubre esa pregunta. No hay información confiable para responderla."
    return "Fragmentos de la guía: " + " | ".join(GUIA_FINANCIERA[i] for i in relevantes)


HERRAMIENTA_GUIA = {
    "type": "function",
    "name": "buscar_en_guia",
    "description": "Busca en la guía de finanzas personales la respuesta a dudas conceptuales: ahorro, fondo de "
                   "emergencia, presupuesto, tarjetas de crédito, deudas, CAT, meses sin intereses, inversión y retiro.",
    "parameters": {
        "type": "object",
        "properties": {"pregunta": {"type": "string", "description": "La duda del usuario, en texto libre."}},
        "required": ["pregunta"],
    },
}
