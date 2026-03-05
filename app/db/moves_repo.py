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


def set_photo(move_id: int, file_id: Optional[str]) -> None:
    """
    photo_file_id = превʼю (перше фото). Для PDF можна ставити None.
    """
    ensure_schema()
    with get_cur() as cur:
        cur.execute("UPDATE moves SET photo_file_id=%s, updated_at=NOW() WHERE id=%s", (file_id, move_id))

    # якщо file_id None — не пишемо в історію (бо історія в тебе photo-centric)
    if not file_id:
        return

    # записати в історію як поточну версію (V1 якщо ще не було)
    v = get_invoice_version(move_id)
    add_invoice_version(move_id, v, file_id)


# ---------- ✅ PDF INVOICE (independent) ----------
def set_invoice_pdf(move_id: int, file_id: Optional[str]) -> None:
    """
    invoice_pdf_file_id = file_id PDF накладної (незалежно від фото).
    Якщо None — прибираємо PDF.
    """
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            "UPDATE moves SET invoice_pdf_file_id=%s, updated_at=NOW() WHERE id=%s",
            (file_id, move_id),
        )


def clear_invoice_pdf(move_id: int) -> None:
    set_invoice_pdf(move_id, None)


def get_invoice_pdf(move_id: int) -> Optional[str]:
    ensure_schema()
    with get_cur() as cur:
        cur.execute("SELECT invoice_pdf_file_id FROM moves WHERE id=%s", (move_id,))
        row = cur.fetchone()
        return row.get("invoice_pdf_file_id") if row else None
# -----------------------------------------------


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
    """
    Повертає move + назви точок + ✅ invoice_photos_count для поточної версії invoice_version
    (щоб move_text() міг показати кількість фото накладної).
    """
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            SELECT
                m.*,
                fp.name AS from_point_name,
                tp.name AS to_point_name,
                COALESCE((
                    SELECT COUNT(*)
                    FROM move_invoice_photos mip
                    WHERE mip.move_id = m.id
                      AND mip.version = m.invoice_version
                ), 0) AS invoice_photos_count
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
def mark_handed(move_id: int, user_id: int) -> bool:
    """
    True  -> підтверджено вперше
    False -> вже було підтверджено раніше
    """
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            UPDATE moves
            SET handed_at=NOW(),
                handed_by=%s,
                updated_at=NOW()
            WHERE id=%s
              AND handed_at IS NULL
            """,
            (user_id, move_id),
        )
        return (cur.rowcount or 0) > 0


def mark_received(move_id: int, user_id: int) -> bool:
    """
    True  -> підтверджено вперше
    False -> вже було підтверджено раніше
    """
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            """
            UPDATE moves
            SET received_at=NOW(),
                received_by=%s,
                updated_at=NOW()
            WHERE id=%s
              AND received_at IS NULL
            """,
            (user_id, move_id),
        )
        return (cur.rowcount or 0) > 0


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
    add_invoice_version(move_id, v, file_id)


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


# --------- INVOICE HISTORY ---------
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


# ✅ multi-photo for a version
def add_invoice_photos(move_id: int, version: int, photos: list[str]) -> None:
    """
    Зберігає всі фото для (move_id, version).
    Повністю перезаписує position 0..N-1 (під твою існуючу схему).
    """
    ensure_schema()
    with get_cur() as cur:
        cur.execute(
            "DELETE FROM move_invoice_photos WHERE move_id=%s AND version=%s",
            (move_id, version)
        )
        for pos, fid in enumerate(photos):
            cur.execute(
                """
                INSERT INTO move_invoice_photos(move_id, version, position, photo_file_id)
                VALUES(%s, %s, %s, %s)
                """,
                (move_id, version, pos, fid),
            )


def list_invoice_photos(move_id: int, version: int) -> list[str]:
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