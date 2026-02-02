from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from ..db import moves_repo as mv_repo
from ..db import auth_repo
from ..states.reinvoice import ReinvoiceStates
from ..keyboards.moves import point_from_kb, point_to_kb, reinvoice_done_kb
from ..utils.text import move_text

router = Router()


async def _send_invoice_album(bot, uid: int, photos: list[str], caption: str, kb):
    """
    Надсилає 1 фото або альбом. Якщо альбом — caption тільки на першому елементі.
    Після альбому окремо шлемо повідомлення з кнопками (бо media_group не тримає markup).
    """
    if not photos:
        return False

    try:
        if len(photos) == 1:
            await bot.send_photo(uid, photo=photos[0], caption=caption, reply_markup=kb)
        else:
            media = [InputMediaPhoto(media=fid) for fid in photos]
            media[0].caption = caption
            media[0].parse_mode = "HTML"
            await bot.send_media_group(uid, media=media)
            await bot.send_message(uid, "✅ Підтверди дію кнопками нижче:", reply_markup=kb)
        return True
    except Exception:
        return False


async def _send_to_both_points(bot, move: dict, photos: list[str], move_id: int) -> tuple[int, int]:
    from_pid = move.get("from_point_id")
    to_pid = move.get("to_point_id")
    if not from_pid or not to_pid:
        return 0, 0

    from_users = auth_repo.get_point_users(int(from_pid))
    to_users = auth_repo.get_point_users(int(to_pid))

    from_rec = [u["telegram_id"] for u in from_users if u.get("telegram_id")]
    to_rec = [u["telegram_id"] for u in to_users if u.get("telegram_id")]

    v = move.get("invoice_version") or 1
    caption = f"🆕 <b>Оновлена накладна</b> для переміщення <b>#{move_id}</b> (V{v})\n\n" + move_text(move)

    sent_from = 0
    sent_to = 0

    for uid in from_rec:
        ok = await _send_invoice_album(bot, uid, photos, caption, point_from_kb(move_id))
        if ok:
            sent_from += 1

    for uid in to_rec:
        ok = await _send_invoice_album(bot, uid, photos, caption, point_to_kb(move_id))
        if ok:
            sent_to += 1

    return sent_from, sent_to


async def _start_reinvoice_flow(target: Message | CallbackQuery, state: FSMContext, move_id: int):
    await state.update_data(move_id=move_id, photos=[])
    await state.set_state(ReinvoiceStates.waiting_photos)

    text = (
        f"↪️ <b>Нова накладна для переміщення #{move_id}</b>\n"
        "Надішли ОДНЕ або КІЛЬКА фото (можна альбомом).\n"
        "Коли все — натисни ✅ <b>Готово</b>."
    )

    if isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=reinvoice_done_kb(move_id))
    else:
        await target.answer(text, reply_markup=reinvoice_done_kb(move_id))


# ✅ ВАЖЛИВО: цей хендлер НЕ ловить done/cancel
@router.callback_query(
    F.data.startswith("mva:reinvoice_")
    & ~F.data.startswith("mva:reinvoice_done_")
    & ~F.data.startswith("mva:reinvoice_cancel_")
)
async def reinvoice_from_button(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])
    m = mv_repo.get_move(move_id)
    if not m:
        await cb.answer("Не знайдено.", show_alert=True)
        return

    await _start_reinvoice_flow(cb, state, move_id)
    await cb.answer()


@router.message(Command("reinvoice"))
async def reinvoice_cmd(message: Message, state: FSMContext):
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Формат: <code>/reinvoice 123</code>")

    move_id = int(parts[1])
    m = mv_repo.get_move(move_id)
    if not m:
        return await message.answer("❌ Переміщення не знайдено.")

    await _start_reinvoice_flow(message, state, move_id)


@router.callback_query(F.data.startswith("mva:reinvoice_cancel_"))
async def reinvoice_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer("Скасовано", show_alert=True)
    await cb.message.answer("❌ Оновлення накладної скасовано.")


@router.message(ReinvoiceStates.waiting_photos)
async def reinvoice_collect_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos: list[str] = data.get("photos", [])

    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id

    if not file_id:
        return await message.answer("⚠️ Надішли фото (або альбом). Потім натисни ✅ Готово.")

    photos.append(file_id)
    await state.update_data(photos=photos)

    await message.answer(f"✅ Додано фото: <b>{len(photos)}</b>\nНатисни ✅ Готово коли завершиш.")


@router.callback_query(F.data.startswith("mva:reinvoice_done_"))
async def reinvoice_done(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])
    data = await state.get_data()
    photos: list[str] = data.get("photos", [])

    if not photos:
        await cb.answer("Спочатку надішли хоча б 1 фото.", show_alert=True)
        return

    m = mv_repo.get_move(move_id)
    if not m:
        await state.clear()
        await cb.answer("Не знайдено.", show_alert=True)
        return

    # 1) bump version
    mv_repo.bump_invoice_version(move_id)

    # 2) оновлюємо поточний photo_file_id (можна перше фото)
    mv_repo.set_invoice_photo(move_id, photos[0])

    # 3) reset confirmations + resolve correction + status sent
    mv_repo.reset_for_reinvoice(move_id)

    m = mv_repo.get_move(move_id) or m
    version = m.get("invoice_version") or 1

    # 4) зберігаємо всі фото цієї версії (multi-photo)
    #    (має бути реалізовано в moves_repo: add_invoice_photos)
    try:
        mv_repo.add_invoice_photos(move_id, version, photos)
    except Exception:
        pass

    sent_from, sent_to = await _send_to_both_points(cb.bot, m, photos, move_id)

    await state.clear()
    await cb.message.answer(
        f"✅ Оновлену накладну (V{version}) відправлено.\n"
        f"📤 Відправник отримали: <b>{sent_from}</b>\n"
        f"📥 Отримувач отримали: <b>{sent_to}</b>\n\n"
        "ТТ мають повторно підтвердити: <b>Віддав</b> / <b>Отримав</b>."
    )
    await cb.answer("Готово ✅", show_alert=True)
