import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# ВАЖЛИВО:
# Не кешуємо DATABASE_URL на імпорті, бо .env може завантажитися пізніше.
# Читаємо змінну кожен раз всередині get_conn().
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # Якщо dotenv не встановлений/не потрібен у проді — просто ігноруємо.
    pass


@contextmanager
def get_conn():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set (Railway Postgres).")

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cur():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur