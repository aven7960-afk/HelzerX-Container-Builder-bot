from __future__ import annotations

from typing import Any

import discord
from discord import ui

from bot.builder.state import BuilderState, ComponentSpec

STYLE_MAP = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
    "link": discord.ButtonStyle.link,
}


def _button(data: dict[str, Any], *, disabled_preview: bool = True) -> ui.Button:
    style = STYLE_MAP.get(str(data.get("style", "secondary")).lower(), discord.ButtonStyle.secondary)
    url = str(data.get("url", "")).strip() or None
    custom_id = None if style is discord.ButtonStyle.link else str(data.get("custom_id", "helzerx:button"))[:100]
    return ui.Button(
        label=str(data.get("label", "Button"))[:80],
        style=style,
        custom_id=custom_id,
        url=url,
        disabled=bool(data.get("disabled", False)) or disabled_preview,
    )


def _string_select(data: dict[str, Any], *, disabled_preview: bool = True) -> ui.Select:
    options = [
        discord.SelectOption(
            label=str(x.get("label", "Option"))[:100],
            value=str(x.get("value", "option"))[:100],
            description=str(x.get("description", ""))[:100] or None,
            default=bool(x.get("default", False)),
        )
        for x in data.get("options", [])[:25]
        if isinstance(x, dict)
    ]
    if not options:
        options = [discord.SelectOption(label="Option", value="option")]
    minimum = max(0, min(int(data.get("min_values", 1)), len(options)))
    maximum = max(minimum, min(int(data.get("max_values", 1)), len(options)))
    return ui.Select(
        placeholder=str(data.get("placeholder", "Choose an option"))[:150],
        options=options,
        min_values=minimum,
        max_values=maximum,
        custom_id=str(data.get("custom_id", "helzerx:select"))[:100],
        disabled=bool(data.get("disabled", False)) or disabled_preview,
    )


def _entity_select(kind: str, data: dict[str, Any], *, disabled_preview: bool = True) -> ui.Select:
    cls = {
        "user_select": ui.UserSelect,
        "role_select": ui.RoleSelect,
        "mentionable_select": ui.MentionableSelect,
        "channel_select": ui.ChannelSelect,
    }[kind]
    minimum = max(0, min(int(data.get("min_values", 1)), 25))
    maximum = max(minimum, min(int(data.get("max_values", 1)), 25))
    return cls(
        placeholder=str(data.get("placeholder", "Select..."))[:150],
        min_values=minimum,
        max_values=maximum,
        custom_id=str(data.get("custom_id", f"helzerx:{kind}"))[:100],
        disabled=bool(data.get("disabled", False)) or disabled_preview,
    )


def _media_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in data.get("items", [])[:10]:
        if isinstance(raw, str) and raw.strip():
            items.append({"url": raw.strip(), "description": "", "spoiler": False})
        elif isinstance(raw, dict) and raw.get("url"):
            items.append(
                {
                    "url": str(raw["url"]).strip(),
                    "description": str(raw.get("description", ""))[:256],
                    "spoiler": bool(raw.get("spoiler", False)),
                }
            )
    return items


def render_component(spec: ComponentSpec, *, interactive: bool = False) -> ui.Item | None:
    if not spec.enabled:
        return None

    data, kind = spec.data, spec.type

    if kind == "text":
        return ui.TextDisplay(str(data.get("content", ""))[:4000])

    if kind == "separator":
        spacing = getattr(
            discord.SeparatorSpacing,
            str(data.get("spacing", "small")).lower(),
            discord.SeparatorSpacing.small,
        )
        return ui.Separator(visible=bool(data.get("visible", True)), spacing=spacing)

    if kind == "thumbnail":
        url = str(data.get("url", "")).strip()
        if not url:
            return None
        return ui.Section(
            ui.TextDisplay(str(data.get("description", "Thumbnail"))[:4000]),
            accessory=ui.Thumbnail(
                url,
                description=str(data.get("description", ""))[:256] or None,
            ),
        )

    if kind == "media":
        items = _media_items(data)
        if not items:
            return ui.TextDisplay("No media uploaded yet.")
        gallery = ui.MediaGallery()
        for item in items:
            gallery.add_item(
                media=item["url"],
                description=item["description"] or None,
                spoiler=item["spoiler"],
            )
        return gallery

    if kind == "button":
        return _button(data, disabled_preview=not interactive)

    if kind == "select":
        return _string_select(data, disabled_preview=not interactive)

    if kind in {"user_select", "role_select", "mentionable_select", "channel_select"}:
        return _entity_select(kind, data, disabled_preview=not interactive)

    if kind == "section":
        if str(data.get("accessory", "button")).lower() == "thumbnail" and data.get("url"):
            accessory: ui.Item = ui.Thumbnail(
                str(data["url"]),
                description=str(data.get("description", ""))[:256] or None,
                spoiler=bool(data.get("spoiler", False)),
            )
        else:
            accessory = _button(data, disabled_preview=not interactive)
        return ui.Section(
            ui.TextDisplay(str(data.get("content", "Section content"))[:4000]),
            accessory=accessory,
        )

    if kind == "action_row":
        row = ui.ActionRow()
        for child in data.get("children", [])[:5]:
            if not isinstance(child, dict):
                continue
            if child.get("type") == "button":
                row.add_item(_button(child.get("data", {}), disabled_preview=not interactive))
            elif child.get("type") == "select":
                row.add_item(_string_select(child.get("data", {}), disabled_preview=not interactive))
        return row

    if kind == "file":
        url = str(data.get("url", "")).strip()
        if url.startswith("attachment://"):
            return ui.File(url, spoiler=bool(data.get("spoiler", False)))
        if url:
            return ui.TextDisplay(f"**File**\n`{str(data.get('filename', 'file'))[:100]}`")
        return ui.TextDisplay("No file uploaded yet.")

    return ui.TextDisplay(f"> Unsupported component type: `{kind}`")


def build_container(
    state: BuilderState,
    *,
    interactive: bool = False,
    show_name: bool = True,
    accent: bool = False,
) -> ui.Container:
    """Build the exact Components V2 container used by both preview and send."""
    container = ui.Container(
        accent_color=(discord.Colour(state.accent_color) if accent and state.accent_color is not None else None)
    )
    if show_name and state.name:
        container.add_item(ui.TextDisplay(f"# {state.name}"[:4000]))
    for spec in state.components:
        item = render_component(spec, interactive=interactive)
        if item is not None:
            container.add_item(item)
    return container


class RenderedComponentsView(ui.LayoutView):
    """Render the saved state as the same Components V2 layout shown in Live Preview."""

    def __init__(self, state: BuilderState, *, interactive: bool = False):
        super().__init__(timeout=300)
        self.add_item(build_container(state, interactive=interactive, show_name=True, accent=False))
