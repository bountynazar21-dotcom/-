# app/handlers/moves.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from ..db import locations_repo as loc_repo
from ..db import moves_repo as mv_repo
from ..db import auth_repo

from ..states.moves import MoveStates
from ..keyboards.moves import (
    moves_menu_kb,
    cities_kb,
    points_kb,
    move_review_kb,
    move_actions_kb,
    point_from_kb,
    point_to_kb,
    mv_photos_done_kb,
)
from ..utils.text import move_text

router = Router()

STATUS_UA = {
    "draft": "чернетка",
    "sent": "відправлено",
    "done": "завершено",
    "canceled": "скасовано",
}

TELEGRAM_LIMIT = 3900
PM = "HTML"


def split_text(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    parts: list[str] = []
    buf = ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > limit:
            if buf:
                parts.append(buf)
            buf = line
        else:
            buf = f"{buf}\n{line}" if buf else line
    if buf:
        parts.append(buf)
    return parts


async def safe_edit(message, text: str, reply_markup=None):
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=PM)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        raise


def _extract_photo_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id
    if message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        return message.document.file_id
    return None


async def _send_album_or_single(bot, uid: int, photos: list[str], caption: str, kb):
    """
    media_group не підтримує reply_markup, тому:
    - 1 фото: send_photo з kb
    - 2+: send_media_group + окреме повідомлення з kb (1 раз)
    """
    if not photos:
        return False

    try:
        if len(photos) == 1:
            await bot.send_photo(uid, photo=photos[0], caption=caption, reply_markup=kb, parse_mode=PM)
        else:
            media = [InputMediaPhoto(media=fid) for fid in photos]
            media[0].caption = caption
            media[0].parse_mode = PM
            await bot.send_media_group(uid, media=media)
            await bot.send_message(uid, "✅ Підтверди дію кнопками нижче:", reply_markup=kb, parse_mode=PM)
        return True
    except Exception:
        return False


@router.callback_query(F.data == "mv:menu")
async def mv_menu(cb: CallbackQuery, state: FSMContext):
    # щоб режим фото не зависав
    if await state.get_state() == MoveStates.waiting_photos:
        await state.clear()
    await safe_edit(cb.message, "📦 Меню переміщень:", reply_markup=moves_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "mv:list")
async def mv_list(cb: CallbackQuery):
    items = mv_repo.list_moves(50)
    if not items:
        await safe_edit(cb.message, "Поки переміщень нема.", reply_markup=moves_menu_kb())
        await cb.answer()
        return

    lines = ["📋 <b>Останні переміщення:</b>"]
    for m in items:
        fp = m.get("from_point_name") or "—"
        tp = m.get("to_point_name") or "—"
        st_raw = (m.get("status") or "").lower()
        st = STATUS_UA.get(st_raw, m.get("status") or "—")
        lines.append(f"• <b>#{m['id']}</b> ({st}) {fp} → {tp}")

    lines.append("\nКоманда: <code>/info ID</code>")
    chunks = split_text("\n".join(lines))

    await safe_edit(cb.message, chunks[0], reply_markup=moves_menu_kb())
    for extra in chunks[1:]:
        await cb.message.answer(extra, parse_mode=PM)

    await cb.answer()


# ---------- create new move flow ----------
@router.callback_query(F.data == "mv:new")
async def mv_new(cb: CallbackQuery, state: FSMContext):
    move_id = mv_repo.create_move(created_by=cb.from_user.id)
    try:
        mv_repo.set_operator(move_id, cb.from_user.id)
    except Exception:
        pass

    await state.update_data(move_id=move_id)

    cities = loc_repo.list_cities()
    if not cities:
        await safe_edit(cb.message, "Спочатку додай міста/ТТ у модулі локацій.")
        await cb.answer()
        return

    await state.set_state(MoveStates.choosing_from_city)
    await safe_edit(
        cb.message,
        f"🚚 Створив чернетку <b>#{move_id}</b>\n\nВибери <b>місто (ЗВІДКИ)</b>:",
        reply_markup=cities_kb(cities, "mv:from_city_", back_cb="mv:menu"),
    )
    await cb.answer()


