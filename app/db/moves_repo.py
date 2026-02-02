from typing import Optional, List, Dict
from .pg_schema import ensure_schema
from .pg import get_cur


def create_move(created_by: int) -> int:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            "INSERT INTO moves (created_by, operator_id) VALUES (%s, %s) RETURNING id",
            (created_by, created_by),
        )
        return int(cur.fetchone()["id"])


def set_operator(move_id: int, operator_id: int) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("UPDATE moves SET operator_id=%s, updated_at=NOW() WHERE id=%s", (operator_id, move_id))


def set_from_point(move_id: int, point_id: int) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("UPDATE moves SET from_point_id=%s, updated_at=NOW() WHERE id=%s", (point_id, move_id))


def set_to_point(move_id: int, point_id: int) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("UPDATE moves SET to_point_id=%s, updated_at=NOW() WHERE id=%s", (point_id, move_id))


def set_photo(move_id: int, file_id: str) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("UPDATE moves SET photo_file_id=%s, updated_at=NOW() WHERE id=%s", (file_id, move_id))

    # записати як V поточну версію (і як 1 фото)
    v = get_invoice_version(move_id)
    add_invoice_version(move_id, v, file_id)          # fallback таблиця (одне фото)
    add_invoice_photos(move_id, v, [file_id])         # нова таблиця (список фото)


def set_note(move_id: int, note: str) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("UPDATE moves SET note=%s, updated_at=NOW() WHERE id=%s", (note, move_id))


def set_status(move_id: int, status: str) -> bool:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("UPDATE moves SET status=%s, updated_at=NOW() WHERE id=%s", (status, move_id))
        return cur.rowcount > 0


def get_move(move_id: int) -> Optional[Dict]:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            SELECT m.*,
                   fp.name AS from_point_name,
                   tp.name AS to_point_name
            FROM moves m
            LEFT JOIN points fp ON fp.id = m.from_point_id
            LEFT JOIN points tp ON tp.id = m.to_point_id
            WHERE m.id=%s
            """,
            (move_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_moves(limit: int = 20) -> List[Dict]:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            SELECT m.*,
                   fp.name AS from_point_name,
                   tp.name AS to_point_name
            FROM moves m
            LEFT JOIN points fp ON fp.id = m.from_point_id
            LEFT JOIN points tp ON tp.id = m.to_point_id
            ORDER BY m.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


def list_moves_active(limit: int = 50) -> List[Dict]:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            SELECT m.*,
                   fp.name AS from_point_name,
                   tp.name AS to_point_name
            FROM moves m
            LEFT JOIN points fp ON fp.id = m.from_point_id
            LEFT JOIN points tp ON tp.id = m.to_point_id
            WHERE m.status NOT IN ('done', 'canceled')
            ORDER BY m.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


def list_moves_closed(limit: int = 30) -> List[Dict]:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            SELECT m.*,
                   fp.name AS from_point_name,
                   tp.name AS to_point_name
            FROM moves m
            LEFT JOIN points fp ON fp.id = m.from_point_id
            LEFT JOIN points tp ON tp.id = m.to_point_id
            WHERE m.status IN ('done', 'canceled')
            ORDER BY m.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


# --------- TT ACTIONS ---------

def mark_handed(move_id: int, user_id: int) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            "UPDATE moves SET handed_at=NOW(), handed_by=%s, updated_at=NOW() WHERE id=%s",
            (user_id, move_id),
        )


def mark_received(move_id: int, user_id: int) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            "UPDATE moves SET received_at=NOW(), received_by=%s, updated_at=NOW() WHERE id=%s",
            (user_id, move_id),
        )


def clear_hand_receive(move_id: int) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            UPDATE moves
            SET handed_at=NULL, handed_by=NULL,
                received_at=NULL, received_by=NULL,
                updated_at=NOW()
            WHERE id=%s
            """,
            (move_id,),
        )


# --------- CORRECTION ---------

def request_correction(move_id: int, user_id: int, note: str, photo_file_id: Optional[str]) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            UPDATE moves
            SET correction_status='requested',
                correction_note=%s,
                correction_photo_file_id=%s,
                correction_by=%s,
                correction_at=NOW(),
                updated_at=NOW()
            WHERE id=%s
            """,
            (note, photo_file_id, user_id, move_id),
        )


def resolve_correction(move_id: int) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            "UPDATE moves SET correction_status='resolved', updated_at=NOW() WHERE id=%s",
            (move_id,),
        )


def bump_invoice_version(move_id: int) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            "UPDATE moves SET invoice_version=invoice_version+1, updated_at=NOW() WHERE id=%s",
            (move_id,),
        )


def set_invoice_photo(move_id: int, file_id: str) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("UPDATE moves SET photo_file_id=%s, updated_at=NOW() WHERE id=%s", (file_id, move_id))

    v = get_invoice_version(move_id)
    add_invoice_version(move_id, v, file_id)          # fallback
    add_invoice_photos(move_id, v, [file_id])  


def reset_for_reinvoice(move_id: int) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            UPDATE moves
            SET status='sent',
                handed_at=NULL, handed_by=NULL,
                received_at=NULL, received_by=NULL,
                correction_status='resolved',
                updated_at=NOW()
            WHERE id=%s
            """,
            (move_id,),
        )

def add_invoice_version(move_id: int, version: int, file_id: str) -> None:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            INSERT INTO move_invoices(move_id, version, photo_file_id)
            VALUES(%s, %s, %s)
            ON CONFLICT (move_id, version) DO UPDATE SET photo_file_id = EXCLUDED.photo_file_id
            """,
            (move_id, version, file_id),
        )

def list_invoices(move_id: int) -> list[dict]:
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            SELECT version, photo_file_id, created_at
            FROM move_invoices
            WHERE move_id=%s
            ORDER BY version ASC
            """,
            (move_id,),
        )
        return cur.fetchall()

def get_invoice_version(move_id: int) -> int:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("SELECT invoice_version FROM moves WHERE id=%s", (move_id,))
        row = cur.fetchone()
        return int(row["invoice_version"]) if row and row.get("invoice_version") else 1

def add_invoice_photos(move_id: int, version: int, file_ids: list[str]) -> None:
    """
    Зберігає список фото накладної для конкретної версії.
    Якщо така версія вже була — перезаписує (щоб reinvoice оновлював).
    """
    ensure_schema()
    with get_cur() as cur:
        # перезаписуємо конкретну версію
        cur.execute("DELETE FROM move_invoice_photos WHERE move_id=%s AND version=%s", (move_id, version))
        for idx, fid in enumerate(file_ids):
            cur.execute(
                """
                INSERT INTO move_invoice_photos(move_id, version, photo_file_id, position)
                VALUES(%s, %s, %s, %s)
                """,
                (move_id, version, fid, idx),
            )

def list_invoice_photos(move_id: int, version: int) -> list[str]:
    """
    Повертає всі фото накладної для версії (в правильному порядку).
    """
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            SELECT photo_file_id
            FROM move_invoice_photos
            WHERE move_id=%s AND version=%s
            ORDER BY position ASC
            """,
            (move_id, version),
        )
        rows = cur.fetchall()
        return [r["photo_file_id"] for r in rows]

def list_invoice_versions(move_id: int) -> list[int]:
    """
    Повертає список версій накладних, які є в move_invoice_photos.
    """
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            SELECT DISTINCT version
            FROM move_invoice_photos
            WHERE move_id=%s
            ORDER BY version ASC
            """,
            (move_id,),
        )
        return [int(r["version"]) for r in cur.fetchall()]
