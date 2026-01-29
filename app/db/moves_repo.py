from typing import Optional, List, Dict
from .sqlite import get_conn
from .schema import ensure_schema


def create_move(created_by: int) -> int:
    ensure_schema()
    with get_conn() as con:
        cur = con.execute(
            "INSERT INTO moves (created_by, operator_id) VALUES (?, ?)",
            (created_by, created_by),
        )
        con.commit()
        return cur.lastrowid


def set_operator(move_id: int, operator_id: int) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            "UPDATE moves SET operator_id=?, updated_at=datetime('now') WHERE id=?",
            (operator_id, move_id),
        )
        con.commit()


def set_from_point(move_id: int, point_id: int) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            "UPDATE moves SET from_point_id=?, updated_at=datetime('now') WHERE id=?",
            (point_id, move_id),
        )
        con.commit()


def set_to_point(move_id: int, point_id: int) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            "UPDATE moves SET to_point_id=?, updated_at=datetime('now') WHERE id=?",
            (point_id, move_id),
        )
        con.commit()


def set_photo(move_id: int, file_id: str) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            "UPDATE moves SET photo_file_id=?, updated_at=datetime('now') WHERE id=?",
            (file_id, move_id),
        )
        con.commit()


def set_note(move_id: int, note: str) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            "UPDATE moves SET note=?, updated_at=datetime('now') WHERE id=?",
            (note, move_id),
        )
        con.commit()


def set_status(move_id: int, status: str) -> bool:
    ensure_schema()
    with get_conn() as con:
        cur = con.execute(
            "UPDATE moves SET status=?, updated_at=datetime('now') WHERE id=?",
            (status, move_id),
        )
        con.commit()
        return cur.rowcount > 0


def get_move(move_id: int) -> Optional[Dict]:
    ensure_schema()
    with get_conn() as con:
        row = con.execute(
            """
            SELECT
                m.*,
                fp.name AS from_point_name,
                tp.name AS to_point_name
            FROM moves m
            LEFT JOIN points fp ON fp.id = m.from_point_id
            LEFT JOIN points tp ON tp.id = m.to_point_id
            WHERE m.id = ?
            """,
            (move_id,),
        ).fetchone()
        return dict(row) if row else None


def list_moves(limit: int = 20) -> List[Dict]:
    ensure_schema()
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT
                m.*,
                fp.name AS from_point_name,
                tp.name AS to_point_name
            FROM moves m
            LEFT JOIN points fp ON fp.id = m.from_point_id
            LEFT JOIN points tp ON tp.id = m.to_point_id
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# --------- TT ACTIONS ---------

def mark_handed(move_id: int, user_id: int) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            """
            UPDATE moves
            SET handed_at=datetime('now'),
                handed_by=?,
                updated_at=datetime('now')
            WHERE id=?
            """,
            (user_id, move_id),
        )
        con.commit()


def mark_received(move_id: int, user_id: int) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            """
            UPDATE moves
            SET received_at=datetime('now'),
                received_by=?,
                updated_at=datetime('now')
            WHERE id=?
            """,
            (user_id, move_id),
        )
        con.commit()


def clear_hand_receive(move_id: int) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            """
            UPDATE moves
            SET handed_at=NULL,
                handed_by=NULL,
                received_at=NULL,
                received_by=NULL,
                updated_at=datetime('now')
            WHERE id=?
            """,
            (move_id,),
        )
        con.commit()


# --------- CORRECTION ---------

def request_correction(
    move_id: int,
    user_id: int,
    note: str,
    photo_file_id: Optional[str],
) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            """
            UPDATE moves
            SET correction_status='requested',
                correction_note=?,
                correction_photo_file_id=?,
                correction_by=?,
                correction_at=datetime('now'),
                updated_at=datetime('now')
            WHERE id=?
            """,
            (note, photo_file_id, user_id, move_id),
        )
        con.commit()


def resolve_correction(move_id: int) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            """
            UPDATE moves
            SET correction_status='resolved',
                updated_at=datetime('now')
            WHERE id=?
            """,
            (move_id,),
        )
        con.commit()


def bump_invoice_version(move_id: int) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            """
            UPDATE moves
            SET invoice_version = invoice_version + 1,
                updated_at=datetime('now')
            WHERE id=?
            """,
            (move_id,),
        )
        con.commit()

def set_invoice_photo(move_id: int, file_id: str) -> None:
    ensure_schema()
    with get_conn() as con:
        con.execute(
            "UPDATE moves SET photo_file_id=?, updated_at=datetime('now') WHERE id=?",
            (file_id, move_id),
        )
        con.commit()


def reset_for_reinvoice(move_id: int) -> None:
    """
    Підготовка до V2/V3: скидаємо підтвердження ТТ і статус,
    щоб вони знову натиснули Віддав/Отримав.
    """
    ensure_schema()
    with get_conn() as con:
        con.execute(
            """
            UPDATE moves
            SET status='sent',
                handed_at=NULL,
                handed_by=NULL,
                received_at=NULL,
                received_by=NULL,
                correction_status='resolved',
                updated_at=datetime('now')
            WHERE id=?
            """,
            (move_id,),
        )
        con.commit()

def list_moves_active(limit: int = 30):
    ensure_schema()
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT m.*, fp.name AS from_point_name, tp.name AS to_point_name
            FROM moves m
            LEFT JOIN points fp ON fp.id = m.from_point_id
            LEFT JOIN points tp ON tp.id = m.to_point_id
            WHERE m.status NOT IN ('done', 'canceled')
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

def list_moves_closed(limit: int = 30):
    ensure_schema()
    with get_conn() as con:
        rows = con.execute(
            """
            SELECT m.*, fp.name AS from_point_name, tp.name AS to_point_name
            FROM moves m
            LEFT JOIN points fp ON fp.id = m.from_point_id
            LEFT JOIN points tp ON tp.id = m.to_point_id
            WHERE m.status IN ('done', 'canceled')
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


