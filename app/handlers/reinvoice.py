from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from ..db import moves_repo as mv_repo
from ..db import auth_repo
from ..states.reinvoice import ReinvoiceStates
from ..keyboards.moves import point_from_kb, point_to_kb
from ..utils.text import move_text

router = Router()

TELEGRAM_LIMIT = 3900

@router.message(Command("reinvoice"))
async def reinvoice_start(message: Message, state: FSMContext):
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Формат: <code>/reinvoice 123</code>")

    move_id = int(parts[1])
    m = mv_repo.get_move(move_id)
    if not m:
        return await message.answer("❌ Переміщення не знайдено.")

    await state.update_data(move_id=move_id)
    await state.set_state(ReinvoiceStates.waiting_photo)

    await message.answer(
        f"🆕 <b>Нова накладна для переміщення #{move_id}</b>\n"
        f"Надішли фото накладної одним повідомленням."
    )

@router.message(ReinvoiceStates.waiting_photo)
async def reinvoice_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    move_id = int(data["move_id"])

    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id

    if not file_id:
        return await message.answer("⚠️ Надішли саме фото/картинку (або image document).")

    m = mv_repo.get_move(move_id)
    if not m:
        await state.clear()
        return await message.answer("❌ Переміщення не знайдено.")

    # 1) bump version
    mv_repo.bump_invoice_version(move_id)
    # 2) set new invoice photo
    mv_repo.set_invoice_photo(move_id, file_id)
    # 3) reset confirmations + resolve correction + status sent
    mv_repo.reset_for_reinvoice(move_id)

    m = mv_repo.get_move(move_id) or m
    version = m.get("invoice_version") or 1

    text = f"🆕 <b>Оновлена накладна</b> для переміщення <b>#{move_id}</b> (V{version})\n\n" + move_text(m)

    # recipients: from + to
    from_pid = m.get("from_point_id")
    to_pid = m.get("to_point_id")
    if not from_pid or not to_pid:
        await state.clear()
        return await message.answer("⚠️ У переміщенні немає from/to. Перевір маршрут.")

    from_users = auth_repo.get_point_users(int(from_pid))
    to_users = auth_repo.get_point_users(int(to_pid))
    from_rec = [u["telegram_id"] for u in from_users if u.get("telegram_id")]
    to_rec = [u["telegram_id"] for u in to_users if u.get("telegram_id")]

    if not from_rec or not to_rec:
        await state.clear()
        return await message.answer("⚠️ Не всі ТТ мають прив’язаних людей. Нехай продавці залогіняться.")

    sent_from = 0
    sent_to = 0

    # send to FROM
    for uid in from_rec:
        try:
            await message.bot.send_photo(uid, photo=file_id, caption=text, reply_markup=point_from_kb(move_id))
            sent_from += 1
        except Exception:
            pass

    # send to TO
    for uid in to_rec:
        try:
            await message.bot.send_photo(uid, photo=file_id, caption=text, reply_markup=point_to_kb(move_id))
            sent_to += 1
        except Exception:
            pass

    await state.clear()

    await message.answer(
        f"✅ Оновлено накладну для <b>#{move_id}</b> (V{version}).\n"
        f"📤 Відправник отримали: <b>{sent_from}</b>\n"
        f"📥 Отримувач отримали: <b>{sent_to}</b>\n\n"
        "Тепер ТТ мають повторно натиснути: <b>Віддав</b> / <b>Отримав</b>."
    )
