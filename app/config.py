from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

def _parse_ids(value: str) -> list[int]:
    if not value:
        return []
    raw = value.replace(",", " ").split()
    ids: list[int] = []
    for x in raw:
        try:
            ids.append(int(x))
        except ValueError:
            pass
    return ids

@dataclass(frozen=True)
class Config:
    bot_token: str
    admins: list[int]
    db_path: str

    @property
    def admins_set(self) -> set[int]:
        return set(self.admins)

def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("❌ BOT_TOKEN відсутній у .env")

    admins = _parse_ids(os.getenv("ADMINS", ""))
    db_path = os.getenv("DB_PATH", "bot.db").strip() or "bot.db"

    return Config(
        bot_token=token,
        admins=admins,
        db_path=db_path,
    )
