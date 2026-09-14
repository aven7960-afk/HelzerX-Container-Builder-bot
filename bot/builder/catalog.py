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
    ComponentDef("section", "Section", "Text with button or thumbnail accessory", "SECTION", {"content": "Section content", "accessory": "button"}),
    ComponentDef("separator", "Separator", "Divider and spacing", "SEPARATOR", {"visible": True, "spacing": "small"}),
    ComponentDef("media", "Media Gallery", "Up to 10 image/video media items", "MEDIA", {"items": ["https://example.com/image.png"]}),
    ComponentDef("thumbnail", "Thumbnail", "Compact image accessory", "THUMBNAIL", {"url": "https://example.com/image.png", "description": ""}),
    ComponentDef("button", "Button", "Interactive button", "BUTTON", {"label": "Click me", "style": "primary", "custom_id": "helzerx:button", "url": ""}),
    ComponentDef("select", "String Select", "Dropdown with options", "SELECT", {"placeholder": "Choose an option", "custom_id": "helzerx:select", "options": [{"label": "Option 1", "value": "one", "description": "First option"}]}),
    ComponentDef("action_row", "Action Row", "Group interactive controls", "ACTION_ROW", {"children": ["button"]}),
    ComponentDef("file", "File", "Inline attachment component", "FILE", {"url": "attachment://file.txt", "spoiler": False}),
)

BY_KEY = {item.key: item for item in COMPONENTS}

def component_def(key: str) -> ComponentDef:
    return BY_KEY[key]
