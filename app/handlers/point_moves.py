# app/handlers/point_moves.py
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from ..db import auth_repo
from ..db import moves_repo as mv_repo
from ..states.point_correction import PointCorrectionStates

router = Router()
PM = "HTML"


def _my_point_id(user_id: int) -> int | None:
    return auth_repo.get_user_point_id(user_id)


def _point_label(m: dict, side: str) -> str:
    key = "from_point_name" if side == "from" else "to_point_name"
    return m.get(key) or "—"


def _kb_only_correction(move_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Коригування", callback_data=f"pt:corr_{move_id}")]
    ])


async def _safe_edit_reply_markup(cb: CallbackQuery, reply_markup: InlineKeyboardMarkup | None):
    try:
        await cb.message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        # якщо це повідомлення з медіа-групи або його вже не можна редагувати
        return
    except Exception:
        return


def _admin_msg_handed(m: dict, confirmer_id: int) -> str:
    when = m.get("handed_at") or "—"
    return (
        f"📦 Відправник <b>{_point_label(m, 'from')}</b>\n"
        f"✅ Підтвердив: <b>{confirmer_id}</b>\n"
        f"🕒 Час: <b>{when}</b>\n"
        f"🆔 Переміщення: <b>{m['id']}</b>"
    )


def _admin_msg_received(m: dict, confirmer_id: int) -> str:
    when = m.get("received_at") or "—"
    return (
        f"📦 Отримувач <b>{_point_label(m, 'to')}</b>\n"
        f"✅ Підтвердив: <b>{confirmer_id}</b>\n"
        f"🕒 Час: <b>{when}</b>\n"
        f"🆔 Переміщення: <b>{m['id']}</b>"
    )


def _admin_msg_closed(m: dict) -> str:
    handed_by = m.get("handed_by") or "—"
    received_by = m.get("received_by") or "—"
    handed_at = m.get("handed_at") or "—"
    received_at = m.get("received_at") or "—"
    return (
        "✅ <b>Успішно, переміщення підтвердили дві точки</b>\n"
        f"🆔 ID: <b>{m['id']}</b>\n\n"
        f"📤 Відправник: <b>{_point_label(m, 'from')}</b>\n"
        f"   👤 {handed_by} • 🕒 {handed_at}\n"
        f"📥 Отримувач: <b>{_point_label(m, 'to')}</b>\n"
        f"   👤 {received_by} • 🕒 {received_at}"
    )


def _admin_msg_correction(m: dict, point_name: str, user_id: int, note: str) -> str:
    return (
        "⚠️ <b>Коригування по переміщенню</b>\n"
        f"🆔 ID: {m['id']}\n"
        f"📍 Точка: <b>{point_name}</b> ({user_id})\n"
        f"📝 Коментар: {note}\n\n"
        f"📤 Відправник: <b>{_point_label(m, 'from')}</b>\n"
        f"📥 Отримувач: <b>{_point_label(m, 'to')}</b>"
    )


@router.callback_query(F.data.startswith("pt:handed_"))
async def pt_handed(cb: CallbackQuery):
    move_id = int(cb.data.split("_")[-1])
    m = mv_repo.get_move(move_id)
    if not m:
        return await cb.answer("❌ Переміщення не знайдено", show_alert=True)

    my_point = _my_point_id(cb.from_user.id)
    if not my_point:
        return await cb.answer("❗ Ти не прив’язаний до ТТ", show_alert=True)

    if int(my_point) != int(m.get("from_point_id") or 0):
        return await cb.answer("⛔ Це не твоє переміщення (ти не відправник)", show_alert=True)

    ok = mv_repo.mark_handed(move_id, cb.from_user.id)
    if not ok:
        return await cb.answer("⚠️ Ви вже підтвердили", show_alert=True)

    # UX: знімаємо кнопку "Віддав", лишаємо "Коригування"
    await _safe_edit_reply_markup(cb, _kb_only_correction(move_id))

    m = mv_repo.get_move(move_id) or m
    op_id = m.get("operator_id") or m.get("created_by")

    if op_id:
        try:
            await cb.bot.send_message(op_id, _admin_msg_handed(m, cb.from_user.id), parse_mode=PM)
        except Exception:
            pass

    if m.get("received_at"):
        mv_repo.set_status(move_id, "done")
        m2 = mv_repo.get_move(move_id)
        if op_id and m2:
            try:
                await cb.bot.send_message(op_id, _admin_msg_closed(m2), parse_mode=PM)
            except Exception:
                pass

    await cb.answer("✅ Зафіксовано: Віддав", show_alert=True)


