from typing import Callable, Awaitable, Any
from aiogram.types import Message, CallbackQuery
from aiogram.dispatcher.middlewares.base import BaseMiddleware

# Адмінські розділи (заборонені не-адмінам)
ADMIN_CALLBACK_PREFIXES = ("loc:", "mv:", "pu:", "mva:")

# Публічні колбеки (дозволені всім)
PUBLIC_CALLBACK_PREFIXES = ("auth:", "pt:", "menu:main")

# Адмін-команди (заборонені не-адмінам)
ADMIN_COMMANDS = (
    "/cities", "/addcity", "/addpoint", "/delcity", "/delpoint",
    "/moves", "/newmove", "/info", "/reinvoice"
)

PUBLIC_COMMANDS = ("/start", "/whoami")


class AdminOnlyMiddleware(BaseMiddleware):
    def __init__(self, admins: set[int]):
        self.admins = admins

    async def __call__(
        self,
        handler: Callable[[Any, dict], Awaitable[Any]],
        event: Any,
        data: dict
    ) -> Any:

        # -------- Messages --------
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            txt = (event.text or "").strip()

            # /start /whoami — для всіх
            if any(txt.startswith(cmd) for cmd in PUBLIC_COMMANDS):
                return await handler(event, data)

            # якщо це адмін-команда — пропускаємо тільки адміна
            if any(txt.startswith(cmd) for cmd in ADMIN_COMMANDS):
                if user_id not in self.admins:
                    await event.answer("⛔️ Це адмін-команда. Звернись до адміністратора.")
                    return
                return await handler(event, data)

            # інші повідомлення — дозволяємо (FSM коригування/фото/тощо)
            return await handler(event, data)

        # -------- Callbacks --------
        if isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
            cbdata = event.data or ""

            # публічні колбеки — завжди ок
            if cbdata.startswith(PUBLIC_CALLBACK_PREFIXES):
                return await handler(event, data)

            # адмінські колбеки — тільки адміни
            if cbdata.startswith(ADMIN_CALLBACK_PREFIXES):
                if user_id not in self.admins:
                    await event.answer("⛔️ Цей розділ тільки для адмінів.", show_alert=True)
                    return
                return await handler(event, data)

            # все інше — дозволяємо
            return await handler(event, data)

        return await handler(event, data)


