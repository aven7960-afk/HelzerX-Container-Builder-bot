from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComponentDef:
    key: str
    label: str
    description: str
    icon: str
    default: dict


COMPONENTS: tuple[ComponentDef, ...] = (
    ComponentDef("text", "Text Display", "Markdown text block", "TEXT", {"content": "## HelzerX\nYour text here."}),
    ComponentDef("section", "Section", "Text with button or thumbnail accessory", "SECTION", {"content": "Section content", "accessory": "button", "label": "Open", "style": "primary", "custom_id": "helzerx:section", "url": ""}),
    ComponentDef("separator", "Separator", "Divider and spacing", "SEPARATOR", {"visible": True, "spacing": "small"}),
    ComponentDef("media", "Media Gallery", "Up to 10 media items", "MEDIA", {"items": ["https://example.com/image.png"]}),
    ComponentDef("thumbnail", "Thumbnail", "Image accessory; rendered inside a Section", "THUMBNAIL", {"url": "https://example.com/image.png", "description": ""}),
    ComponentDef("button", "Button", "Interactive button", "BUTTON", {"label": "Click me", "style": "primary", "custom_id": "helzerx:button", "url": ""}),
    ComponentDef("select", "String Select", "Dropdown with up to 25 options", "SELECT", {"placeholder": "Choose an option", "custom_id": "helzerx:select", "options": [{"label": "Option 1", "value": "one", "description": "First option"}]}),
    ComponentDef("user_select", "User Select", "Select Discord users", "SELECT", {"placeholder": "Select users", "custom_id": "helzerx:user-select"}),
    ComponentDef("role_select", "Role Select", "Select Discord roles", "SELECT", {"placeholder": "Select roles", "custom_id": "helzerx:role-select"}),
    ComponentDef("mentionable_select", "Mentionable Select", "Select users or roles", "SELECT", {"placeholder": "Select mentionables", "custom_id": "helzerx:mentionable-select"}),
    ComponentDef("channel_select", "Channel Select", "Select Discord channels", "SELECT", {"placeholder": "Select channels", "custom_id": "helzerx:channel-select"}),
    ComponentDef("action_row", "Action Row", "Group interactive controls", "ACTION_ROW", {"children": [{"type": "button", "data": {"label": "Button", "style": "primary", "custom_id": "helzerx:row-button"}}]}),
    ComponentDef("file", "File", "Inline uploaded attachment", "FILE", {"url": "attachment://file.txt", "spoiler": False}),
)

BY_KEY = {item.key: item for item in COMPONENTS}


def component_def(key: str) -> ComponentDef:
    return BY_KEY[key]
