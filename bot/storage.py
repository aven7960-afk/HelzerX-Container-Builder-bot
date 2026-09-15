from __future__ import annotations

import json
from pathlib import Path

from bot.builder.state import BuilderState


class TemplateStore:
    """Small JSON-backed per-user template store."""

    def __init__(self, path: str = "data/templates.json") -> None:
        self.path = Path(path)

    def _read(self) -> dict:
        if not self.path.exists(): return {}
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError): return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)

    def save(self, owner_id: int, name: str, state: BuilderState) -> None:
        data = self._read()
        data.setdefault(str(owner_id), {})[name] = state.to_dict()
        self._write(data)

    def load(self, owner_id: int, name: str) -> dict | None:
        return self._read().get(str(owner_id), {}).get(name)

    def names(self, owner_id: int) -> list[str]:
        return sorted(self._read().get(str(owner_id), {}).keys())

    def delete(self, owner_id: int, name: str) -> bool:
        data = self._read(); bucket = data.get(str(owner_id), {})
        if name not in bucket: return False
        del bucket[name]; self._write(data); return True

    def duplicate(self, owner_id: int, source: str, target: str) -> bool:
        data = self._read(); bucket = data.get(str(owner_id), {})
        if source not in bucket or not target or target in bucket: return False
        bucket[target] = json.loads(json.dumps(bucket[source], ensure_ascii=False))
        self._write(data); return True
