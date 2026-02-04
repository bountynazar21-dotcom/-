# app/handlers/reinvoice.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from ..db import moves_repo as mv_repo
from ..keyboards.moves import move_review_kb
from ..utils.text import move_text

router = Router()
PM = "HTML"


async def _safe_answer(cb: CallbackQuery, text: str, alert: bool = True):
    try:
        await cb.answer(text, show_alert=alert)
    except Exception:
        pass


@router.callback_query(F.data.startswith("mva:reinvoice_"))
async def mva_reinvoice(cb: CallbackQuery):
    move_id = int(cb.data.split("_")[-1])
    m = mv_repo.get_move(move_id)
    if not m:
        return await _safe_answer(cb, "❌ Переміщення не знайдено")

    # 1) піднімаємо версію накладної
    try:
        mv_repo.bump_invoice_version(move_id)
    except Exception:
        pass

    # 2) статус назад в sent (щоб по UX було як “оновлено/перевідправляємо”)
    # 3) обнуляємо підтвердження (handed/received) і коригування
    try:
        mv_repo.reset_for_reinvoice(move_id)
    except Exception:
        pass

    try:
        mv_repo.clear_hand_receive(move_id)
    except Exception:
        pass

    m2 = mv_repo.get_move(move_id) or m
    v = int(m2.get("invoice_version") or 1)

    # оператору: просто повертаємо карточку з кнопками (додати фото → готово → відправити)
    try:
        await cb.bot.send_message(
            cb.from_user.id,
            f"♻️ <b>Коригування прийнято</b>\n"
            f"Тепер додай <b>нову накладну</b> для <b>#{move_id}</b> (V{v}).\n\n"
            "Натисни «📷 Додати фото», скинь 1…10 фото, ✅ Готово, і далі «Відправити на ТТ».",
            parse_mode=PM,
        )
    except Exception:
        pass

    # редагувати повідомлення з кнопкою не завжди можна (медіа), тому просто даємо відповідь
    await cb.message.answer(move_text(m2), reply_markup=move_review_kb(move_id), parse_mode=PM)
    await _safe_answer(cb, "Ок ✅ Тепер додай нову накладну", alert=True)

