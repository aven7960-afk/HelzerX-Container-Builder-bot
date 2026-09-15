from __future__ import annotations

from typing import Any

import discord
from discord import ui

from bot.builder.state import BuilderState, ComponentSpec

STYLE_MAP = {"primary": discord.ButtonStyle.primary, "secondary": discord.ButtonStyle.secondary, "success": discord.ButtonStyle.success, "danger": discord.ButtonStyle.danger, "link": discord.ButtonStyle.link}


def _button(data: dict[str, Any], *, disabled_preview: bool = True) -> ui.Button:
    style_name = str(data.get("style", "secondary")).lower()
    style = STYLE_MAP.get(style_name, discord.ButtonStyle.secondary)
    url = str(data.get("url", "")).strip() or None
    custom_id = None if style is discord.ButtonStyle.link else str(data.get("custom_id", "helzerx:button"))[:100]
    return ui.Button(label=str(data.get("label", "Button"))[:80], style=style, custom_id=custom_id, url=url, disabled=bool(data.get("disabled", False)) or disabled_preview, emoji=data.get("emoji") or None)


def _string_select(data: dict[str, Any], *, disabled_preview: bool = True) -> ui.Select:
    options = []
    for raw in data.get("options", [])[:25]:
        if isinstance(raw, dict):
            options.append(discord.SelectOption(label=str(raw.get("label", "Option"))[:100], value=str(raw.get("value", "option"))[:100], description=str(raw.get("description", ""))[:100] or None, default=bool(raw.get("default", False))))
    if not options: options = [discord.SelectOption(label="Option", value="option")]
    minimum = max(0, min(int(data.get("min_values", 1)), len(options)))
    maximum = max(minimum, min(int(data.get("max_values", 1)), len(options)))
    return ui.Select(placeholder=str(data.get("placeholder", "Choose an option"))[:150], options=options, min_values=minimum, max_values=maximum, custom_id=str(data.get("custom_id", "helzerx:select"))[:100], disabled=bool(data.get("disabled", False)) or disabled_preview)


def _entity_select(kind: str, data: dict[str, Any], *, disabled_preview: bool = True) -> ui.Select:
    cls = {"user_select": ui.UserSelect, "role_select": ui.RoleSelect, "mentionable_select": ui.MentionableSelect, "channel_select": ui.ChannelSelect}[kind]
    return cls(placeholder=str(data.get("placeholder", "Select..."))[:150], min_values=max(0, min(int(data.get("min_values", 1)), 25)), max_values=max(1, min(int(data.get("max_values", 1)), 25)), custom_id=str(data.get("custom_id", f"helzerx:{kind}"))[:100], disabled=bool(data.get("disabled", False)) or disabled_preview)


def render_component(spec: ComponentSpec) -> ui.Item | None:
    if not spec.enabled: return None
    data, kind = spec.data, spec.type
    if kind == "text": return ui.TextDisplay(str(data.get("content", ""))[:4000])
    if kind == "separator":
        spacing = getattr(discord.SeparatorSpacing, str(data.get("spacing", "small")).lower(), discord.SeparatorSpacing.small)
        return ui.Separator(visible=bool(data.get("visible", True)), spacing=spacing)
    if kind == "thumbnail":
        url = str(data.get("url", "")).strip()
        if not url: return None
        return ui.Section(ui.TextDisplay(str(data.get("description", "Thumbnail"))[:4000]), accessory=ui.Thumbnail(url, description=str(data.get("description", ""))[:256] or None, spoiler=bool(data.get("spoiler", False))))
    if kind == "media":
        gallery = ui.MediaGallery()
        for raw in data.get("items", [])[:10]:
            if isinstance(raw, str) and raw.strip(): gallery.add_item(media=raw.strip())
            elif isinstance(raw, dict) and raw.get("url"): gallery.add_item(media=str(raw["url"]), description=str(raw.get("description", ""))[:256] or None, spoiler=bool(raw.get("spoiler", False)))
        return gallery if gallery.items else None
    if kind == "button": return _button(data)
    if kind == "select": return _string_select(data)
    if kind in {"user_select", "role_select", "mentionable_select", "channel_select"}: return _entity_select(kind, data)
    if kind == "section":
        content = str(data.get("content", "Section content"))[:4000]
        if str(data.get("accessory", "button")).lower() == "thumbnail" and data.get("url"):
            accessory: ui.Item = ui.Thumbnail(str(data["url"]), description=str(data.get("description", ""))[:256] or None, spoiler=bool(data.get("spoiler", False)))
        else:
            accessory = _button(data, disabled_preview=True)
        return ui.Section(ui.TextDisplay(content), accessory=accessory)
    if kind == "action_row":
        row = ui.ActionRow()
        for child in data.get("children", [])[:5]:
            if isinstance(child, dict) and child.get("type") == "button": row.add_item(_button(child.get("data", {})))
            elif isinstance(child, dict) and child.get("type") == "select": row.add_item(_string_select(child.get("data", {})))
            elif child == "button": row.add_item(_button(data))
            elif child == "select": row.add_item(_string_select(data))
        return row
    if kind == "file":
        url = str(data.get("url", "")).strip()
        if url.startswith("attachment://"): return ui.File(url, spoiler=bool(data.get("spoiler", False)))
        return ui.TextDisplay(f"`File` preview requires an uploaded attachment: `{url or 'attachment://filename'}`")
    return ui.TextDisplay(f"> Unsupported component type: `{kind}`")


class RenderedComponentsView(ui.LayoutView):
    """Components V2 rendering of a saved builder state."""
    def __init__(self, state: BuilderState):
        super().__init__(timeout=300)
        accent = state.accent_color
        container = ui.Container(accent_color=discord.Colour(accent) if accent is not None else None)
        if state.name: container.add_item(ui.TextDisplay(f"# {state.name}"[:4000]))
        for spec in state.components:
            item = render_component(spec)
            if item is not None: container.add_item(item)
        self.add_item(container)
