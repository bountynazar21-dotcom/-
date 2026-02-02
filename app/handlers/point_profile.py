from aiogram import Router, F
from aiogram.types import CallbackQuery

from ..db import auth_repo
from ..db.pg import get_cur

router = Router()


@router.callback_query(F.data == "pt:mytt")
async def my_tt(cb: CallbackQuery):
    point_id = auth_repo.get_user_point_id(cb.from_user.id)

    if not point_id:
        await cb.message.edit_text("❗️Ти ще не прив’язаний до ТТ. Натисни 🔐 Обрати свою ТТ.")
        await cb.answer()
        return

    with get_cur() as cur:
        cur.execute(
            """
            SELECT p.name AS point_name, c.name AS city_name
            FROM points p
            JOIN cities c ON c.id = p.city_id
            WHERE p.id = %s
            """,
            (point_id,),
        )
        row = cur.fetchone()

    if not row:
        await cb.message.edit_text("⚠️ ТТ не знайдена (можливо видалена). Переприв’яжись.")
        await cb.answer()
        return

    await cb.message.edit_text(
        f"🏷 <b>Твоя ТТ:</b>\n<b>{row['city_name']}</b> / <b>{row['point_name']}</b>\n\n"
        "Якщо треба — натисни 🔁 Змінити ТТ."
    )
    await cb.answer()