@router.callback_query(MoveStates.choosing_from_city, F.data.startswith("mv:from_city_"))
async def mv_from_city(cb: CallbackQuery, state: FSMContext):
    city_id = int(cb.data.split("_")[-1])
    await state.update_data(from_city_id=city_id)

    points = loc_repo.list_points(city_id)
    if not points:
        await cb.answer("У місті немає ТТ.", show_alert=True)
        return

    await state.set_state(MoveStates.choosing_from_point)
    await safe_edit(
        cb.message,
        "Вибери <b>ТТ (ЗВІДКИ)</b>:",
        reply_markup=points_kb(points, "mv:from_point_", back_cb="mv:new"),
    )
    await cb.answer()


@router.callback_query(MoveStates.choosing_from_point, F.data.startswith("mv:from_point_"))
async def mv_from_point(cb: CallbackQuery, state: FSMContext):
    point_id = int(cb.data.split("_")[-1])
    move_id = int((await state.get_data())["move_id"])

    mv_repo.set_from_point(move_id, point_id)

    await state.set_state(MoveStates.choosing_to_city)
    await safe_edit(
        cb.message,
        "Тепер вибери <b>місто (КУДИ)</b>:",
        reply_markup=cities_kb(loc_repo.list_cities(), "mv:to_city_", back_cb="mv:menu"),
    )
    await cb.answer()


@router.callback_query(MoveStates.choosing_to_city, F.data.startswith("mv:to_city_"))
async def mv_to_city(cb: CallbackQuery, state: FSMContext):
    city_id = int(cb.data.split("_")[-1])
    await state.update_data(to_city_id=city_id)

    points = loc_repo.list_points(city_id)
    if not points:
        await cb.answer("У місті немає ТТ.", show_alert=True)
        return

    await state.set_state(MoveStates.choosing_to_point)
    await safe_edit(
        cb.message,
        "Вибери <b>ТТ (КУДИ)</b>:",
        reply_markup=points_kb(points, "mv:to_point_", back_cb="mv:menu"),
    )
    await cb.answer()


@router.callback_query(MoveStates.choosing_to_point, F.data.startswith("mv:to_point_"))
async def mv_to_point(cb: CallbackQuery, state: FSMContext):
    point_id = int(cb.data.split("_")[-1])
    move_id = int((await state.get_data())["move_id"])

    mv_repo.set_to_point(move_id, point_id)

    m = mv_repo.get_move(move_id)
    await state.clear()
    await safe_edit(
        cb.message,
        "✅ Маршрут зібраний.\n\n" + move_text(m),
        reply_markup=move_review_kb(move_id),
    )
    await cb.answer()


# ---------- add photo(s) ----------
@router.callback_query(F.data.startswith("mv:photo_"))
async def mv_photo_start(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])

    await state.update_data(move_id=move_id, media_groups_seen=[])
    await state.set_state(MoveStates.waiting_photos)

    v = mv_repo.get_invoice_version(move_id)
    text = (
        f"📷 <b>Накладна для #{move_id}</b> (V{v})\n\n"
        "Надсилай фото накладної (1…10 фото, по одному або альбомом).\n"
        "Коли завершиш — натисни ✅ <b>Готово</b>.\n\n"
        "Якщо передумав — натисни ❌ <b>Скасувати</b>."
    )
    await safe_edit(cb.message, text, reply_markup=mv_photos_done_kb(move_id))
    await cb.answer()


@router.callback_query(F.data.startswith("mv:photo_cancel_"))
@router.callback_query(F.data.startswith("mv:photos_cancel_"))
async def mv_photo_cancel(cb: CallbackQuery, state: FSMContext):
    move_id = int((await state.get_data()).get("move_id") or cb.data.split("_")[-1])
    await state.clear()

    m = mv_repo.get_move(move_id)
    await cb.message.answer("❌ Ок, додавання фото скасовано.", parse_mode=PM)
    if m:
        await cb.message.answer(move_text(m), reply_markup=move_review_kb(move_id), parse_mode=PM)
    await cb.answer()


