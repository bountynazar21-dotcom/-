# app/handlers/reinvoice.py
"""
Цей файл РАНІШЕ конфліктував з moves_admin.py, бо ловив:
    F.data.startswith("mva:reinvoice_")
і дублював логіку.

Реінвойс-флоу тепер єдине джерело правди в:
    app/handlers/moves_admin.py

Тому тут ми або:
- не ловимо ці callback-и взагалі, або
- залишаємо legacy-хендлер на інший префікс, який не використовується в проді.

Якщо хочеш — можеш взагалі прибрати include_router(reinvoice.router) з main.py.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()
PM = "HTML"


async def _safe_answer(cb: CallbackQuery, text: str, alert: bool = True):
    try:
        await cb.answer(text, show_alert=alert)
    except Exception:
        pass


# ✅ Legacy хендлер (НЕ конфліктує)
# Спрацьовує лише якщо ти ДУЖЕ спеціально зробиш кнопку з таким callback_data.
@router.callback_query(F.data.regexp(r"^mva:reinvoice_legacy_\d+$"))
async def mva_reinvoice_legacy(cb: CallbackQuery):
    await _safe_answer(
        cb,
        "ℹ️ Реінвойс перенесено в адмін-флоу. Використай кнопку «Реінвойс» в картці переміщення.",
        alert=True,
    )
