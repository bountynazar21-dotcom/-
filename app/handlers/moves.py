# app/handlers/moves.py
import logging
import traceback

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)

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
    mv_pdf_done_kb,
)
from ..utils.text import move_text

router = Router()
log = logging.getLogger(__name__)

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


def _extract_pdf_file_id(message: Message) -> str | None:
    if not message.document:
        return None
    mt = message.document.mime_type or ""
    fn = (message.document.file_name or "").lower()
    if mt == "application/pdf" or fn.endswith(".pdf"):
        return message.document.file_id
    return None


async def _send_invoice_package(bot, uid: int, photos: list[str], pdf_file_id: str | None, caption: str, kb):
    """
    Відправляє вкладення (фото альбомом і/або pdf) + 1 повідомлення з кнопками.
    Додаємо детальні логи, щоб зрозуміти чому "не надсилається".
    """
    try:
        sent_any = False

        log.info("SEND pkg uid=%s photos=%s pdf=%s", uid, len(photos), bool(pdf_file_id))

        if photos:
            if len(photos) == 1:
                await bot.send_photo(uid, photo=photos[0], caption=caption, parse_mode=PM)
            else:
                media = [InputMediaPhoto(media=fid) for fid in photos]
                media[0].caption = caption
                media[0].parse_mode = PM
                await bot.send_media_group(uid, media=media)
            sent_any = True

        if pdf_file_id:
            if not photos:
                await bot.send_document(uid, document=pdf_file_id, caption=caption, parse_mode=PM)
            else:
                await bot.send_document(uid, document=pdf_file_id, caption="📄 PDF накладної", parse_mode=PM)
            sent_any = True

        if not sent_any:
            log.warning("SEND pkg uid=%s: nothing to send (no photos, no pdf)", uid)
            return False

        await bot.send_message(uid, "✅ Підтверди дію кнопками нижче:", reply_markup=kb, parse_mode=PM)
        return True

    except TelegramRetryAfter as e:
        log.error("SEND FAIL uid=%s flood_wait=%s", uid, getattr(e, "retry_after", None))
        return False
    except TelegramForbiddenError as e:
        log.error("SEND FAIL uid=%s forbidden: %s", uid, str(e))
        return False
    except TelegramBadRequest as e:
        # тут найчастіше: wrong file_id, chat not found, can't parse entities, etc.
        log.error("SEND FAIL uid=%s bad_request: %s", uid, str(e))
        return False
    except Exception as e:
        log.error("SEND FAIL uid=%s unknown: %s\n%s", uid, str(e), traceback.format_exc())
        return False


async def _send_invoice_to_operator(message: Message, move_id: int, m: dict):
    """
    Для звітності/перегляду: текст + вкладення (фото і/або pdf).
    """
    text = move_text(m)
    for chunk in split_text(text):
        await message.answer(chunk, parse_mode=PM)

    v = int(m.get("invoice_version") or 1)
    try:
        photos = mv_repo.list_invoice_photos(move_id, v)
    except Exception:
        photos = []

    if not photos and m.get("photo_file_id"):
        photos = [m["photo_file_id"]]

    if photos:
        try:
            if len(photos) == 1:
                await message.answer_photo(photos[0], caption=f"📷 Накладна (V{v})", parse_mode=PM)
            else:
                media = [InputMediaPhoto(media=fid) for fid in photos]
                media[0].caption = f"📷 Накладна (V{v})"
                media[0].parse_mode = PM
                await message.bot.send_media_group(message.chat.id, media=media)
        except Exception:
            log.exception("Failed to show invoice photos in /info for move_id=%s", move_id)

    pdf_id = m.get("invoice_pdf_file_id")
    if pdf_id:
        try:
            await message.answer_document(pdf_id, caption="📄 PDF накладної", parse_mode=PM)
        except Exception:
            log.exception("Failed to show invoice pdf in /info for move_id=%s", move_id)


