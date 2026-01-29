# app/handlers/point_moves.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from ..db import auth_repo
from ..db import moves_repo as mv_repo
from ..states.point_correction import PointCorrectionStates

router = Router()


def _my_point_id(user_id: int) -> int | None:
    return auth_repo.get_user_point_id(user_id)


def _point_label(m: dict, side: str) -> str:
    # side: "from" or "to"
    key = "from_point_name" if side == "from" else "to_point_name"
    name = m.get(key) or "—"
    return name


def _admin_msg_handed(m: dict) -> str:
    return (
        f"📦 Відправник <b>{_point_label(m, 'from')}</b> "
        f"підтвердив видачу товару у переміщенні <b>{m['id']}</b>."
    )


def _admin_msg_received(m: dict) -> str:
    return (
        f"📦 Отримувач <b>{_point_label(m, 'to')}</b> "
        f"підтвердив отримання у переміщенні <b>{m['id']}</b>."
    )


def _admin_msg_closed(m: dict) -> str:
    handed_by = m.get("handed_by") or "—"
    received_by = m.get("received_by") or "—"
    return (
        "✅ <b>Успішно, переміщення підтвердили дві точки</b>\n"
        f"🆔 ID: {m['id']}\n"
        f"📤 Відправник: {_point_label(m, 'from')} ({handed_by})\n"
        f"📥 Отримувач: {_point_label(m, 'to')} ({received_by})"
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

    # тільки ТТ-відправник може натиснути "Віддав"
    if int(my_point) != int(m.get("from_point_id") or 0):
        return await cb.answer("⛔ Це не твоє переміщення (ти не відправник)", show_alert=True)

    mv_repo.mark_handed(move_id, cb.from_user.id)

    m = mv_repo.get_move(move_id)
    op_id = m.get("operator_id") or m.get("created_by")

    # 1) івент адміну/оператору
    if op_id:
        try:
            await cb.bot.send_message(op_id, _admin_msg_handed(m))
        except Exception:
            pass

    # 2) якщо обидві точки підтвердили — закриваємо і шлемо фінал
    if m.get("received_at"):
        mv_repo.set_status(move_id, "done")
        m2 = mv_repo.get_move(move_id)
        if op_id and m2:
            try:
                await cb.bot.send_message(op_id, _admin_msg_closed(m2))
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

    # тільки ТТ-отримувач може натиснути "Отримав"
    if int(my_point) != int(m.get("to_point_id") or 0):
        return await cb.answer("⛔ Це не твоє переміщення (ти не отримувач)", show_alert=True)

    mv_repo.mark_received(move_id, cb.from_user.id)

    m = mv_repo.get_move(move_id)
    op_id = m.get("operator_id") or m.get("created_by")

    # 1) івент адміну/оператору
    if op_id:
        try:
            await cb.bot.send_message(op_id, _admin_msg_received(m))
        except Exception:
            pass

    # 2) якщо обидві точки підтвердили — закриваємо і шлемо фінал
    if m.get("handed_at"):
        mv_repo.set_status(move_id, "done")
        m2 = mv_repo.get_move(move_id)
        if op_id and m2:
            try:
                await cb.bot.send_message(op_id, _admin_msg_closed(m2))
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

    # коригування може робити і відправник, і отримувач
    if int(my_point) not in {int(m.get("from_point_id") or 0), int(m.get("to_point_id") or 0)}:
        return await cb.answer("⛔ Це не твоє переміщення", show_alert=True)

    await state.update_data(move_id=move_id, point_id=int(my_point))
    await state.set_state(PointCorrectionStates.waiting_note)

    await cb.message.answer(
        f"⚠️ <b>Коригування по переміщенню #{move_id}</b>\n\n"
        "Напиши коментар (що не так: не вистачає / зайве / інший товар):"
    )
    await cb.answer()


@router.message(PointCorrectionStates.waiting_note)
async def pt_corr_note(message: Message, state: FSMContext):
    note = (message.text or "").strip()
    if not note:
        return await message.answer("Напиши текстом, що саме не так.")

    await state.update_data(note=note)
    await state.set_state(PointCorrectionStates.waiting_photo)
    await message.answer("Тепер надішли фото (або напиши <code>-</code> якщо без фото).")


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
        return await message.answer("Надішли фото або '-'.")

    mv_repo.request_correction(move_id, message.from_user.id, note, file_id)

    m = mv_repo.get_move(move_id)
    if not m:
        await state.clear()
        return await message.answer("❌ Переміщення не знайдено.")

    op_id = m.get("operator_id") or m.get("created_by")

    # визначимо назву точки, яка ініціює коригування
    point_name = "—"
    if point_id == int(m.get("from_point_id") or 0):
        point_name = _point_label(m, "from")
    elif point_id == int(m.get("to_point_id") or 0):
        point_name = _point_label(m, "to")

    text = _admin_msg_correction(m, point_name, message.from_user.id, note)

    if op_id:
        try:
            if file_id:
                await message.bot.send_photo(op_id, photo=file_id, caption=text)
            else:
                await message.bot.send_message(op_id, text)
        except Exception:
            pass

    await state.clear()
    await message.answer("✅ Коригування відправлено оператору. Очікуй оновлену накладну.")
