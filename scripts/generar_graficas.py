"""Genera las gráficas de resultados a partir de la base de datos REAL del agente.

Uso:
    docker compose exec app python -m scripts.generar_graficas                 # producción (/data/finanzas_claras.db)

Escribe en docs/img/: latencia.png, rutas.png, herramientas.png y docs/resultados/metricas.json
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.db import db, init_db  # noqa: E402
from app.metricas import calcular_metricas  # noqa: E402

TINTA, ACENTO, ALERTA, GRIS = "#18211D", "#0E6B5A", "#B3261E", "#8A968F"
IMG = Path("docs/img")
RES = Path("docs/resultados")


def estilo(ax, titulo):
    ax.set_title(titulo, loc="left", fontsize=13, fontweight="bold", color=TINTA)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=TINTA)
    ax.grid(axis="x", alpha=0.25)


def main():
    init_db()
    IMG.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    m = calcular_metricas()
    if m["total"] == 0:
        print("No hay métricas todavía: manda mensajes al agente o corre scripts.probar_agente primero.")
        return
    (RES / "metricas.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    with db() as con:
        filas = con.execute("SELECT ruta, duracion_s FROM metricas").fetchall()

    # 1. Latencia
    fig, ax = plt.subplots(figsize=(8, 4))
    llama = [f["duracion_s"] for f in filas if f["ruta"].startswith("llama")]
    otras = [f["duracion_s"] for f in filas if not f["ruta"].startswith("llama")]
    ax.hist([llama, otras], bins=15, stacked=True, color=[ACENTO, GRIS], label=["Responde Llama", "Reglas / bloqueos"])
    ax.axvline(m["latencia_promedio_s"], color=TINTA, ls="--", lw=1)
    ax.axvline(m["latencia_p95_s"], color=ALERTA, lw=2)
    ax.text(m["latencia_p95_s"], ax.get_ylim()[1] * 0.92, f"  p95 = {m['latencia_p95_s']} s", color=ALERTA)
    ax.text(m["latencia_promedio_s"], ax.get_ylim()[1] * 0.80, f"  promedio = {m['latencia_promedio_s']} s", color=TINTA)
    ax.set_xlabel("segundos por mensaje")
    ax.set_ylabel("mensajes")
    ax.legend(frameon=False)
    estilo(ax, f"Tiempo de respuesta ({m['total']} mensajes)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(IMG / "latencia.png", dpi=160)

    # 2. Rutas
    rutas = sorted(m["por_ruta"].items(), key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(8, 4))
    colores = [ALERTA if r.startswith("bloqueado") or r == "error" else ACENTO for r, _ in rutas]
    ax.barh([r for r, _ in rutas], [n for _, n in rutas], color=colores)
    for i, (_, n) in enumerate(rutas):
        ax.text(n, i, f" {n}", va="center", color=TINTA)
    estilo(ax, f"Ruta de cada mensaje · tasa de error {m['tasa_error']:.1%}")
    fig.tight_layout()
    fig.savefig(IMG / "rutas.png", dpi=160)

    # 3. Herramientas
    if m["herramientas_mas_usadas"]:
        h = sorted(m["herramientas_mas_usadas"].items(), key=lambda x: x[1])
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.barh([k for k, _ in h], [v for _, v in h], color=ACENTO)
        for i, (_, v) in enumerate(h):
            ax.text(v, i, f" {v}", va="center", color=TINTA)
        estilo(ax, "Herramientas que eligió Llama (function calling)")
        fig.tight_layout()
        fig.savefig(IMG / "herramientas.png", dpi=160)

    print(json.dumps(m, ensure_ascii=False, indent=2))
    print(f"Gráficas guardadas en {IMG}/")


if __name__ == "__main__":
    main()
