"""Persistencia en SQLite: datos del usuario (memoria larga) y datos de operación."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from app import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS gastos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT NOT NULL, monto REAL NOT NULL, categoria TEXT NOT NULL,
    descripcion TEXT, fecha TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_gastos_numero_fecha ON gastos(numero, fecha);
CREATE TABLE IF NOT EXISTS presupuestos (
    numero TEXT PRIMARY KEY, monto_mensual REAL NOT NULL, actualizado TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversaciones (
    numero TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, ultima_actividad TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wamids (wamid TEXT PRIMARY KEY, recibido TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS metricas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, numero TEXT, ruta TEXT NOT NULL,
    duracion_s REAL NOT NULL, herramientas TEXT);
CREATE TABLE IF NOT EXISTS errores (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, numero TEXT, texto TEXT,
    causa TEXT, detalle TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS bloqueos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, numero TEXT, texto TEXT,
    capa TEXT, detalle TEXT);
"""

FORMATO = "%Y-%m-%d %H:%M:%S"


def ahora():
    return datetime.now(config.ZONA)


def ahora_str():
    return ahora().strftime(FORMATO)


def parsear(fecha_str):
    return datetime.strptime(fecha_str, FORMATO).replace(tzinfo=config.ZONA)


@contextmanager
def db():
    # Una conexión por operación: segura desde los hilos de BackgroundTasks
    con = sqlite3.connect(config.DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with db() as con:
        con.executescript(ESQUEMA)


def enmascarar(numero):
    # En logs de operación solo se guardan los últimos 4 dígitos
    return "***" + numero[-4:] if numero else None


def registrar_bloqueo(numero, texto, capa, detalle):
    with db() as con:
        con.execute("INSERT INTO bloqueos (ts, numero, texto, capa, detalle) VALUES (?, ?, ?, ?, ?)",
                    (ahora_str(), enmascarar(numero), (texto or "")[:500], capa, detalle))


def registrar_error(numero, texto, causa, detalle, error):
    with db() as con:
        con.execute("INSERT INTO errores (ts, numero, texto, causa, detalle, error) VALUES (?, ?, ?, ?, ?, ?)",
                    (ahora_str(), enmascarar(numero), (texto or "")[:500], causa, detalle, repr(error)[:500]))


def registrar_metrica(numero, ruta, duracion, herramientas):
    with db() as con:
        con.execute("INSERT INTO metricas (ts, numero, ruta, duracion_s, herramientas) VALUES (?, ?, ?, ?, ?)",
                    (ahora_str(), enmascarar(numero), ruta, round(duracion, 2), ",".join(herramientas)))


def es_wamid_nuevo(wamid):
    # Idempotencia: INSERT OR IGNORE es atómico, así dos reintentos simultáneos no pasan ambos
    with db() as con:
        cur = con.execute("INSERT OR IGNORE INTO wamids (wamid, recibido) VALUES (?, ?)", (wamid, ahora_str()))
        return cur.rowcount == 1


def borrar_datos(numero):
    with db() as con:
        for tabla in ("gastos", "presupuestos", "conversaciones"):
            con.execute(f"DELETE FROM {tabla} WHERE numero = ?", (numero,))
