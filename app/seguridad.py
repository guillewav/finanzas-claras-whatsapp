"""Capa de seguridad: Prompt Guard (manipulación) + Llama Guard 3 (contenido)."""
import logging
import re

import ollama

from app import config
from app.herramientas import quitar_acentos

log = logging.getLogger("finanzas_claras")

CATEGORIAS_LLAMA_GUARD = {
    "S1": "Delitos violentos", "S2": "Delitos no violentos", "S3": "Delitos sexuales",
    "S4": "Explotación sexual infantil", "S5": "Difamación", "S6": "Asesoría especializada",
    "S7": "Privacidad", "S8": "Propiedad intelectual", "S9": "Armas indiscriminadas",
    "S10": "Odio", "S11": "Suicidio y autolesión", "S12": "Contenido sexual",
    "S13": "Elecciones", "S14": "Abuso de intérprete de código",
}

MENSAJE_BLOQUEO = ("Lo siento, no puedo ayudar con ese mensaje. Puedo ayudarte a registrar gastos "
                   "o resolver dudas de finanzas personales.")
MENSAJE_RESPUESTA_BLOQUEADA = "No puedo compartir esa respuesta. ¿Te ayudo con otra duda sobre tus finanzas?"
MENSAJE_APOYO = ("Siento que estés pasando por esto. Las deudas pueden pesar mucho, pero no tienes que enfrentarlo solo. "
                 "Si sientes que no puedes más, llama a la Línea de la Vida: 800 911 2000 (gratuita, 24 h). "
                 "Cuando quieras, también podemos revisar juntos tus gastos y armar un plan.")
AVISO_ASESORIA = "\n\n_Orientación general, no sustituye asesoría financiera profesional._"

cliente_ollama = ollama.Client(host=config.OLLAMA_HOST)


def revisar_con_llama_guard(mensajes):
    r = cliente_ollama.chat(model=config.MODELO_GUARD, messages=mensajes)
    veredicto = r["message"]["content"].strip().lower()
    if veredicto.startswith("safe"):
        return True, None
    if veredicto.startswith("unsafe"):
        partes = veredicto.split()
        return False, partes[1].upper() if len(partes) > 1 else "SIN_CATEGORIA"
    raise ValueError(f"Veredicto inesperado de Llama Guard: {veredicto!r}")


# ---------------- Prompt Guard ----------------

_pg = {"activo": False, "tokenizer": None, "modelo": None, "indice_benigno": 0}


def cargar_prompt_guard():
    """Intenta cargar Prompt Guard (repo restringido de HF). Si falla, queda la heurística de respaldo."""
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        kwargs = {"token": config.HF_TOKEN} if config.HF_TOKEN else {}
        _pg["tokenizer"] = AutoTokenizer.from_pretrained(config.PROMPT_GUARD_MODELO, **kwargs)
        _pg["modelo"] = AutoModelForSequenceClassification.from_pretrained(config.PROMPT_GUARD_MODELO, **kwargs)
        etiquetas = {i: l.upper() for i, l in _pg["modelo"].config.id2label.items()}
        _pg["indice_benigno"] = next((i for i, l in etiquetas.items() if l in ("BENIGN", "LABEL_0")), 0)
        _pg["activo"] = True
        log.info("Prompt Guard listo: %s", etiquetas)
    except Exception as e:  # noqa: BLE001
        log.warning("Prompt Guard no disponible, se usa heurística de respaldo: %r", e)
    return _pg["activo"]


def prompt_guard_activo():
    return _pg["activo"]


PATRONES_INYECCION = [
    r"ignora\w* (todas )?(tus|las|mis)? ?(instrucciones|reglas)",
    r"olvida\w* (todas )?(tus|las)? ?(instrucciones|reglas)",
    r"(system prompt|prompt del sistema|tus instrucciones (internas|originales))",
    r"ignore (all )?(previous|prior|your) (instructions|rules)",
    r"modo (desarrollador|dios|sin restricciones)",
    r"\bjailbreak\b",
    r"(eres|ahora eres) un (modelo|asistente) sin (reglas|restricciones|filtros)",
]


def riesgo_inyeccion(texto):
    """Regresa (riesgo entre 0 y 1, detector usado). riesgo = 1 - p(benigno)."""
    if _pg["activo"]:
        import torch
        entradas = _pg["tokenizer"](texto, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            logits = _pg["modelo"](**entradas).logits[0]
        probabilidades = torch.softmax(logits, dim=-1)
        return 1 - probabilidades[_pg["indice_benigno"]].item(), "prompt_guard"
    texto_norm = quitar_acentos(texto.lower())
    atrapado = any(re.search(p, texto_norm) for p in PATRONES_INYECCION)
    return (1.0 if atrapado else 0.0), "heuristica_respaldo"


def es_inyeccion(texto):
    riesgo, detector = riesgo_inyeccion(texto)
    return riesgo >= config.UMBRAL_PROMPT_GUARD, detector, riesgo
