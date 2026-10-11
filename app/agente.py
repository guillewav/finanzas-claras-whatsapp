"""Flujo de decisión: seguridad de entrada -> reglas fijas -> Llama + herramientas -> seguridad de salida."""
import threading
import time

import ollama
import requests
from llama_stack_client import APIConnectionError, APIStatusError, APITimeoutError

from app import seguridad
from app.db import borrar_datos, registrar_bloqueo, registrar_error, registrar_metrica
from app.herramientas import quitar_acentos
from app.llm import generar_respuesta
from app.salud import servicios_vivos
from app.whatsapp import enviar_respuesta

FRASES_SALUDO = ["hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "que tal", "buen dia", "hey"]
FRASES_AYUDA = ["ayuda", "menu", "que puedes hacer", "como funciona"]
FRASE_BORRAR = "borrar mis datos"

MENSAJE_BIENVENIDA = ("¡Hola! Soy *Finanzas Claras* 💸. Puedo ayudarte a:\n"
                      "• Registrar gastos: _gasté 180 en comida_\n"
                      "• Ver cómo vas: _¿cuánto llevo este mes?_\n"
                      "• Fijar presupuesto: _mi presupuesto es 12 mil al mes_\n"
                      "• Resolver dudas: _¿conviene pagar el mínimo de la tarjeta?_\n"
                      "Escribe *borrar mis datos* si quieres eliminar tu información.")

_locks = {}
_lock_global = threading.Lock()


def obtener_lock(numero):
    with _lock_global:
        if numero not in _locks:
            _locks[numero] = threading.Lock()
        return _locks[numero]


def texto_normalizado(texto):
    return quitar_acentos(texto.lower()).strip(" ,.!¡¿?")


def decidir_y_responder(numero, texto):
    """Regresa (ruta, herramientas_usadas)."""
    t = texto_normalizado(texto)
    CAT = seguridad.CATEGORIAS_LLAMA_GUARD

    # 1. Seguridad sobre la entrada
    inyeccion, detector, riesgo = seguridad.es_inyeccion(texto)
    if inyeccion:
        registrar_bloqueo(numero, texto, detector, f"riesgo={riesgo:.2f}")
        enviar_respuesta(numero, seguridad.MENSAJE_BLOQUEO)
        return "bloqueado_prompt_guard", []

    seguro, categoria = seguridad.revisar_con_llama_guard([{"role": "user", "content": texto}])
    if not seguro:
        registrar_bloqueo(numero, texto, "llama_guard_entrada", f"{categoria} {CAT.get(categoria, '')}")
        enviar_respuesta(numero, seguridad.MENSAJE_APOYO if categoria == "S11" else seguridad.MENSAJE_BLOQUEO)
        return "bloqueado_llama_guard_entrada", []

    # 2. Reglas fijas
    if t in FRASES_SALUDO or t in FRASES_AYUDA:
        enviar_respuesta(numero, MENSAJE_BIENVENIDA)
        return "regla_bienvenida", []
    if t == FRASE_BORRAR:
        borrar_datos(numero)
        enviar_respuesta(numero, "Listo, eliminé tus gastos, presupuesto e historial de conversación. 🗑️")
        return "regla_borrar_datos", []

    # 3. Llama con herramientas
    respuesta, herramientas = generar_respuesta(numero, texto)

    # 4. Seguridad sobre la salida
    seguro, categoria = seguridad.revisar_con_llama_guard([
        {"role": "user", "content": texto}, {"role": "assistant", "content": respuesta}])
    if not seguro and categoria == "S6":
        enviar_respuesta(numero, respuesta + seguridad.AVISO_ASESORIA)
        return "llama_con_aviso", herramientas
    if not seguro:
        registrar_bloqueo(numero, respuesta, "llama_guard_salida", f"{categoria} {CAT.get(categoria, '')}")
        enviar_respuesta(numero, seguridad.MENSAJE_RESPUESTA_BLOQUEADA)
        return "bloqueado_llama_guard_salida", herramientas

    enviar_respuesta(numero, respuesta)
    return "llama", herramientas


def enviar_aviso_de_error(numero):
    try:
        enviar_respuesta(numero, "Estoy teniendo un problema técnico. Intenta de nuevo en un momento 🙏")
    except Exception:  # noqa: BLE001
        pass


def procesar_y_responder(numero, texto):
    with obtener_lock(numero):
        inicio = time.perf_counter()
        ruta, herramientas = "error", []
        try:
            ruta, herramientas = decidir_y_responder(numero, texto)
        except APITimeoutError as e:
            registrar_error(numero, texto, "llama_timeout", "Llama Stack conectó pero la generación tardó demasiado.", e)
            enviar_aviso_de_error(numero)
        except APIConnectionError as e:
            vivos = servicios_vivos()
            if not vivos["llama_stack"]:
                causa = "llama_stack_caido"
            elif not vivos["ollama"]:
                causa = "ollama_caido"
            else:
                causa = "conexion_desconocida"
            registrar_error(numero, texto, causa, f"Estado de servicios: {vivos}", e)
            enviar_aviso_de_error(numero)
        except APIStatusError as e:
            registrar_error(numero, texto, "llama_stack_error_http", f"Llama Stack respondió HTTP {e.status_code}.", e)
            enviar_aviso_de_error(numero)
        except (ConnectionError, ollama.ResponseError) as e:
            registrar_error(numero, texto, "llama_guard_no_disponible", "Falló la llamada a Ollama (Llama Guard).", e)
            enviar_aviso_de_error(numero)
        except requests.exceptions.RequestException as e:
            registrar_error(numero, texto, "whatsapp_api_error", "Falló el envío a la Graph API de WhatsApp.", e)
        except Exception as e:  # noqa: BLE001
            registrar_error(numero, texto, "desconocido", "Error no clasificado.", e)
            enviar_aviso_de_error(numero)
        finally:
            registrar_metrica(numero, ruta, time.perf_counter() - inicio, herramientas)
        return ruta, herramientas
