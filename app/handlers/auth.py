from aiogram import Router, F
from aiogram.types import CallbackQuery

from ..config import load_config
from ..db import locations_repo as loc_repo
from ..db import auth_repo
from ..keyboards.auth import cities_kb, points_kb, approve_kb

router = Router()

@router.callback_query(F.data == "auth:login_point")
async def login_point(cb: CallbackQuery):
    cities = loc_repo.list_cities()
    if not cities:
        await cb.answer("Нема міст. Нехай адмін додасть.", show_alert=True)
        return
    await cb.message.edit_text("🏙 Обери місто:", reply_markup=cities_kb(cities, "auth:city_"))
    await cb.answer()
    
@router.callback_query(F.data == "auth:change_point")
async def change_point(cb: CallbackQuery):
    # Це той самий флоу, просто інша кнопка
    cities = loc_repo.list_cities()
    if not cities:
        await cb.answer("Нема міст. Нехай адмін додасть.", show_alert=True)
        return
    await cb.message.edit_text("🔁 Змінити ТТ\n\n🏙 Обери місто:", reply_markup=cities_kb(cities, "auth:city_"))
    await cb.answer()


@router.callback_query(F.data.startswith("auth:city_"))
async def pick_city(cb: CallbackQuery):
    city_id = int(cb.data.split("_")[-1])
    points = loc_repo.list_points(city_id)
    if not points:
        await cb.answer("В цьому місті нема ТТ.", show_alert=True)
        return
    await cb.message.edit_text("📍 Обери свою ТТ:", reply_markup=points_kb(points, "auth:point_"))
    await cb.answer()

@router.callback_query(F.data.startswith("auth:point_"))
async def request_link(cb: CallbackQuery):
    point_id = int(cb.data.split("_")[-1])

    u = cb.from_user
    username = f"@{u.username}" if u.username else "no-username"
    full_name = u.full_name

    cfg = load_config()

    text = (
        "🧾 <b>Заявка на прив’язку ТТ</b>\n"
        f"Користувач: {username}\n"
        f"Ім’я: {full_name}\n"
        f"ID: <code>{u.id}</code>\n"
        f"ТТ ID: <code>{point_id}</code>\n\n"
        "Підтвердити прив’язку?"
    )

    kb = approve_kb(u.id, point_id)

    # зафіксуємо дані користувача в users (щоб адмін бачив username/ім'я)
    auth_repo.upsert_user(u.id, u.username, u.full_name, role="point")

    for admin_id in cfg.admins_set:
        try:
            await cb.bot.send_message(admin_id, text, reply_markup=kb)
        except Exception:
            pass

    await cb.message.edit_text("✅ Запит відправлено адмінам. Чекай підтвердження.")
    await cb.answer()

@router.callback_query(F.data.startswith("auth:approve_"))
async def approve(cb: CallbackQuery):
    # auth:approve_{userId}_{pointId}
    _, _, tail = cb.data.partition("auth:approve_")
    user_id_str, point_id_str = tail.split("_", 1)
    user_id = int(user_id_str)
    point_id = int(point_id_str)

    # прив'язка (можна скільки завгодно людей до однієї ТТ)
    auth_repo.link_user_to_point(user_id, point_id, username=None, full_name=None)

    await cb.answer("✅ Прив’язано", show_alert=True)
    await cb.message.edit_text("✅ Прив’язку підтверджено.")

    try:
        await cb.bot.send_message(user_id, "✅ Тебе прив’язано до ТТ. Тепер переміщення будуть приходити сюди.")
    except Exception:
        pass
