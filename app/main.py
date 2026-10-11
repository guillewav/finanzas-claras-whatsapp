"""Servidor FastAPI: webhook de WhatsApp + endpoints de monitoreo."""
import json
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from app import config, rag, seguridad
from app.agente import procesar_y_responder
from app.db import es_wamid_nuevo, init_db
from app.metricas import calcular_metricas
from app.salud import servicios_vivos
from app.whatsapp import enviar_respuesta, firma_valida, normalizar_numero_mx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("finanzas_claras")
estado = {"listo": False}


def calentar():
    """Carga modelos antes del primer usuario (la 1a llamada a Llama Guard tardó ~100 s en Colab)."""
    try:
        seguridad.cargar_prompt_guard()
        rag.embeddings_guia()
        seguridad.revisar_con_llama_guard([{"role": "user", "content": "hola"}])
        estado["listo"] = True
        log.info("Modelos calientes. Agente listo.")
    except Exception as e:  # noqa: BLE001
        log.error("Falló el calentamiento: %r", e)


@asynccontextmanager
async def lifespan(_app):
    init_db()
    if config.CALENTAR_MODELOS:
        threading.Thread(target=calentar, daemon=True).start()
    else:
        estado["listo"] = True
    yield


app = FastAPI(title="Finanzas Claras — Agente de WhatsApp con Llama", lifespan=lifespan)


@app.get("/webhook")
async def verificar_webhook(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == config.VERIFY_TOKEN:
        return PlainTextResponse(p.get("hub.challenge", ""))
    return Response(status_code=403)


@app.post("/webhook")
async def recibir_mensaje(request: Request, background_tasks: BackgroundTasks):
    cuerpo = await request.body()
    if not firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256")):
        return Response(status_code=401)
    body = json.loads(cuerpo or b"{}")
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            for mensaje in change.get("value", {}).get("messages", []):   # 'statuses' no trae 'messages'
                if not es_wamid_nuevo(mensaje.get("id", "")):
                    continue                                              # reintento de Meta
                numero = normalizar_numero_mx(mensaje.get("from", ""))
                if mensaje.get("type") == "text":
                    background_tasks.add_task(procesar_y_responder, numero, mensaje["text"]["body"])
                else:
                    background_tasks.add_task(enviar_respuesta, numero,
                                              "Por ahora solo entiendo mensajes de texto ✍️. Escríbeme tu gasto o tu duda.")
    return {"status": "ok"}


@app.get("/health")
async def health():
    vivos = servicios_vivos()
    return {"agente_listo": estado["listo"], **vivos,
            "prompt_guard": "modelo" if seguridad.prompt_guard_activo() else "heuristica_respaldo",
            "modo_simulacion": config.MODO_SIMULACION}


@app.get("/metricas")
async def metricas():
    return calcular_metricas()