@router.message(MoveStates.waiting_photos)
async def mv_photo_collect(message: Message, state: FSMContext):
    """
    Головний фікс: НЕ тримаємо список фото лише в state (бо альбоми можуть “змагатись” по апдейтах).
    Джерело правди = БД:
    - беремо поточний список фото з БД для цієї версії
    - додаємо нове
    - перезаписуємо (move_invoice_photos) одним махом
    """
    file_id = _extract_photo_file_id(message)
    if not file_id:
        return await message.answer("⚠️ Надішли саме фото/картинку. Потім натисни ✅ Готово.", parse_mode=PM)

    data = await state.get_data()
    move_id = int(data.get("move_id") or 0)
    if not move_id:
        await state.clear()
        return await message.answer("⚠️ Не знайшов move_id. Зайди ще раз в 📷 Додати фото.", parse_mode=PM)

    v = mv_repo.get_invoice_version(move_id)

    # беремо вже збережені фото (щоб альбом/окремі не губились)
    try:
        current = mv_repo.list_invoice_photos(move_id, v)
    except Exception:
        current = []

    if file_id not in current:
        current.append(file_id)

    # обмеження 10 фото
    if len(current) > 10:
        return await message.answer("⚠️ Максимум 10 фото для 1 накладної.", parse_mode=PM)

    # пишемо в БД одразу
    try:
        mv_repo.set_photo(move_id, current[0])          # превʼю
        mv_repo.add_invoice_photos(move_id, v, current) # всі фото
    except Exception:
        pass

    media_groups_seen: list[str] = data.get("media_groups_seen", [])

    if message.media_group_id:
        mg = str(message.media_group_id)
        # відповідаємо 1 раз на весь альбом
        if mg not in media_groups_seen:
            media_groups_seen.append(mg)
            await state.update_data(media_groups_seen=media_groups_seen)
            return await message.answer(
                "📎 Альбом прийнято ✅\n"
                f"Фото в накладній: <b>{len(current)}</b>\n"
                "Можеш додати ще або натиснути ✅ <b>Готово</b>.",
                parse_mode=PM,
            )
        return

    await message.answer(
        f"✅ Додано фото: <b>{len(current)}</b>\n"
        "Можеш додати ще або натиснути ✅ <b>Готово</b>.",
        parse_mode=PM,
    )


@router.callback_query(F.data.startswith("mv:photo_done_"))
@router.callback_query(F.data.startswith("mv:photos_done_"))
async def mv_photo_done(cb: CallbackQuery, state: FSMContext):
    move_id = int((await state.get_data()).get("move_id") or cb.data.split("_")[-1])
    v = mv_repo.get_invoice_version(move_id)

    try:
        photos = mv_repo.list_invoice_photos(move_id, v)
    except Exception:
        photos = []

    if not photos:
        await cb.answer("Спочатку додай хоча б 1 фото.", show_alert=True)
        return

    await state.clear()
    m = mv_repo.get_move(move_id)

    await cb.message.answer(
        f"✅ Накладну збережено: <b>{len(photos)}</b> фото (V{v})\n\n" + move_text(m),
        reply_markup=move_review_kb(move_id),
        parse_mode=PM,
    )
    await cb.answer("Готово ✅", show_alert=True)


