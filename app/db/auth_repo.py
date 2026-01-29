from .schema import ensure_schema
from .sqlite import get_conn

def upsert_user(telegram_id: int, username: str | None, full_name: str | None, role: str = "point") -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            """
            INSERT INTO users(telegram_id, username, full_name, role)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
              username=COALESCE(excluded.username, users.username),
              full_name=COALESCE(excluded.full_name, users.full_name),
              role=excluded.role
            """,
            (telegram_id, username, full_name, role),
        )
        con.commit()


def link_user_to_point(telegram_id: int, point_id: int, username: str | None, full_name: str | None) -> None:
    ensure_schema()
    upsert_user(telegram_id, username, full_name, "point")
    with get_conn() as con:
        # 1 user = 1 point (переприв’язка замінює стару)
        con.execute(
            """
            INSERT INTO point_users(telegram_id, point_id)
            VALUES(?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET point_id=excluded.point_id
            """,
            (telegram_id, point_id),
        )
        con.commit()

def get_user_point_id(telegram_id: int) -> int | None:
    ensure_schema()
    with get_conn() as con:
        row = con.execute(
            "SELECT point_id FROM point_users WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()
        return int(row["point_id"]) if row else None

def get_point_users(point_id: int) -> list[dict]:
    """
    Повертає список користувачів прив’язаних до ТТ
    """
    ensure_schema()
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT u.telegram_id, u.username, u.full_name, pu.created_at
            FROM point_users pu
            JOIN users u ON u.telegram_id = pu.telegram_id
            WHERE pu.point_id=?
            ORDER BY pu.created_at DESC
            """,
            (point_id,),
        ).fetchall()
        return [dict(r) for r in rows]

def count_users_for_point(point_id: int) -> int:
    ensure_schema()
    with get_conn() as con:
        row = con.execute("SELECT COUNT(*) AS c FROM point_users WHERE point_id=?", (point_id,)).fetchone()
        return int(row["c"]) if row else 0

def unlink_user(telegram_id: int) -> bool:
    ensure_schema()
    with get_conn() as con:
        cur = con.execute("DELETE FROM point_users WHERE telegram_id=?", (telegram_id,))
        con.commit()
        return cur.rowcount > 0
