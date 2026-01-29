import sqlite3
from typing import Optional

_DB_PATH: Optional[str] = None

def init_db(db_path: str):
    global _DB_PATH
    _DB_PATH = db_path

def get_conn() -> sqlite3.Connection:
    if not _DB_PATH:
        raise RuntimeError("DB не ініціалізована. Виклич init_db(db_path) у main.py")
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con
