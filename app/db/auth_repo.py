from .pg_schema import ensure_schema
from .pg import get_cur


def upsert_user(telegram_id: int, username: str | None, full_name: str | None, role: str = "point") -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            INSERT INTO users(telegram_id, username, full_name, role)
            VALUES(%s, %s, %s, %s)
            ON CONFLICT (telegram_id) DO UPDATE SET
              username = COALESCE(EXCLUDED.username, users.username),
              full_name = COALESCE(EXCLUDED.full_name, users.full_name),
              role = EXCLUDED.role
            """,
            (telegram_id, username, full_name, role),
        )


def link_user_to_point(telegram_id: int, point_id: int, username: str | None, full_name: str | None) -> None:
    ensure_schema()
    upsert_user(telegram_id, username, full_name, "point")
    with get_cur() as cur:
        cur.execute(
            """
            INSERT INTO point_users(telegram_id, point_id)
            VALUES(%s, %s)
            ON CONFLICT (telegram_id) DO UPDATE SET point_id = EXCLUDED.point_id
            """,
            (telegram_id, point_id),
        )


def get_user_point_id(telegram_id: int) -> int | None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("SELECT point_id FROM point_users WHERE telegram_id=%s", (telegram_id,))
        row = cur.fetchone()
        return int(row["point_id"]) if row else None


def get_point_users(point_id: int) -> list[dict]:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            SELECT u.telegram_id, u.username, u.full_name, pu.created_at
            FROM point_users pu
            JOIN users u ON u.telegram_id = pu.telegram_id
            WHERE pu.point_id=%s
            ORDER BY pu.created_at DESC
            """,
            (point_id,),
        )
        return cur.fetchall()


def unlink_user(telegram_id: int) -> bool:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("DELETE FROM point_users WHERE telegram_id=%s", (telegram_id,))
        return cur.rowcount > 0

