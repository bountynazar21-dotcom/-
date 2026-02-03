from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..db import moves_repo as mv_repo
from ..db import auth_repo
from ..states.reinvoice import ReinvoiceStates
from ..keyboards.moves import (
    point_from_kb,
    point_to_kb,
    reinvoice_done_kb,
)
from ..utils.text import move_text

router = Router()


# ---------- helpers ----------
async def _send_album(bot, uid: int, photos: list[str], caption: str, kb):
    if not photos:
        return False

    try:
        if len(photos) == 1:
            await bot.send_photo(uid, photo=photos[0], caption=caption, reply_markup=kb)
        else:
            media = [InputMediaPhoto(media=fid) for fid in photos]
            media[0].caption = caption
            media[0].parse_mode = "HTML"
            await bot.send_media_group(uid, media)
            await bot.send_message(uid, "⬇️ Підтверди дію:", reply_markup=kb)
        return True
    except Exception:
        return False


async def _send_to_points(bot, move: dict, photos: list[str], move_id: int):
    from_users = auth_repo.get_point_users(int(move["from_point_id"]))
    to_users = auth_repo.get_point_users(int(move["to_point_id"]))

    from_ids = [u["telegram_id"] for u in from_users if u.get("telegram_id")]
    to_ids = [u["telegram_id"] for u in to_users if u.get("telegram_id")]

    v = move.get("invoice_version") or 1
    caption = f"📦 <b>Переміщення #{move_id}</b> (V{v})\n\n" + move_text(move)

    sf = st = 0
    for uid in from_ids:
        if await _send_album(bot, uid, photos, caption, point_from_kb(move_id)):
            sf += 1

    for uid in to_ids:
        if await _send_album(bot, uid, photos, caption, point_to_kb(move_id)):
            st += 1

    return sf, st


# ---------- start ----------
@router.callback_query(F.data.startswith("mva:reinvoice_"))
async def reinvoice_start(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])
    if not mv_repo.get_move(move_id):
        return await cb.answer("Не знайдено", show_alert=True)

    await state.update_data(move_id=move_id, photos=[])
    await state.set_state(ReinvoiceStates.waiting_photos)

    await cb.message.answer(
        f"📷 <b>Нова накладна для #{move_id}</b>\n"
        "Надішли ОДНЕ або КІЛЬКА фото (можна альбомом).\n"
        "Потім натисни ✅ Готово.",
        reply_markup=reinvoice_done_kb(move_id),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("mva:reinvoice_cancel_"))
async def reinvoice_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.answer("❌ Оновлення скасовано.")
    await cb.answer()


# ---------- collect photos ----------
@router.message(ReinvoiceStates.waiting_photos)
async def collect_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id

    if not file_id:
        return

    photos.append(file_id)
    await state.update_data(photos=photos)

    # ⚠️ якщо це альбом — мовчимо
    if message.media_group_id:
        return

    await message.answer(
        f"✅ Додано фото: <b>{len(photos)}</b>\n"
        "Можеш додати ще або натиснути ✅ Готово"
    )


# ---------- done ----------
@router.callback_query(F.data.startswith("mva:reinvoice_done_"))
async def reinvoice_done(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])
    data = await state.get_data()
    photos = data.get("photos", [])

    if not photos:
        return await cb.answer("Немає фото", show_alert=True)

    mv_repo.bump_invoice_version(move_id)
    mv_repo.set_invoice_photo(move_id, photos[0])
    mv_repo.reset_for_reinvoice(move_id)

    move = mv_repo.get_move(move_id)
    sent_from, sent_to = await _send_to_points(cb.bot, move, photos, move_id)

    await state.clear()

    await cb.message.answer(
        f"✅ Накладну оновлено\n"
        f"📤 Відправник: {sent_from}\n"
        f"📥 Отримувач: {sent_to}"
    )
    await cb.answer("Готово ✅", show_alert=True)