@router.callback_query(F.data.startswith("pt:received_"))
async def pt_received(cb: CallbackQuery):
    move_id = int(cb.data.split("_")[-1])
    m = mv_repo.get_move(move_id)
    if not m:
        return await cb.answer("❌ Переміщення не знайдено", show_alert=True)

    my_point = _my_point_id(cb.from_user.id)
    if not my_point:
        return await cb.answer("❗ Ти не прив’язаний до ТТ", show_alert=True)

    if int(my_point) != int(m.get("to_point_id") or 0):
        return await cb.answer("⛔ Це не твоє переміщення (ти не отримувач)", show_alert=True)

    ok = mv_repo.mark_received(move_id, cb.from_user.id)
    if not ok:
        return await cb.answer("⚠️ Ви вже підтвердили", show_alert=True)

    # UX: знімаємо кнопку "Отримав", лишаємо "Коригування"
    await _safe_edit_reply_markup(cb, _kb_only_correction(move_id))

    m = mv_repo.get_move(move_id) or m
    op_id = m.get("operator_id") or m.get("created_by")

    if op_id:
        try:
            await cb.bot.send_message(op_id, _admin_msg_received(m, cb.from_user.id), parse_mode=PM)
        except Exception:
            pass

    if m.get("handed_at"):
        mv_repo.set_status(move_id, "done")
        m2 = mv_repo.get_move(move_id)
        if op_id and m2:
            try:
                await cb.bot.send_message(op_id, _admin_msg_closed(m2), parse_mode=PM)
            except Exception:
                pass

    await cb.answer("✅ Зафіксовано: Отримав", show_alert=True)


@router.callback_query(F.data.startswith("pt:corr_"))
async def pt_corr_start(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])
    m = mv_repo.get_move(move_id)
    if not m:
        return await cb.answer("❌ Переміщення не знайдено", show_alert=True)

    my_point = _my_point_id(cb.from_user.id)
    if not my_point:
        return await cb.answer("❗ Ти не прив’язаний до ТТ", show_alert=True)

    if int(my_point) not in {int(m.get("from_point_id") or 0), int(m.get("to_point_id") or 0)}:
        return await cb.answer("⛔ Це не твоє переміщення", show_alert=True)

    await state.update_data(move_id=move_id, point_id=int(my_point))
    await state.set_state(PointCorrectionStates.waiting_note)

    await cb.message.answer(
        f"⚠️ <b>Коригування по переміщенню #{move_id}</b>\n\n"
        "Напиши коментар (що не так: не вистачає / зайве / інший товар):",
        parse_mode=PM,
    )
    await cb.answer()


@router.message(PointCorrectionStates.waiting_note)
async def pt_corr_note(message: Message, state: FSMContext):
    note = (message.text or "").strip()
    if not note:
        return await message.answer("Напиши текстом, що саме не так.")

    await state.update_data(note=note)
    await state.set_state(PointCorrectionStates.waiting_photo)
    await message.answer("Тепер надішли фото (або напиши <code>-</code> якщо без фото).", parse_mode=PM)


@router.message(PointCorrectionStates.waiting_photo)
async def pt_corr_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    move_id = int(data["move_id"])
    note = data.get("note", "")
    point_id = int(data.get("point_id") or 0)

    file_id = None
    if (message.text or "").strip() == "-":
        file_id = None
    elif message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        return await message.answer("Надішли фото або '-'.", parse_mode=PM)

    mv_repo.request_correction(move_id, message.from_user.id, note, file_id)

    m = mv_repo.get_move(move_id)
    if not m:
        await state.clear()
        return await message.answer("❌ Переміщення не знайдено.")

    op_id = m.get("operator_id") or m.get("created_by")

    point_name = "—"
    if point_id == int(m.get("from_point_id") or 0):
        point_name = _point_label(m, "from")
    elif point_id == int(m.get("to_point_id") or 0):
        point_name = _point_label(m, "to")

    text = _admin_msg_correction(m, point_name, message.from_user.id, note)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↪️ Надіслати нову накладну", callback_data=f"mva:reinvoice_{move_id}")]
    ])

    if op_id:
        try:
            if file_id:
                await message.bot.send_photo(op_id, photo=file_id, caption=text, reply_markup=kb, parse_mode=PM)
            else:
                await message.bot.send_message(op_id, text, reply_markup=kb, parse_mode=PM)
        except Exception:
            pass

    await state.clear()
    await message.answer("✅ Коригування відправлено оператору. Очікуй оновлену накладну.", parse_mode=PM)
