"""Monitoreo: volumen, tasa de error, latencia (p50/p95), bloqueos por capa y uso de herramientas."""
from collections import Counter

from app import config
from app.db import db


def percentil(valores, p):
    if not valores:
        return None
    v = sorted(valores)
    k = (len(v) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def calcular_metricas():
    with db() as con:
        filas = con.execute("SELECT ts, ruta, duracion_s, herramientas FROM metricas").fetchall()
        bloqueos = con.execute("SELECT capa, COUNT(*) n FROM bloqueos GROUP BY capa").fetchall()
        causas = con.execute("SELECT causa, COUNT(*) n FROM errores GROUP BY causa").fetchall()
    total = len(filas)
    if total == 0:
        return {"total": 0, "alertas": []}
    dur = [f["duracion_s"] for f in filas]
    dur_llama = [f["duracion_s"] for f in filas if f["ruta"].startswith("llama")]
    errores = sum(1 for f in filas if f["ruta"] == "error")
    tasa_error = errores / total
    p95 = percentil(dur, 95)
    alertas = []
    if tasa_error > config.UMBRAL_TASA_ERROR:
        alertas.append(f"tasa_error {tasa_error:.1%} > {config.UMBRAL_TASA_ERROR:.0%}")
    if p95 > config.UMBRAL_P95_S:
        alertas.append(f"latencia_p95 {p95:.1f}s > {config.UMBRAL_P95_S:.0f}s")
    return {
        "total": total,
        "volumen_por_hora": dict(Counter(f["ts"][:13] + "h" for f in filas)),
        "por_ruta": dict(Counter(f["ruta"] for f in filas)),
        "tasa_error": round(tasa_error, 4),
        "latencia_promedio_s": round(sum(dur) / total, 2),
        "latencia_p50_s": round(percentil(dur, 50), 2),
        "latencia_p95_s": round(p95, 2),
        "latencia_p95_llama_s": round(percentil(dur_llama, 95), 2) if dur_llama else None,
        "bloqueos_por_capa": {b["capa"]: b["n"] for b in bloqueos},
        "causas_de_error": {c["causa"]: c["n"] for c in causas},
        "herramientas_mas_usadas": dict(Counter(h for f in filas for h in (f["herramientas"] or "").split(",") if h)
                                        .most_common()),
        "alertas": alertas,
    }
