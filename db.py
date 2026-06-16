"""
Base de datos PostgreSQL para Neuron Computación.
Guarda presupuestos y contadores de forma permanente.
Si no hay DATABASE_URL (entorno local), usa archivos JSON como fallback.
"""

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
BASE_DIR = Path(__file__).parent

COUNTERS_FILE = BASE_DIR / "counters.json"
PRESUPUESTOS_FILE = BASE_DIR / "presupuestos.json"


def _get_conn():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def init_db():
    if not DATABASE_URL:
        logger.warning("⚠️ Sin DATABASE_URL — usando archivos JSON locales")
        return
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS contadores (
                tipo TEXT PRIMARY KEY,
                valor INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS presupuestos (
                numero TEXT PRIMARY KEY,
                datos JSONB NOT NULL,
                creado TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute("INSERT INTO contadores (tipo, valor) VALUES ('presupuesto', 0) ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO contadores (tipo, valor) VALUES ('comprobante', 0) ON CONFLICT DO NOTHING")
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Base de datos PostgreSQL lista")
    except Exception as e:
        logger.error(f"Error inicializando DB: {e}")


def next_number(tipo: str) -> str:
    if not DATABASE_URL:
        c = {}
        if COUNTERS_FILE.exists():
            with open(COUNTERS_FILE) as f: c = json.load(f)
        c[tipo] = c.get(tipo, 0) + 1
        with open(COUNTERS_FILE, "w") as f: json.dump(c, f)
        return str(c[tipo]).zfill(4)

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE contadores SET valor = valor + 1 WHERE tipo = %s RETURNING valor", (tipo,))
    row = cur.fetchone()
    if row is None:
        cur.execute("INSERT INTO contadores (tipo, valor) VALUES (%s, 1) RETURNING valor", (tipo,))
        row = cur.fetchone()
    conn.commit()
    valor = row[0]
    cur.close()
    conn.close()
    return str(valor).zfill(4)


def guardar_presupuesto(numero: str, datos: dict):
    if not DATABASE_URL:
        presupuestos = {}
        if PRESUPUESTOS_FILE.exists():
            with open(PRESUPUESTOS_FILE) as f: presupuestos = json.load(f)
        presupuestos[numero] = datos
        with open(PRESUPUESTOS_FILE, "w") as f:
            json.dump(presupuestos, f, ensure_ascii=False)
        return

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO presupuestos (numero, datos) VALUES (%s, %s) "
        "ON CONFLICT (numero) DO UPDATE SET datos = EXCLUDED.datos",
        (numero, json.dumps(datos, ensure_ascii=False)))
    conn.commit()
    cur.close()
    conn.close()


def buscar_presupuesto(numero: str):
    numero_norm = numero.zfill(4)
    if not DATABASE_URL:
        if not PRESUPUESTOS_FILE.exists(): return None
        with open(PRESUPUESTOS_FILE) as f: presupuestos = json.load(f)
        return presupuestos.get(numero_norm) or presupuestos.get(numero)

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT datos FROM presupuestos WHERE numero = %s", (numero_norm,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return None
