from .pg_schema import ensure_schema
from .pg import get_cur


def list_cities():
    ensure_schema()
    with get_cur() as cur:
        cur.execute("SELECT id, name FROM cities ORDER BY name")
        rows = cur.fetchall()
        return [(r["id"], r["name"]) for r in rows]


def add_city(name: str) -> bool:
    ensure_schema()
    name = (name or "").strip()
    if not name:
        return False
    with get_cur() as cur:
        try:
            cur.execute("INSERT INTO cities(name) VALUES(%s)", (name,))
            return True
        except Exception:
            return False


def delete_city(city_id: int) -> bool:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("DELETE FROM cities WHERE id=%s", (city_id,))
        return cur.rowcount > 0


def list_points(city_id: int):
    ensure_schema()
    with get_cur() as cur:
        cur.execute("SELECT id, name FROM points WHERE city_id=%s ORDER BY name", (city_id,))
        rows = cur.fetchall()
        return [(r["id"], r["name"]) for r in rows]


def add_point(city_id: int, name: str) -> bool:
    ensure_schema()
    name = (name or "").strip()
    if not name:
        return False
    with get_cur() as cur:
        try:
            cur.execute("INSERT INTO points(city_id, name) VALUES(%s, %s)", (city_id, name))
            return True
        except Exception:
            return False


def delete_point(point_id: int) -> bool:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("DELETE FROM points WHERE id=%s", (point_id,))
        return cur.rowcount > 0


def count_points(city_id: int) -> int:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM points WHERE city_id=%s", (city_id,))
        row = cur.fetchone()
        return int(row["c"]) if row else 0

