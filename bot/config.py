from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_hex_color(value: str | None, default: int = 0x5865F2) -> int:
    if not value:
        return default
    try:
        return int(value.strip().lstrip("#"), 16)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    token: str
    dev_guild_ids: tuple[int, ...]
    default_accent_color: int

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token:
            raise RuntimeError("DISCORD_TOKEN is missing from the environment")

        raw_guilds = os.getenv("DEV_GUILD_IDS", "")
        guild_ids = tuple(
            int(item.strip())
            for item in raw_guilds.split(",")
            if item.strip().isdigit()
        )

        return cls(
            token=token,
            dev_guild_ids=guild_ids,
            default_accent_color=_parse_hex_color(os.getenv("DEFAULT_ACCENT_COLOR")),
        )
