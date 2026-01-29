from app.db.sqlite import get_conn
from app.db.schema import ensure_schema

def list_cities():
    ensure_schema()
    with get_conn() as con:
        rows = con.execute("SELECT id, name FROM cities ORDER BY name").fetchall()
        return [(r["id"], r["name"]) for r in rows]

def add_city(name: str) -> bool:
    ensure_schema()
    name = name.strip()
    if not name:
        return False
    try:
        with get_conn() as con:
            con.execute("INSERT INTO cities(name) VALUES(?)", (name,))
            con.commit()
        return True
    except Exception:
        return False

def delete_city(city_id: int) -> bool:
    ensure_schema()
    with get_conn() as con:
        cur = con.execute("DELETE FROM cities WHERE id = ?", (city_id,))
        con.commit()
        return cur.rowcount > 0

def list_points(city_id: int):
    ensure_schema()
    with get_conn() as con:
        rows = con.execute(
            "SELECT id, name FROM points WHERE city_id=? ORDER BY name",
            (city_id,),
        ).fetchall()
        return [(r["id"], r["name"]) for r in rows]

def add_point(city_id: int, name: str) -> bool:
    ensure_schema()
    name = name.strip()
    if not name:
        return False
    try:
        with get_conn() as con:
            con.execute("INSERT INTO points(city_id, name) VALUES(?,?)", (city_id, name))
            con.commit()
        return True
    except Exception:
        return False

def delete_point(point_id: int) -> bool:
    ensure_schema()
    with get_conn() as con:
        cur = con.execute("DELETE FROM points WHERE id = ?", (point_id,))
        con.commit()
        return cur.rowcount > 0

def count_points(city_id: int) -> int:
    ensure_schema()
    with get_conn() as con:
        row = con.execute("SELECT COUNT(*) AS c FROM points WHERE city_id=?", (city_id,)).fetchone()
        return int(row["c"]) if row else 0
