import sqlite3
from .sqlite import get_conn


def ensure_schema() -> None:
    with get_conn() as con:
        cur = con.cursor()

        # ---------- USERS ----------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            role TEXT
        )
        """)

        # ---------- CITIES ----------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
        """)

        # ---------- POINTS (ТТ) ----------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (city_id) REFERENCES cities(id)
        )
        """)

        # ---------- POINT USERS ----------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS point_users (
            telegram_id INTEGER PRIMARY KEY,
            point_id INTEGER NOT NULL,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id),
            FOREIGN KEY (point_id) REFERENCES points(id)
        )
        """)

        # ---------- MOVES ----------
        cur.execute("""
        CREATE TABLE IF NOT EXISTS moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_point_id INTEGER,
            to_point_id INTEGER,
            photo_file_id TEXT,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by INTEGER,
            operator_id INTEGER,
            invoice_version INTEGER NOT NULL DEFAULT 1,
            handed_at TEXT,
            handed_by INTEGER,
            received_at TEXT,
            received_by INTEGER,
            correction_status TEXT NOT NULL DEFAULT 'none',
            correction_note TEXT,
            correction_photo_file_id TEXT,
            correction_by INTEGER,
            correction_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (from_point_id) REFERENCES points(id),
            FOREIGN KEY (to_point_id) REFERENCES points(id)
        )
        """)

        # ---------- LIGHT MIGRATIONS ----------
        cols = [r[1] for r in cur.execute("PRAGMA table_info(moves)").fetchall()]

        def add_col(name: str, ddl: str):
            if name not in cols:
                cur.execute(ddl)

        add_col("operator_id", "ALTER TABLE moves ADD COLUMN operator_id INTEGER")
        add_col("invoice_version", "ALTER TABLE moves ADD COLUMN invoice_version INTEGER NOT NULL DEFAULT 1")
        add_col("handed_at", "ALTER TABLE moves ADD COLUMN handed_at TEXT")
        add_col("handed_by", "ALTER TABLE moves ADD COLUMN handed_by INTEGER")
        add_col("received_at", "ALTER TABLE moves ADD COLUMN received_at TEXT")
        add_col("received_by", "ALTER TABLE moves ADD COLUMN received_by INTEGER")
        add_col("correction_status", "ALTER TABLE moves ADD COLUMN correction_status TEXT NOT NULL DEFAULT 'none'")
        add_col("correction_note", "ALTER TABLE moves ADD COLUMN correction_note TEXT")
        add_col("correction_photo_file_id", "ALTER TABLE moves ADD COLUMN correction_photo_file_id TEXT")
        add_col("correction_by", "ALTER TABLE moves ADD COLUMN correction_by INTEGER")
        add_col("correction_at", "ALTER TABLE moves ADD COLUMN correction_at TEXT")
        add_col("updated_at", "ALTER TABLE moves ADD COLUMN updated_at TEXT NOT NULL DEFAULT (datetime('now'))")

        con.commit()
