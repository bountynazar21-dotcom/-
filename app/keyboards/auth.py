from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def cities_kb(cities: list[tuple[int, str]], prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=name, callback_data=f"{prefix}{cid}")] for cid, name in cities]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def points_kb(points: list[tuple[int, str]], prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=name, callback_data=f"{prefix}{pid}")] for pid, name in points]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="auth:login_point")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def approve_kb(user_id: int, point_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"auth:approve_{user_id}_{point_id}")],
    ])
