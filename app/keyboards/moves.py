from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def moves_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Нове переміщення", callback_data="mv:new")],
        [InlineKeyboardButton(text="📋 Список переміщень", callback_data="mv:list")],
        [InlineKeyboardButton(text="🔎 Переглянути / Керувати", callback_data="mva:list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main")],
    ])


def cities_kb(cities: list[tuple[int, str]], prefix: str, back_cb: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=name, callback_data=f"{prefix}{cid}")]
            for cid, name in cities]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def points_kb(points: list[tuple[int, str]], prefix: str, back_cb: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=name, callback_data=f"{prefix}{pid}")]
            for pid, name in points]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def move_review_kb(move_id: int) -> InlineKeyboardMarkup:
    # ✅ ДВІ НЕЗАЛЕЖНІ КНОПКИ: фото та PDF
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📸 Фото накладної (альбом)", callback_data=f"mv:photo_{move_id}"),
            InlineKeyboardButton(text="📄 PDF накладної", callback_data=f"mv:pdf_{move_id}"),
        ],
        [InlineKeyboardButton(text="📝 Додати / змінити коментар", callback_data=f"mv:note_{move_id}")],
        [InlineKeyboardButton(text="✅ Відправити на ТТ", callback_data=f"mv:send_{move_id}")],
        [InlineKeyboardButton(text="🗑 Скасувати", callback_data=f"mv:cancel_{move_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="mv:menu")],
    ])


def move_actions_kb(move_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершити", callback_data=f"mv:done_{move_id}")],
        [InlineKeyboardButton(text="🗑 Скасувати", callback_data=f"mv:cancel_{move_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="mv:menu")],
    ])


# ---- keyboards for точки ----
def point_from_kb(move_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Віддав", callback_data=f"pt:handed_{move_id}")],
        [InlineKeyboardButton(text="⚠️ Коригування", callback_data=f"pt:corr_{move_id}")],
    ])


def point_to_kb(move_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отримав", callback_data=f"pt:received_{move_id}")],
        [InlineKeyboardButton(text="⚠️ Коригування", callback_data=f"pt:corr_{move_id}")],
    ])


# ✅ OPTIONAL UX: коли вже підтвердили, можна показати "засірені" кнопки (працюють як алерт)
def point_from_confirmed_kb(move_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Віддав (вже підтверджено)", callback_data=f"pt:handed_{move_id}")],
        [InlineKeyboardButton(text="⚠️ Коригування", callback_data=f"pt:corr_{move_id}")],
    ])


def point_to_confirmed_kb(move_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отримав (вже підтверджено)", callback_data=f"pt:received_{move_id}")],
        [InlineKeyboardButton(text="⚠️ Коригування", callback_data=f"pt:corr_{move_id}")],
    ])


# ✅ MULTI-PHOTO ДЛЯ СТВОРЕННЯ ПЕРЕМІЩЕННЯ
def mv_photos_done_kb(move_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data=f"mv:photo_done_{move_id}")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data=f"mv:photo_cancel_{move_id}")],
    ])


# ✅ PDF ДЛЯ СТВОРЕННЯ ПЕРЕМІЩЕННЯ (незалежно від фото)
def mv_pdf_done_kb(move_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Зберегти PDF", callback_data=f"mv:pdf_done_{move_id}")],
        [InlineKeyboardButton(text="🗑 Прибрати PDF", callback_data=f"mv:pdf_clear_{move_id}")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data=f"mv:pdf_cancel_{move_id}")],
    ])


# ---------- admin ----------
def admin_moves_tabs_kb(active: bool = True) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Активні", callback_data="mva:active"),
            InlineKeyboardButton(text="✅ Завершені", callback_data="mva:closed"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="mv:menu")],
    ])


def admin_moves_list_kb(moves: list[dict], back_cb: str) -> InlineKeyboardMarkup:
    rows = []
    for m in moves:
        mid = m["id"]
        fp = m.get("from_point_name") or "—"
        tp = m.get("to_point_name") or "—"
        status = m.get("status") or "?"
        rows.append([
            InlineKeyboardButton(
                text=f"#{mid} [{status}] {fp} → {tp}"[:60],
                callback_data=f"mva:view_{mid}"
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_move_actions_kb(move_id: int, back_cb: str = "mva:active") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Показати накладні", callback_data=f"mva:docs_{move_id}")],
        [InlineKeyboardButton(text="↪️ Надіслати нову накладну", callback_data=f"mva:reinvoice_{move_id}")],
        [InlineKeyboardButton(text="✅ Закрити переміщення", callback_data=f"mva:close_{move_id}")],
        [InlineKeyboardButton(text="⬅️ Назад до списку", callback_data=back_cb)],
    ])


# ✅ MULTI-PHOTO REINVOICE
def reinvoice_done_kb(move_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data=f"mva:reinvoice_done_{move_id}")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data=f"mva:reinvoice_cancel_{move_id}")],
    ])

