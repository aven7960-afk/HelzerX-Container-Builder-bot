from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ComponentSpec:
    """Serializable description of one component in a builder session."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **self.data}


@dataclass(slots=True)
class BuilderState:
    """Mutable per-user builder state.

    The state is intentionally framework-independent so it can later be saved
    to SQLite and imported/exported as JSON without coupling persistence to UI.
    """

    owner_id: int
    accent_color: int | None = None
    components: list[ComponentSpec] = field(default_factory=list)

    MAX_COMPONENTS = 40

    @property
    def component_count(self) -> int:
        return len(self.components)

    def add(self, component: ComponentSpec) -> bool:
        if self.component_count >= self.MAX_COMPONENTS:
            return False
        self.components.append(component)
        return True

    def remove(self, index: int) -> bool:
        if not 0 <= index < self.component_count:
            return False
        self.components.pop(index)
        return True

    def move(self, index: int, direction: int) -> bool:
        target = index + direction
        if not (0 <= index < self.component_count and 0 <= target < self.component_count):
            return False
        self.components[index], self.components[target] = (
            self.components[target],
            self.components[index],
        )
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "accent_color": self.accent_color,
            "components": [component.to_dict() for component in self.components],
        }
