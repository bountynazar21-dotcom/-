from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from ..config import load_config
from ..keyboards.common import public_menu_kb, admin_menu_kb

router = Router()

@router.message(CommandStart())
async def start_cmd(message: Message):
    cfg = load_config()
    if message.from_user.id in cfg.admins_set:
        await message.answer("👋 Адмін-панель:", reply_markup=admin_menu_kb())
    else:
        await message.answer("👋 Обери дію:", reply_markup=public_menu_kb())

@router.message(Command("whoami"))
async def whoami_cmd(message: Message):
    await message.answer(f"🆔 Твій Telegram ID: <code>{message.from_user.id}</code>")

@router.callback_query(lambda c: c.data == "menu:main")
async def menu_main(cb: CallbackQuery):
    cfg = load_config()
    if cb.from_user.id in cfg.admins_set:
        await cb.message.edit_text("👋 Адмін-панель:", reply_markup=admin_menu_kb())
    else:
        await cb.message.edit_text("👋 Обери дію:", reply_markup=public_menu_kb())
    await cb.answer()
