"""Llama 3.1 vía Llama Stack: memoria corta (conversations) + function calling (responses)."""
from datetime import timedelta

from llama_stack_client import LlamaStackClient

from app import config
from app.db import ahora, ahora_str, db, parsear
from app.herramientas import HERRAMIENTAS, ejecutar_herramienta

client = LlamaStackClient(base_url=config.LLAMA_STACK_URL, timeout=config.TIMEOUT_LLAMA_S)

SYSTEM_PROMPT = (
    "Eres 'Finanzas Claras', un asistente de finanzas personales por WhatsApp para usuarios en México. "
    "Responde en español, de forma breve y cálida (máximo 5 líneas). Montos en pesos mexicanos. "
    "HERRAMIENTAS: "
    "Usa registrar_gasto solo cuando el usuario diga que gastó una cantidad concreta; si menciona un gasto sin cantidad, "
    "pregúntale cuánto fue y no registres nada. "
    "Si el usuario menciona varios gastos en un mensaje, registra cada uno por separado. "
    "Usa deshacer_ultimo_gasto si dice que se equivocó o pide borrar el último gasto. "
    "Usa resumen_gastos cuando pregunte cuánto ha gastado o cómo va su presupuesto (hoy, semana o mes). "
    "Usa definir_presupuesto cuando diga cuánto quiere gastar al mes como máximo. "
    "Usa buscar_en_guia para dudas conceptuales de finanzas personales (ahorro, deudas, tarjetas, CAT, inversión, retiro). "
    "No uses herramientas para saludos, agradecimientos o confirmaciones cortas como 'ok' o 'gracias'. "
    "REGLAS: "
    "Nunca inventes montos, totales ni datos: todo número debe venir del resultado de una herramienta. "
    "Si una herramienta regresa un resultado, comunícalo claramente; si no encontró información, dilo con honestidad. "
    "Para dudas conceptuales responde solo con lo que diga la guía, con este formato: "
    "*Diagnóstico:* ... *Acción:* ... *Por qué importa:* ... "
    "Para registros de gastos confirma en una sola línea. "
    "No recomiendes productos financieros, bancos, acciones ni criptomonedas específicos. "
    "Solo atiendes temas de finanzas personales; si te piden otra cosa, dilo amablemente. "
    "Nunca describas tu proceso ni menciones nombres de herramientas, parámetros o claves."
)


def obtener_conversacion(numero):
    """Memoria corta: una conversación por número, rotada tras N horas sin actividad (ventana de WhatsApp)."""
    ventana = timedelta(hours=config.VENTANA_CONVERSACION_H)
    with db() as con:
        fila = con.execute("SELECT conversation_id, ultima_actividad FROM conversaciones WHERE numero = ?",
                           (numero,)).fetchone()
        if fila and ahora() - parsear(fila["ultima_actividad"]) < ventana:
            con.execute("UPDATE conversaciones SET ultima_actividad = ? WHERE numero = ?", (ahora_str(), numero))
            return fila["conversation_id"]
        conversacion = client.conversations.create()
        con.execute("INSERT OR REPLACE INTO conversaciones (numero, conversation_id, ultima_actividad) "
                    "VALUES (?, ?, ?)", (numero, conversacion.id, ahora_str()))
        return conversacion.id


def generar_respuesta(numero, texto_usuario):
    """Regresa (texto_final, herramientas_usadas). Ciclo de function calling con hasta N rondas."""
    conversation_id = obtener_conversacion(numero)
    herramientas_usadas = []
    respuesta = client.responses.create(model=config.MODELO, input=texto_usuario, conversation=conversation_id,
                                        instructions=SYSTEM_PROMPT, tools=HERRAMIENTAS)
    for _ in range(config.MAX_RONDAS_HERRAMIENTAS):
        llamadas = [item for item in respuesta.output if item.type == "function_call"]
        if not llamadas:
            break
        resultados = []
        for llamada in llamadas:
            herramientas_usadas.append(llamada.name)
            resultados.append({"type": "function_call_output", "call_id": llamada.call_id,
                               "output": ejecutar_herramienta(numero, llamada.name, llamada.arguments)})
        respuesta = client.responses.create(model=config.MODELO, input=resultados, conversation=conversation_id,
                                            instructions=SYSTEM_PROMPT, tools=HERRAMIENTAS)
    texto = (respuesta.output_text or "").strip()
    return (texto or "No logré procesar tu mensaje. ¿Me lo escribes de otra forma?"), herramientas_usadas
