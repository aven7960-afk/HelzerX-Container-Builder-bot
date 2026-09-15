from __future__ import annotations

from dataclasses import dataclass, field
import copy
import json
from typing import Any


@dataclass(slots=True)
class ComponentSpec:
    type: str
    data: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "enabled": self.enabled, "data": copy.deepcopy(self.data)}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ComponentSpec":
        if not isinstance(raw, dict) or not isinstance(raw.get("type"), str) or not raw["type"].strip():
            raise ValueError("Each component must contain a non-empty string 'type'.")
        data = raw.get("data", {})
        if not isinstance(data, dict):
            raise ValueError("Component 'data' must be an object.")
        return cls(type=raw["type"].strip(), data=copy.deepcopy(data), enabled=bool(raw.get("enabled", True)))


@dataclass(slots=True)
class BuilderState:
    owner_id: int
    accent_color: int | None = 0x5865F2
    components: list[ComponentSpec] = field(default_factory=list)
    name: str = "Untitled Container"
    version: int = 2

    MAX_COMPONENTS = 40

    @property
    def component_count(self) -> int:
        return len(self.components)

    def add(self, component: ComponentSpec) -> bool:
        if self.component_count >= self.MAX_COMPONENTS:
            return False
        self.components.append(component)
        return True

    def duplicate(self, index: int) -> bool:
        if not 0 <= index < self.component_count or self.component_count >= self.MAX_COMPONENTS:
            return False
        original = self.components[index]
        self.components.insert(index + 1, ComponentSpec(original.type, copy.deepcopy(original.data), original.enabled))
        return True

    def remove(self, index: int) -> bool:
        if not 0 <= index < self.component_count:
            return False
        self.components.pop(index)
        return True

    def update(self, index: int, data: dict[str, Any]) -> bool:
        if not 0 <= index < self.component_count or not isinstance(data, dict):
            return False
        self.components[index].data = copy.deepcopy(data)
        return True

    def toggle(self, index: int) -> bool:
        if not 0 <= index < self.component_count:
            return False
        self.components[index].enabled = not self.components[index].enabled
        return True

    def move(self, index: int, direction: int) -> bool:
        target = index + direction
        if not (0 <= index < self.component_count and 0 <= target < self.component_count):
            return False
        self.components[index], self.components[target] = self.components[target], self.components[index]
        return True

    def clear(self) -> None:
        self.components.clear()

    def to_dict(self) -> dict[str, Any]:
        return {"version": 2, "name": self.name[:100], "accent_color": self.accent_color, "components": [c.to_dict() for c in self.components]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, owner_id: int, raw: dict[str, Any]) -> "BuilderState":
        if not isinstance(raw, dict):
            raise ValueError("Builder payload must be a JSON object.")
        raw_components = raw.get("components", [])
        if not isinstance(raw_components, list) or len(raw_components) > cls.MAX_COMPONENTS:
            raise ValueError("Components must be a list with at most 40 items.")
        accent = raw.get("accent_color", 0x5865F2)
        if accent is not None and (not isinstance(accent, int) or not 0 <= accent <= 0xFFFFFF):
            raise ValueError("accent_color must be a valid integer color.")
        return cls(owner_id=owner_id, accent_color=accent, components=[ComponentSpec.from_dict(x) for x in raw_components], name=str(raw.get("name", "Untitled Container"))[:100], version=2)

    @classmethod
    def from_json(cls, owner_id: int, raw: str) -> "BuilderState":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON.") from exc
        return cls.from_dict(owner_id, payload)
