"""Chequeo de salud de los servicios externos (reemplaza al proceso.poll() del notebook)."""
import requests

from app import config


def _vivo(url):
    try:
        return requests.get(url, timeout=3).status_code < 500
    except requests.exceptions.RequestException:
        return False


def servicios_vivos():
    return {
        "ollama": _vivo(f"{config.OLLAMA_HOST}/api/tags"),
        "llama_stack": _vivo(f"{config.LLAMA_STACK_URL}/v1/health"),
    }
