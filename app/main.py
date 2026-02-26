# app/main.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from aiogram.types import BotCommand
from aiogram.methods import SetMyCommands
from aiogram.types import BotCommandScopeDefault, BotCommandScopeChat

from .logger import setup_logging
from .config import load_config
from .db.pg_schema import ensure_schema

from .handlers.start import router as start_router
from .handlers.locations import router as locations_router
from .handlers.moves import router as moves_router
from .handlers.point_users import router as point_users_router
from .handlers.auth import router as auth_router
from .handlers.point_profile import router as point_profile_router
from .handlers.point_moves import router as point_moves_router
from .handlers.moves_admin import router as moves_admin_router

from .middlewares.admin_only import AdminOnlyMiddleware


async def _setup_bot_commands(bot: Bot, admins: set[int]) -> None:
    """
    Telegram menu commands:
    - default (для всіх): тільки /start
    - admins: повний список команд
    """
    # 1) Для всіх користувачів (продавці/ТТ)
    await bot(SetMyCommands(
        commands=[
            BotCommand(command="start", description="Запуск / меню"),
        ],
        scope=BotCommandScopeDefault(),
    ))

    # 2) Для адмінів — повний список
    admin_cmds = [
        BotCommand(command="start", description="Запуск / меню"),
        BotCommand(command="moves", description="Список переміщень"),
        BotCommand(command="info", description="Інфо по переміщенню: /info ID"),
        # якщо є ще адмінські команди — додаємо тут:
        # BotCommand(command="addcity", description="Додати місто"),
        # BotCommand(command="addpoint", description="Додати ТТ"),
    ]

    for admin_id in admins:
        await bot(SetMyCommands(
            commands=admin_cmds,
            scope=BotCommandScopeChat(chat_id=admin_id),
        ))


async def main() -> None:
    setup_logging()
    log = logging.getLogger("main")

    cfg = load_config()

    # ✅ Postgres schema init
    ensure_schema()

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # ✅ ПУБЛІЧНІ РОУТЕРИ (для всіх)
    dp.include_router(start_router)
    dp.include_router(auth_router)
    dp.include_router(point_profile_router)
    dp.include_router(point_moves_router)   # ✅ Віддав/Отримав/Коригування для ТТ

    # ✅ АДМІН РОУТЕРИ (тільки для адмінів)
    locations_router.message.middleware(AdminOnlyMiddleware(cfg.admins_set))
    locations_router.callback_query.middleware(AdminOnlyMiddleware(cfg.admins_set))

    moves_router.message.middleware(AdminOnlyMiddleware(cfg.admins_set))
    moves_router.callback_query.middleware(AdminOnlyMiddleware(cfg.admins_set))

    point_users_router.message.middleware(AdminOnlyMiddleware(cfg.admins_set))
    point_users_router.callback_query.middleware(AdminOnlyMiddleware(cfg.admins_set))

    moves_admin_router.message.middleware(AdminOnlyMiddleware(cfg.admins_set))
    moves_admin_router.callback_query.middleware(AdminOnlyMiddleware(cfg.admins_set))

    dp.include_router(locations_router)
    dp.include_router(moves_router)
    dp.include_router(point_users_router)
    dp.include_router(moves_admin_router)

    me = await bot.get_me()
    log.info("Bot started as @%s", me.username)

    # ✅ Commands меню: продавці бачать тільки /start, адміни — всі
    try:
        await _setup_bot_commands(bot, cfg.admins_set)
        log.info("Bot commands set: default=/start, admins=full")
    except Exception:
        log.exception("Failed to set bot commands")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())