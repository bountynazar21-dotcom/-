from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def locations_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список міст", callback_data="loc:cities")],
        [InlineKeyboardButton(text="➕ Додати місто", callback_data="loc:add_city")],
        [InlineKeyboardButton(text="➕ Додати ТТ", callback_data="loc:add_point_choose_city")],
        [InlineKeyboardButton(text="🗑 Видалити місто", callback_data="loc:del_city_choose")],
        [InlineKeyboardButton(text="🗑 Видалити ТТ", callback_data="loc:del_point_choose_city")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main")],
    ])

def cities_kb(cities: list[tuple[int, str]], prefix: str) -> InlineKeyboardMarkup:
    # prefix: loc:city_... / loc:delcity_... / etc
    rows = []
    for cid, name in cities:
        rows.append([InlineKeyboardButton(text=name, callback_data=f"{prefix}{cid}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="loc:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def points_kb(points: list[tuple[int, str]], prefix: str, back_cb: str) -> InlineKeyboardMarkup:
    rows = []
    for pid, name in points:
        rows.append([InlineKeyboardButton(text=name, callback_data=f"{prefix}{pid}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
