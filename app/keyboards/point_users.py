from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def point_users_list_kb(users: list[dict], point_id: int) -> InlineKeyboardMarkup:
    rows = []
    for u in users:
        username = f"@{u['username']}" if u.get("username") else "no-username"
        name = u.get("full_name") or ""
        tid = u["telegram_id"]
        text = f"🧑 {username} {name} ({tid})"
        rows.append([InlineKeyboardButton(text=text[:60], callback_data=f"pu:kick_{point_id}_{tid}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="pu:choose_point")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def confirm_kick_kb(point_id: int, telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Так, прибрати", callback_data=f"pu:confirm_{point_id}_{telegram_id}")],
        [InlineKeyboardButton(text="❌ Ні", callback_data=f"pu:view_{point_id}")],
    ])
