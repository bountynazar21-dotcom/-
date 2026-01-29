from aiogram import Router, F
from aiogram.types import CallbackQuery

from ..db import locations_repo as loc_repo
from ..db import auth_repo
from ..keyboards.locations import cities_kb, points_kb
from ..keyboards.point_users import point_users_list_kb, confirm_kick_kb

router = Router()

# Меню перегляду користувачів по ТТ: city -> point -> list users
@router.callback_query(F.data == "pu:choose_city")
async def choose_city(cb: CallbackQuery):
    cities = loc_repo.list_cities()
    if not cities:
        await cb.answer("Нема міст.", show_alert=True)
        return
    await cb.message.edit_text("🏙 Обери місто:", reply_markup=cities_kb(cities, "pu:city_"))
    await cb.answer()

@router.callback_query(F.data.startswith("pu:city_"))
async def choose_point(cb: CallbackQuery):
    city_id = int(cb.data.split("_")[-1])
    points = loc_repo.list_points(city_id)
    if not points:
        await cb.answer("Нема ТТ.", show_alert=True)
        return
    await cb.message.edit_text("📍 Обери ТТ:", reply_markup=points_kb(points, "pu:view_", back_cb="pu:choose_city"))
    await cb.answer()

@router.callback_query(F.data.startswith("pu:view_"))
async def view_point_users(cb: CallbackQuery):
    point_id = int(cb.data.split("_")[-1])
    users = auth_repo.get_point_users(point_id)

    if not users:
        await cb.message.edit_text("До цієї ТТ ще нікого не прив’язано.", reply_markup=None)
        await cb.answer()
        return

    await cb.message.edit_text(
        f"👥 Користувачі ТТ (ID: <code>{point_id}</code>):\n"
        f"Кількість: <b>{len(users)}</b>\n\n"
        "Натисни на людину, щоб прибрати.",
        reply_markup=point_users_list_kb(users, point_id),
    )
    await cb.answer()

@router.callback_query(F.data.startswith("pu:kick_"))
async def kick_preview(cb: CallbackQuery):
    _, _, tail = cb.data.partition("pu:kick_")
    point_id_str, user_id_str = tail.split("_", 1)
    point_id = int(point_id_str)
    user_id = int(user_id_str)

    await cb.message.edit_text(
        f"Точно прибрати користувача <code>{user_id}</code> з ТТ <code>{point_id}</code>?",
        reply_markup=confirm_kick_kb(point_id, user_id),
    )
    await cb.answer()

@router.callback_query(F.data.startswith("pu:confirm_"))
async def kick_do(cb: CallbackQuery):
    _, _, tail = cb.data.partition("pu:confirm_")
    point_id_str, user_id_str = tail.split("_", 1)
    point_id = int(point_id_str)
    user_id = int(user_id_str)

    ok = auth_repo.unlink_user(user_id)
    await cb.answer("✅ Прибрано" if ok else "⚠️ Не знайдено", show_alert=True)

    # повертаємось до списку
    users = auth_repo.get_point_users(point_id)
    if not users:
        await cb.message.edit_text("До цієї ТТ нікого не прив’язано.")
        return

    await cb.message.edit_text(
        f"👥 Користувачі ТТ (ID: <code>{point_id}</code>):\nКількість: <b>{len(users)}</b>",
        reply_markup=point_users_list_kb(users, point_id),
    )
