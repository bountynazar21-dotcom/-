from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from app.keyboards.locations import locations_menu_kb, cities_kb, points_kb
from app.states.locations import LocationsStates
from app.db import ensure_schema
from app.db import locations_repo as repo
from app.utils.text import cities_text

router = Router()

# ---------- MENU ----------
@router.callback_query(F.data == "loc:menu")
async def loc_menu(cb: CallbackQuery):
    ensure_schema()
    await cb.message.edit_text("🏙 Меню локацій:", reply_markup=locations_menu_kb())
    await cb.answer()

# ---------- LIST CITIES ----------
@router.callback_query(F.data == "loc:cities")
async def loc_cities(cb: CallbackQuery):
    ensure_schema()
    cities = repo.list_cities()
    payload = []
    for cid, name in cities:
        payload.append((cid, name, repo.count_points(cid)))
    await cb.message.edit_text(cities_text(payload), reply_markup=locations_menu_kb())
    await cb.answer()

# ---------- ADD CITY (FSM) ----------
@router.callback_query(F.data == "loc:add_city")
async def add_city_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(LocationsStates.add_city)
    await cb.message.edit_text("➕ Введи назву міста одним повідомленням:")
    await cb.answer()

@router.message(LocationsStates.add_city)
async def add_city_finish(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    ok = repo.add_city(name)
    await state.clear()
    if ok:
        await message.answer(f"✅ Місто додано: <b>{name}</b>\n/ start або кнопки для продовження.")
    else:
        await message.answer("⚠️ Не додалось. Може вже існує або порожня назва.")

# ---------- ADD POINT (choose city -> enter name) ----------
@router.callback_query(F.data == "loc:add_point_choose_city")
async def add_point_choose_city(cb: CallbackQuery, state: FSMContext):
    cities = repo.list_cities()
    if not cities:
        await cb.answer("Спочатку додай місто.", show_alert=True)
        return
    await state.set_state(LocationsStates.add_point_choose_city)
    await cb.message.edit_text("Вибери місто:", reply_markup=cities_kb(cities, "loc:addpoint_city_"))
    await cb.answer()

@router.callback_query(LocationsStates.add_point_choose_city, F.data.startswith("loc:addpoint_city_"))
async def add_point_city_picked(cb: CallbackQuery, state: FSMContext):
    city_id = int(cb.data.split("_")[-1])
    await state.update_data(city_id=city_id)
    await state.set_state(LocationsStates.add_point_enter_name)
    await cb.message.edit_text("➕ Введи назву ТТ (як в реалі, без приколів):")
    await cb.answer()

@router.message(LocationsStates.add_point_enter_name)
async def add_point_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    city_id = int(data["city_id"])
    name = (message.text or "").strip()
    ok = repo.add_point(city_id, name)
    await state.clear()
    if ok:
        await message.answer(f"✅ ТТ додано: <b>{name}</b>")
    else:
        await message.answer("⚠️ Не додалось. Може вже існує або порожня назва.")

# ---------- DELETE CITY ----------
@router.callback_query(F.data == "loc:del_city_choose")
async def del_city_choose(cb: CallbackQuery):
    cities = repo.list_cities()
    if not cities:
        await cb.answer("Міст нема.", show_alert=True)
        return
    await cb.message.edit_text("🗑 Вибери місто для видалення:", reply_markup=cities_kb(cities, "loc:delcity_"))
    await cb.answer()

@router.callback_query(F.data.startswith("loc:delcity_"))
async def del_city_do(cb: CallbackQuery):
    city_id = int(cb.data.split("_")[-1])
    ok = repo.delete_city(city_id)
    await cb.answer("✅ Видалено" if ok else "⚠️ Не знайдено", show_alert=True)
    await cb.message.edit_text("🏙 Меню локацій:", reply_markup=locations_menu_kb())

# ---------- DELETE POINT (choose city -> choose point) ----------
@router.callback_query(F.data == "loc:del_point_choose_city")
async def del_point_choose_city(cb: CallbackQuery):
    cities = repo.list_cities()
    if not cities:
        await cb.answer("Міст нема.", show_alert=True)
        return
    await cb.message.edit_text("Вибери місто:", reply_markup=cities_kb(cities, "loc:delpoint_city_"))
    await cb.answer()

@router.callback_query(F.data.startswith("loc:delpoint_city_"))
async def del_point_choose_point(cb: CallbackQuery):
    city_id = int(cb.data.split("_")[-1])
    points = repo.list_points(city_id)
    if not points:
        await cb.answer("У цьому місті нема ТТ.", show_alert=True)
        return
    await cb.message.edit_text(
        "🗑 Вибери ТТ для видалення:",
        reply_markup=points_kb(points, "loc:delpoint_", back_cb="loc:del_point_choose_city"),
    )
    await cb.answer()

@router.callback_query(F.data.startswith("loc:delpoint_"))
async def del_point_do(cb: CallbackQuery):
    point_id = int(cb.data.split("_")[-1])
    ok = repo.delete_point(point_id)
    await cb.answer("✅ Видалено" if ok else "⚠️ Не знайдено", show_alert=True)
    await cb.message.edit_text("🏙 Меню локацій:", reply_markup=locations_menu_kb())

# ---------- COMMAND FALLBACKS ----------
@router.message(Command("cities"))
async def cmd_cities(message: Message):
    cities = repo.list_cities()
    payload = [(cid, name, repo.count_points(cid)) for cid, name in cities]
    await message.answer(cities_text(payload))

@router.message(Command("addcity"))
async def cmd_addcity(message: Message):
    name = (message.text or "").replace("/addcity", "").strip()
    if not name:
        return await message.answer("Формат: <code>/addcity НазваМіста</code>")
    ok = repo.add_city(name)
    await message.answer("✅ Додано" if ok else "⚠️ Не додалось (може існує)")

@router.message(Command("addpoint"))
async def cmd_addpoint(message: Message):
    # /addpoint City | TT
    raw = (message.text or "").replace("/addpoint", "").strip()
    if "|" not in raw:
        return await message.answer("Формат: <code>/addpoint Місто | НазваТТ</code>")
    city_name, tt = [x.strip() for x in raw.split("|", 1)]
    cities = repo.list_cities()
    city_id = next((cid for cid, name in cities if name.lower() == city_name.lower()), None)
    if not city_id:
        return await message.answer("⚠️ Місто не знайдено.")
    ok = repo.add_point(city_id, tt)
    await message.answer("✅ ТТ додано" if ok else "⚠️ Не додалось (може існує)")