@router.callback_query(F.data == "mv:menu")
async def mv_menu(cb: CallbackQuery, state: FSMContext):
    st = await state.get_state()
    if st in {MoveStates.waiting_photos, MoveStates.waiting_pdf}:
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
        log.exception("set_operator failed for move_id=%s", move_id)

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
    file_id = _extract_photo_file_id(message)
    if not file_id:
        return await message.answer("⚠️ Надішли саме фото/картинку. Потім натисни ✅ Готово.", parse_mode=PM)

    data = await state.get_data()
    move_id = int(data.get("move_id") or 0)
    if not move_id:
        await state.clear()
        return await message.answer("⚠️ Не знайшов move_id. Зайди ще раз в 📷 Додати фото.", parse_mode=PM)

    v = mv_repo.get_invoice_version(move_id)

    try:
        current = mv_repo.list_invoice_photos(move_id, v)
    except Exception:
        current = []

    if file_id not in current:
        current.append(file_id)

    if len(current) > 10:
        return await message.answer("⚠️ Максимум 10 фото для 1 накладної.", parse_mode=PM)

    try:
        mv_repo.set_photo(move_id, current[0])
        mv_repo.add_invoice_photos(move_id, v, current)
    except Exception:
        log.exception("Failed to save invoice photos for move_id=%s v=%s", move_id, v)

    media_groups_seen: list[str] = data.get("media_groups_seen", [])

    if message.media_group_id:
        mg = str(message.media_group_id)
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
        f"✅ Фото накладної збережено: <b>{len(photos)}</b> фото (V{v})\n\n" + move_text(m),
        reply_markup=move_review_kb(move_id),
        parse_mode=PM,
    )
    await cb.answer("Готово ✅", show_alert=True)


# ---------- add PDF (independent) ----------
@router.callback_query(F.data.startswith("mv:pdf_"))
async def mv_pdf_start(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])

    await state.update_data(move_id=move_id, pdf_file_id=None)
    await state.set_state(MoveStates.waiting_pdf)

    text = (
        f"📄 <b>PDF накладної для #{move_id}</b>\n\n"
        "Надішли PDF файлом. Я його прийму, а потім натисни ✅ <b>Зберегти PDF</b>.\n"
        "Або натисни 🗑 <b>Прибрати PDF</b>, якщо треба очистити.\n"
        "Скасувати — ❌."
    )

    await safe_edit(cb.message, text, reply_markup=mv_pdf_done_kb(move_id))
    await cb.answer()


@router.message(MoveStates.waiting_pdf)
async def mv_pdf_collect(message: Message, state: FSMContext):
    # Лог корисний: інколи прилітає не pdf, а інший mime
    try:
        log.info(
            "PDF incoming: has_doc=%s mime=%s name=%s",
            bool(message.document),
            getattr(message.document, "mime_type", None),
            getattr(message.document, "file_name", None),
        )
    except Exception:
        pass

    pdf_id = _extract_pdf_file_id(message)
    if not pdf_id:
        return await message.answer("⚠️ Надішли саме PDF файлом (.pdf).", parse_mode=PM)

    await state.update_data(pdf_file_id=pdf_id)
    await message.answer("✅ PDF отримано. Натисни <b>Зберегти PDF</b>.", parse_mode=PM)


@router.callback_query(F.data.startswith("mv:pdf_done_"))
async def mv_pdf_done(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])
    data = await state.get_data()
    pdf_id = data.get("pdf_file_id")

    if not pdf_id:
        await cb.answer("Спочатку надішли PDF файлом.", show_alert=True)
        return

    try:
        mv_repo.set_invoice_pdf(move_id, pdf_id)
    except Exception:
        log.exception("Failed to save invoice pdf for move_id=%s", move_id)
        await cb.answer("❌ Не вдалося зберегти PDF. Дивись логи.", show_alert=True)
        return

    await state.clear()
    m = mv_repo.get_move(move_id)

    await cb.message.answer(
        "✅ PDF накладної збережено.\n\n" + move_text(m),
        reply_markup=move_review_kb(move_id),
        parse_mode=PM,
    )
    await cb.answer("Збережено ✅", show_alert=True)


