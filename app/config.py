"""Configuración del agente: todo sale de variables de entorno (ver .env.example)."""
import os
from zoneinfo import ZoneInfo


def _env(nombre, defecto=None):
    valor = os.getenv(nombre)
    return valor if valor not in (None, "") else defecto


def _bool(nombre, defecto=False):
    return str(_env(nombre, str(defecto))).lower() in ("1", "true", "si", "sí", "yes")


# --- WhatsApp Cloud API ---
VERIFY_TOKEN = _env("VERIFY_TOKEN", "mi_token")
WHATSAPP_TOKEN = _env("WHATSAPP_ACCESS_TOKEN")
PHONE_ID = _env("PHONE_NUMBER_ID")
WABA_ID = _env("WABA_TOKEN_ID")
APP_SECRET = _env("WHATSAPP_APP_SECRET")              # opcional: verifica X-Hub-Signature-256
GRAPH_VERSION = _env("GRAPH_API_VERSION", "v25.0")
LIMITE_WHATSAPP = 4096

# --- Modelos ---
OLLAMA_HOST = _env("OLLAMA_HOST", "http://localhost:11434")
LLAMA_STACK_URL = _env("LLAMA_STACK_URL", "http://localhost:8321")
MODELO = _env("MODELO", "ollama/llama3.1:8b")
MODELO_GUARD = _env("MODELO_GUARD", "llama-guard3")
PROMPT_GUARD_MODELO = _env("PROMPT_GUARD_MODELO", "meta-llama/Llama-Prompt-Guard-2-86M")
MODELO_EMBEDDINGS = _env("MODELO_EMBEDDINGS", "paraphrase-multilingual-MiniLM-L12-v2")
HF_TOKEN = _env("HF_TOKEN")
TIMEOUT_LLAMA_S = int(_env("TIMEOUT_LLAMA_S", "300"))  # con 60 s el cliente reintenta y duplica turnos

# --- Comportamiento ---
UMBRAL_GUIA = float(_env("UMBRAL_GUIA", "0.30"))
UMBRAL_PROMPT_GUARD = float(_env("UMBRAL_PROMPT_GUARD", "0.5"))
MAX_RONDAS_HERRAMIENTAS = int(_env("MAX_RONDAS_HERRAMIENTAS", "3"))
VENTANA_CONVERSACION_H = int(_env("VENTANA_CONVERSACION_H", "24"))
MODO_SIMULACION = _bool("MODO_SIMULACION", False)    # True: imprime en vez de enviar a WhatsApp
CALENTAR_MODELOS = _bool("CALENTAR_MODELOS", True)

# --- Persistencia y monitoreo ---
DB_PATH = _env("DB_PATH", "finanzas_claras.db")
UMBRAL_TASA_ERROR = float(_env("UMBRAL_TASA_ERROR", "0.05"))
UMBRAL_P95_S = float(_env("UMBRAL_P95_S", "30"))
ZONA = ZoneInfo(_env("ZONA_HORARIA", "America/Mexico_City"))
