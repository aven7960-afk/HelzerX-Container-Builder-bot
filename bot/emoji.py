"""Centralized emoji registry.

Keep emoji presentation out of commands/views so the UI can be restyled from
one place. Custom Discord emoji strings can be supplied through environment
variables later without touching the builder code.
"""

from __future__ import annotations

import os


class Emoji:
    # Brand / navigation
    LOGO = "<:helzerx:>"
    BUILDER = "🧩"
    PREVIEW = "👁️"
    SETTINGS = "⚙️"
    SAVE = "💾"
    JSON = "{ }"
    BACK = "↩️"
    CLOSE = "✕"

    # Components
    CONTAINER = "📦"
    TEXT = "📝"
    SECTION = "▤"
    SEPARATOR = "➖"
    MEDIA = "🖼️"
    THUMBNAIL = "🏷️"
    BUTTON = "🔘"
    SELECT = "🔽"
    ACTION_ROW = "▰"
    FILE = "📎"

    # Actions / status
    ADD = "＋"
    EDIT = "✏️"
    REMOVE = "🗑️"
    REORDER = "↕️"
    COLOR = "🎨"
    SEND = "📤"
    SUCCESS = "✅"
    WARNING = "⚠️"
    ERROR = "❌"
    ONLINE = "🟢"
    OFFLINE = "🔴"

    @classmethod
    def from_env(cls, name: str, fallback: str) -> str:
        """Return a custom emoji from env, or the built-in fallback."""
        return os.getenv(f"EMOJI_{name.upper()}", fallback)


def emoji(name: str) -> str:
    """Resolve an emoji by registry name with an environment override."""
    value = getattr(Emoji, name.upper(), "")
    return Emoji.from_env(name, value)
