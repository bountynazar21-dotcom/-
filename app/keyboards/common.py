from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def public_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 Обрати свою ТТ", callback_data="auth:login_point")],
        [InlineKeyboardButton(text="🔁 Змінити ТТ", callback_data="auth:change_point")],
        [InlineKeyboardButton(text="🏷 Моя ТТ", callback_data="pt:mytt")],
        [InlineKeyboardButton(text="📦 Мої переміщення", callback_data="pt:moves")],
    ])

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏙 Міста / ТТ", callback_data="loc:menu")],
        [InlineKeyboardButton(text="📦 Переміщення", callback_data="mv:menu")],
        [InlineKeyboardButton(text="👥 Користувачі ТТ", callback_data="pu:choose_city")],
    ])