# ---------- send / cancel / done ----------
@router.callback_query(F.data.startswith("mv:send_"))
async def mv_send(cb: CallbackQuery):
    move_id = int(cb.data.split("_")[-1])
    m = mv_repo.get_move(move_id)
    if not m:
        await cb.answer("Не знайдено.", show_alert=True)
        return

    if not m.get("from_point_id") or not m.get("to_point_id"):
        await cb.answer("Немає маршруту (from/to).", show_alert=True)
        return

    # 🔥 критично: перед кожною відправкою НОВОЇ накладної
    # обнуляємо підтвердження, щоб не було “вже підтверджено”
    try:
        mv_repo.clear_hand_receive(move_id)
    except Exception:
        pass

    from_users = auth_repo.get_point_users(int(m["from_point_id"]))
    to_users = auth_repo.get_point_users(int(m["to_point_id"]))

    from_rec = [u["telegram_id"] for u in from_users if u.get("telegram_id")]
    to_rec = [u["telegram_id"] for u in to_users if u.get("telegram_id")]

    if not from_rec or not to_rec:
        await cb.answer(
            "⚠️ Не всі ТТ мають прив’язаних людей.\n"
            "Нехай продавці оберуть ТТ в боті, а адмін підтвердить.",
            show_alert=True
        )
        return

    # беремо фото поточної версії
    v = int((m.get("invoice_version") or 1))
    try:
        photos = mv_repo.list_invoice_photos(move_id, v)
    except Exception:
        photos = []

    if not photos and m.get("photo_file_id"):
        photos = [m["photo_file_id"]]

    if not photos:
        await cb.answer("⚠️ Нема фото накладної. Додай фото перед відправкою.", show_alert=True)
        return

    mv_repo.set_status(move_id, "sent")
    m = mv_repo.get_move(move_id) or m

    caption = f"📣 <b>Переміщення #{move_id}</b> (V{v})\n\n" + move_text(m)

    sent_from = 0
    sent_to = 0

    for uid in from_rec:
        if await _send_album_or_single(cb.bot, uid, photos, caption, point_from_kb(move_id)):
            sent_from += 1

    for uid in to_rec:
        if await _send_album_or_single(cb.bot, uid, photos, caption, point_to_kb(move_id)):
            sent_to += 1

    operator_id = m.get("operator_id") or cb.from_user.id
    try:
        await cb.bot.send_message(
            operator_id,
            f"✅ Відправлено на ТТ.\n"
            f"Відправник отримали: <b>{sent_from}</b>\n"
            f"Отримувач отримали: <b>{sent_to}</b>\n\n"
            + move_text(m),
            parse_mode=PM,
        )
    except Exception:
        pass

    await safe_edit(
        cb.message,
        f"✅ Відправлено.\n"
        f"Відправник: <b>{sent_from}</b> отримувачів\n"
        f"Отримувач: <b>{sent_to}</b> отримувачів\n\n"
        + move_text(m),
        reply_markup=move_actions_kb(move_id),
    )
    await cb.answer("Sent ✅", show_alert=True)


@router.callback_query(F.data.startswith("mv:cancel_"))
async def mv_cancel(cb: CallbackQuery):
    move_id = int(cb.data.split("_")[-1])
    ok = mv_repo.set_status(move_id, "canceled")
    await cb.answer("🗑 Скасовано" if ok else "⚠️ Не знайдено", show_alert=True)
    m = mv_repo.get_move(move_id)
    if m:
        await safe_edit(cb.message, move_text(m), reply_markup=moves_menu_kb())


@router.callback_query(F.data.startswith("mv:done_"))
async def mv_done(cb: CallbackQuery):
    move_id = int(cb.data.split("_")[-1])
    ok = mv_repo.set_status(move_id, "done")
    await cb.answer("✅ Завершено" if ok else "⚠️ Не знайдено", show_alert=True)
    m = mv_repo.get_move(move_id)
    if m:
        await safe_edit(cb.message, move_text(m), reply_markup=moves_menu_kb())


# ---------- commands ----------
@router.message(Command("moves"))
async def cmd_moves(message: Message):
    items = mv_repo.list_moves(50)
    if not items:
        return await message.answer("Поки переміщень нема.", parse_mode=PM)

    lines = ["📋 <b>Останні переміщення:</b>"]
    for m in items:
        fp = m.get("from_point_name") or "—"
        tp = m.get("to_point_name") or "—"
        st_raw = (m.get("status") or "").lower()
        st = STATUS_UA.get(st_raw, m.get("status") or "—")
        lines.append(f"• <b>#{m['id']}</b> ({st}) {fp} → {tp}")

    lines.append("\nДетально: <code>/info ID</code>")
    for chunk in split_text("\n".join(lines)):
        await message.answer(chunk, parse_mode=PM)


@router.message(Command("info"))
async def cmd_info(message: Message):
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Формат: <code>/info 123</code>", parse_mode=PM)
    move_id = int(parts[1])
    m = mv_repo.get_move(move_id)
    if not m:
        return await message.answer("Не знайдено.", parse_mode=PM)
    await message.answer(move_text(m), parse_mode=PM)
