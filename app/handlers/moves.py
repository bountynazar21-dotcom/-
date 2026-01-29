from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

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
)
from ..utils.text import move_text

router = Router()

# ---------- helpers: UA statuses + telegram-safe splitting ----------
STATUS_UA = {
    "draft": "чернетка",
    "sent": "відправлено",
    "done": "завершено",
    "canceled": "скасовано",
}

TELEGRAM_LIMIT = 3900  # запас під HTML

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


@router.callback_query(F.data == "mv:menu")
async def mv_menu(cb: CallbackQuery):
    await cb.message.edit_text("📦 Меню переміщень:", reply_markup=moves_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "mv:list")
async def mv_list(cb: CallbackQuery):
    items = mv_repo.list_moves(50)
    if not items:
        await cb.message.edit_text("Поки переміщень нема.", reply_markup=moves_menu_kb())
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

    text = "\n".join(lines)
    chunks = split_text(text)

    # перший шматок редагуємо, решту — новими повідомленнями
    await cb.message.edit_text(chunks[0], reply_markup=moves_menu_kb())
    for extra in chunks[1:]:
        await cb.message.answer(extra)

    await cb.answer()


# ---------- create new move flow ----------
@router.callback_query(F.data == "mv:new")
async def mv_new(cb: CallbackQuery, state: FSMContext):
    move_id = mv_repo.create_move(created_by=cb.from_user.id)

    # оператор = хто створив переміщення
    try:
        mv_repo.set_operator(move_id, cb.from_user.id)
    except Exception:
        pass

    await state.update_data(move_id=move_id)

    cities = loc_repo.list_cities()
    if not cities:
        await cb.message.edit_text("Спочатку додай міста/ТТ у модулі локацій.")
        await cb.answer()
        return

    await state.set_state(MoveStates.choosing_from_city)
    await cb.message.edit_text(
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
    await cb.message.edit_text(
        "Вибери <b>ТТ (ЗВІДКИ)</b>:",
        reply_markup=points_kb(points, "mv:from_point_", back_cb="mv:new"),
    )
    await cb.answer()


@router.callback_query(MoveStates.choosing_from_point, F.data.startswith("mv:from_point_"))
async def mv_from_point(cb: CallbackQuery, state: FSMContext):
    point_id = int(cb.data.split("_")[-1])
    data = await state.get_data()
    move_id = int(data["move_id"])

    mv_repo.set_from_point(move_id, point_id)

    cities = loc_repo.list_cities()
    await state.set_state(MoveStates.choosing_to_city)
    await cb.message.edit_text(
        "Тепер вибери <b>місто (КУДИ)</b>:",
        reply_markup=cities_kb(cities, "mv:to_city_", back_cb="mv:menu"),
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
    await cb.message.edit_text(
        "Вибери <b>ТТ (КУДИ)</b>:",
        reply_markup=points_kb(points, "mv:to_point_", back_cb="mv:menu"),
    )
    await cb.answer()


@router.callback_query(MoveStates.choosing_to_point, F.data.startswith("mv:to_point_"))
async def mv_to_point(cb: CallbackQuery, state: FSMContext):
    point_id = int(cb.data.split("_")[-1])
    data = await state.get_data()
    move_id = int(data["move_id"])

    mv_repo.set_to_point(move_id, point_id)

    m = mv_repo.get_move(move_id)
    await state.clear()
    await cb.message.edit_text(
        "✅ Маршрут зібраний.\n\n" + move_text(m),
        reply_markup=move_review_kb(move_id),
    )
    await cb.answer()


# ---------- add photo / note ----------
@router.callback_query(F.data.startswith("mv:photo_"))
async def mv_photo_start(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])
    await state.update_data(move_id=move_id)
    await state.set_state(MoveStates.waiting_photo)
    await cb.message.edit_text(
        f"📷 Надішли фото накладної для <b>#{move_id}</b> одним повідомленням.\n\n"
        f"Якщо передумав — напиши <code>-</code> (дефіс)."
    )
    await cb.answer()


@router.message(MoveStates.waiting_photo)
async def mv_photo_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    move_id = int(data["move_id"])

    if (message.text or "").strip() == "-":
        await state.clear()
        m = mv_repo.get_move(move_id)
        await message.answer("Ок, фото пропущено.\n\n" + move_text(m), reply_markup=move_review_kb(move_id))
        return

    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id

    if not file_id:
        await message.answer("⚠️ Це не схоже на фото. Надішли саме фото/картинку або постав '-' щоб пропустити.")
        return

    mv_repo.set_photo(move_id, file_id)
    await state.clear()

    m = mv_repo.get_move(move_id)
    await message.answer("✅ Фото збережено.\n\n" + move_text(m), reply_markup=move_review_kb(move_id))


@router.callback_query(F.data.startswith("mv:note_"))
async def mv_note_start(cb: CallbackQuery, state: FSMContext):
    move_id = int(cb.data.split("_")[-1])
    await state.update_data(move_id=move_id)
    await state.set_state(MoveStates.waiting_note)
    await cb.message.edit_text(
        f"📝 Напиши коментар для <b>#{move_id}</b>.\n\n"
        f"Якщо без комента — напиши <code>-</code>."
    )
    await cb.answer()


@router.message(MoveStates.waiting_note)
async def mv_note_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    move_id = int(data["move_id"])

    txt = (message.text or "").strip()
    if txt == "-":
        txt = ""

    mv_repo.set_note(move_id, txt)
    await state.clear()

    m = mv_repo.get_move(move_id)
    await message.answer("✅ Коментар оновлено.\n\n" + move_text(m), reply_markup=move_review_kb(move_id))


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

    from_point_id = int(m["from_point_id"])
    to_point_id = int(m["to_point_id"])

    from_users = auth_repo.get_point_users(from_point_id)
    to_users = auth_repo.get_point_users(to_point_id)

    from_rec = [u["telegram_id"] for u in from_users if u.get("telegram_id")]
    to_rec = [u["telegram_id"] for u in to_users if u.get("telegram_id")]

    if not from_rec or not to_rec:
        await cb.answer(
            "⚠️ Не всі ТТ мають прив’язаних людей.\n"
            "Нехай продавці оберуть ТТ в боті, а адмін підтвердить.",
            show_alert=True
        )
        return

    mv_repo.set_status(move_id, "sent")
    m = mv_repo.get_move(move_id)

    version = m.get("invoice_version") or 1
    text = f"📣 <b>Переміщення #{move_id}</b> (V{version})\n\n" + move_text(m)

    sent_from = 0
    sent_to = 0

    for uid in from_rec:
        try:
            if m.get("photo_file_id"):
                await cb.bot.send_photo(uid, photo=m["photo_file_id"], caption=text, reply_markup=point_from_kb(move_id))
            else:
                await cb.bot.send_message(uid, text, reply_markup=point_from_kb(move_id))
            sent_from += 1
        except Exception:
            pass

    for uid in to_rec:
        try:
            if m.get("photo_file_id"):
                await cb.bot.send_photo(uid, photo=m["photo_file_id"], caption=text, reply_markup=point_to_kb(move_id))
            else:
                await cb.bot.send_message(uid, text, reply_markup=point_to_kb(move_id))
            sent_to += 1
        except Exception:
            pass

    if sent_from == 0 or sent_to == 0:
        await cb.answer(
            "⚠️ Частині людей не доставилось.\n"
            "Перевір, чи вони натиснули /start у боті і не блокували його.",
            show_alert=True
        )

    operator_id = m.get("operator_id") or cb.from_user.id
    try:
        await cb.bot.send_message(
            operator_id,
            f"✅ Відправлено на ТТ.\n"
            f"Відправник отримали: <b>{sent_from}</b>\n"
            f"Отримувач отримали: <b>{sent_to}</b>\n\n"
            + move_text(m)
        )
    except Exception:
        pass

    await cb.message.edit_text(
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
        await cb.message.edit_text(move_text(m), reply_markup=moves_menu_kb())


@router.callback_query(F.data.startswith("mv:done_"))
async def mv_done(cb: CallbackQuery):
    move_id = int(cb.data.split("_")[-1])
    ok = mv_repo.set_status(move_id, "done")
    await cb.answer("✅ Завершено" if ok else "⚠️ Не знайдено", show_alert=True)
    m = mv_repo.get_move(move_id)
    if m:
        await cb.message.edit_text(move_text(m), reply_markup=moves_menu_kb())


# ---------- commands ----------
@router.message(Command("moves"))
async def cmd_moves(message: Message):
    items = mv_repo.list_moves(50)
    if not items:
        return await message.answer("Поки переміщень нема.")

    lines = ["📋 <b>Останні переміщення:</b>"]
    for m in items:
        fp = m.get("from_point_name") or "—"
        tp = m.get("to_point_name") or "—"
        st_raw = (m.get("status") or "").lower()
        st = STATUS_UA.get(st_raw, m.get("status") or "—")
        lines.append(f"• <b>#{m['id']}</b> ({st}) {fp} → {tp}")

    lines.append("\nДетально: <code>/info ID</code>")
    text = "\n".join(lines)

    for chunk in split_text(text):
        await message.answer(chunk)


@router.message(Command("info"))
async def cmd_info(message: Message):
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Формат: <code>/info 123</code>")
    move_id = int(parts[1])
    m = mv_repo.get_move(move_id)
    if not m:
        return await message.answer("Не знайдено.")
    await message.answer(move_text(m))
