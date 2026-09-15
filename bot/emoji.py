"""Centralized emoji registry for the HelzerX Discord UI."""

from __future__ import annotations

import os


class Emoji:
    # Brand / navigation
    LOGO = "🔷"
    BUILDER = "🧩"
    PREVIEW = "👁️"
    SETTINGS = "⚙️"
    SAVE = "💾"
    JSON = "📄"
    BACK = "↩️"
    CLOSE = "❌"

    # Components
    CONTAINER = "📦"
    TEXT = "📝"
    SECTION = "📋"
    SEPARATOR = "➖"
    MEDIA = "🖼️"
    THUMBNAIL = "🏷️"
    BUTTON = "🔘"
    SELECT = "🔽"
    ACTION_ROW = "🔲"
    FILE = "📎"

    # Actions / status
    ADD = "➕"
    EDIT = "✏️"
    DUPLICATE = "📑"
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
        """Return a server custom emoji from env, or the Unicode fallback."""
        return os.getenv(f"EMOJI_{name.upper()}", fallback)


def emoji(name: str) -> str:
    """Resolve an emoji by registry name with an environment override."""
    value = getattr(Emoji, name.upper(), "")
    return Emoji.from_env(name, value)
