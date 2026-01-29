# app/main.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from .logger import setup_logging
from .config import load_config

from .db.sqlite import init_db
from .db.schema import ensure_schema

from .handlers.start import router as start_router
from .handlers.locations import router as locations_router
from .handlers.moves import router as moves_router
from .handlers.point_users import router as point_users_router
from .handlers.auth import router as auth_router
from .handlers.point_profile import router as point_profile_router
from .handlers.point_moves import router as point_moves_router
from .handlers.moves_admin import router as moves_admin_router
from .handlers.reinvoice import router as reinvoice_router

from .middlewares.admin_only import AdminOnlyMiddleware


async def main() -> None:
    setup_logging()
    log = logging.getLogger("main")

    cfg = load_config()

    # DB init + schema
    init_db(cfg.db_path)
    ensure_schema()

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # middleware: admin gate
    dp.message.middleware(AdminOnlyMiddleware(cfg.admins_set))
    dp.callback_query.middleware(AdminOnlyMiddleware(cfg.admins_set))

    # routers
    dp.include_router(start_router)
    dp.include_router(locations_router)
    dp.include_router(moves_router)
    dp.include_router(point_users_router)
    dp.include_router(auth_router)
    dp.include_router(point_profile_router)
    dp.include_router(point_moves_router)
    dp.include_router(moves_admin_router)
    dp.include_router(reinvoice_router)

    me = await bot.get_me()
    log.info("Bot started as @%s", me.username)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

