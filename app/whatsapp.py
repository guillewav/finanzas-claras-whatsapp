"""Envío por Graph API, normalización de números y verificación de firma de Meta."""
import hashlib
import hmac
import logging

import requests

from app import config

log = logging.getLogger("finanzas_claras")
respuestas_simuladas = []   # en MODO_SIMULACION, aquí quedan las respuestas


def normalizar_numero_mx(numero):
    # Meta entrega "521XXXXXXXXXX"; para enviar se usa "52XXXXXXXXXX"
    if numero.startswith("521") and len(numero) == 13:
        return "52" + numero[3:]
    return numero


def enviar_respuesta(numero, texto):
    texto = texto[:config.LIMITE_WHATSAPP]
    if config.MODO_SIMULACION:
        respuestas_simuladas.append({"numero": numero, "texto": texto})
        log.info("[simulación] -> %s: %s", numero, texto)
        return
    url = f"https://graph.facebook.com/{config.GRAPH_VERSION}/{config.PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {config.WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": numero, "type": "text", "text": {"body": texto}}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()   # 401 = token vencido -> se clasifica como whatsapp_api_error


def firma_valida(cuerpo_bytes, firma_header):
    if not config.APP_SECRET:
        return True   # sin secreto no se puede verificar (aceptable solo en desarrollo)
    esperado = "sha256=" + hmac.new(config.APP_SECRET.encode(), cuerpo_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, firma_header or "")