@router.callback_query(F.data.startswith("mv:pdf_clear_"))
async def mv_pdf_clear(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])

    try:
        mv_repo.set_invoice_pdf(move_id, None)
    except Exception:
        log.exception("Failed to clear invoice pdf for move_id=%s", move_id)
        await cb.answer("❌ Не вдалося прибрати PDF. Дивись логи.", show_alert=True)
        return

    await state.clear()
    m = mv_repo.get_move(move_id)

    await cb.message.answer(
        "🗑 PDF прибрано.\n\n" + move_text(m),
        reply_markup=move_review_kb(move_id),
        parse_mode=PM,
    )
    await cb.answer("Прибрано ✅", show_alert=True)


@router.callback_query(F.data.startswith("mv:pdf_cancel_"))
async def mv_pdf_cancel(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])
    await state.clear()

    m = mv_repo.get_move(move_id)
    await cb.message.answer("❌ Ок, додавання PDF скасовано.", parse_mode=PM)
    if m:
        await cb.message.answer(move_text(m), reply_markup=move_review_kb(move_id), parse_mode=PM)
    await cb.answer()


@router.callback_query(F.data.startswith("mv:note_"))
async def mv_note_start(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])
    await state.update_data(move_id=move_id)
    await state.set_state(MoveStates.waiting_note)

    await cb.message.answer(
        f"📝 <b>Коментар для переміщення #{move_id}</b>\n\n"
        "Напиши текстом коментар.\n"
        "Щоб прибрати коментар — надішли <code>-</code>.",
        parse_mode=PM,
    )
    await cb.answer()


@router.message(MoveStates.waiting_note)
async def mv_note_collect(message: Message, state: FSMContext):
    data = await state.get_data()
    move_id = int(data.get("move_id") or 0)
    if not move_id:
        await state.clear()
        return await message.answer("⚠️ Не знайшов move_id. Натисни ще раз 📝 Коментар.", parse_mode=PM)

    text = (message.text or "").strip()
    if not text:
        return await message.answer("Напиши текстом або <code>-</code> щоб прибрати.", parse_mode=PM)

    if text == "-":
        mv_repo.set_note(move_id, "")
        await state.clear()
        m = mv_repo.get_move(move_id)
        return await message.answer(
            "🗑 Коментар прибрано.\n\n" + move_text(m),
            reply_markup=move_review_kb(move_id),
            parse_mode=PM,
        )

    mv_repo.set_note(move_id, text)
    await state.clear()
    m = mv_repo.get_move(move_id)
    await message.answer(
        "✅ Коментар збережено.\n\n" + move_text(m),
        reply_markup=move_review_kb(move_id),
        parse_mode=PM,
    )


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

    try:
        mv_repo.clear_hand_receive(move_id)
    except Exception:
        log.exception("clear_hand_receive failed for move_id=%s", move_id)

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

    v = int((m.get("invoice_version") or 1))
    try:
        photos = mv_repo.list_invoice_photos(move_id, v)
    except Exception:
        photos = []

    if not photos and m.get("photo_file_id"):
        photos = [m["photo_file_id"]]

    pdf_id = m.get("invoice_pdf_file_id")

    log.info(
        "MOVE SEND move_id=%s from_rec=%s to_rec=%s v=%s photos=%s pdf=%s",
        move_id, from_rec, to_rec, v, len(photos), bool(pdf_id)
    )

    if not photos and not pdf_id:
        await cb.answer("⚠️ Нема ні фото, ні PDF накладної. Додай перед відправкою.", show_alert=True)
        return

    mv_repo.set_status(move_id, "sent")
    m = mv_repo.get_move(move_id) or m

    caption = f"📣 <b>Переміщення #{move_id}</b> (V{v})\n\n" + move_text(m)

    sent_from = 0
    sent_to = 0

    for uid in from_rec:
        ok = await _send_invoice_package(cb.bot, uid, photos, pdf_id, caption, point_from_kb(move_id))
        if ok:
            sent_from += 1
        else:
            log.error("SEND FAIL to FROM uid=%s move_id=%s", uid, move_id)

    for uid in to_rec:
        ok = await _send_invoice_package(cb.bot, uid, photos, pdf_id, caption, point_to_kb(move_id))
        if ok:
            sent_to += 1
        else:
            log.error("SEND FAIL to TO uid=%s move_id=%s", uid, move_id)

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
        log.exception("Failed to notify operator after send move_id=%s", move_id)

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

    await _send_invoice_to_operator(message, move_id, m)