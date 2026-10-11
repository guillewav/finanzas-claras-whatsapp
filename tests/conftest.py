"""Pruebas sin modelos: Llama Stack, Llama Guard y embeddings se reemplazan por dobles de prueba."""
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(MODO_SIMULACION="1", CALENTAR_MODELOS="0", WHATSAPP_APP_SECRET="secreto_test",
                  DB_PATH=os.path.join(tempfile.mkdtemp(), "test.db"))

from app import db, llm, rag, seguridad  # noqa: E402


def embedding_falso(textos):
    out = []
    for t in textos:
        v = np.zeros(384)
        for w in re.findall(r"\w+", t.lower()):
            if len(w) > 3:
                v[int(hashlib.md5(w[:6].encode()).hexdigest(), 16) % 384] += 1
        n = np.linalg.norm(v)
        out.append(v / n if n else v)
    return np.array(out)


def llama_guard_falso(model, messages):
    txt = " ".join(m["content"] for m in messages).lower()
    if "bomba" in txt:
        return {"message": {"content": "unsafe\nS9"}}
    if "no quiero vivir" in txt:
        return {"message": {"content": "unsafe\nS11"}}
    return {"message": {"content": "safe"}}


class LlamaFalso:
    """Elige herramientas con reglas simples, como haría Llama, para probar el ciclo de function calling."""
    def __init__(self):
        self.n = 0
        self.conversations = SimpleNamespace(create=self._conv)
        self.responses = SimpleNamespace(create=self._resp)

    def _conv(self):
        self.n += 1
        return SimpleNamespace(id=f"conv_{self.n}")

    def _resp(self, model, input, conversation, instructions, tools):
        if isinstance(input, list):
            return SimpleNamespace(output=[], output_text=" / ".join(r["output"] for r in input))
        t = input.lower()
        calls = []

        def fc(name, args):
            calls.append(SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args),
                                         call_id=f"c{len(calls)}"))
        if "presupuesto" in t:
            fc("definir_presupuesto", {"monto_mensual": 12000})
        elif "borra" in t:
            fc("deshacer_ultimo_gasto", {})
        elif re.search(r"\d", t) and "gast" in t:
            fc("registrar_gasto", {"monto": re.search(r"\d+", t).group(), "categoria": "transporte",
                                   "descripcion": "uber", "numero": "OTRO_USUARIO"})
        elif "cuánto llevo" in t:
            fc("resumen_gastos", {"periodo": "mes"})
        if calls:
            return SimpleNamespace(output=calls, output_text="")
        return SimpleNamespace(output=[SimpleNamespace(type="message")], output_text="Solo atiendo finanzas personales.")


@pytest.fixture(autouse=True)
def dobles(monkeypatch):
    monkeypatch.setattr(rag, "codificar", embedding_falso)
    monkeypatch.setattr(rag, "_emb_guia", None)
    monkeypatch.setattr(seguridad.cliente_ollama, "chat", llama_guard_falso)
    monkeypatch.setattr(llm, "client", LlamaFalso())
    db.init_db()
    yield
