import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL")


@contextmanager
def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set (Railway Postgres).")

    conn = psycopg2.connect(DATABASE_URL)
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
