from __future__ import annotations

import json
from pathlib import Path

from .keymap import key_name


class MacroEngine:
    def __init__(self, macros: dict[str, str] | None = None) -> None:
        self._macros = {normalize_combo(combo): text for combo, text in (macros or {}).items()}

    @classmethod
    def from_file(cls, path: str | None) -> "MacroEngine":
        if not path:
            return cls()
        macro_path = Path(path)
        if not macro_path.exists():
            return cls()
        with macro_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("macro file must be a JSON object mapping hotkeys to text")
        return cls({str(key): str(value) for key, value in data.items()})

    def match(self, modifiers: set[str], key) -> str | None:
        token = normalize_key_token(key_name(key))
        combo = normalize_combo("+".join([*sorted(modifiers), token]))
        return self._macros.get(combo)


def normalize_combo(combo: str) -> str:
    tokens = [normalize_key_token(token) for token in combo.split("+") if token.strip()]
    modifiers = [token for token in ("ctrl", "alt", "shift", "meta") if token in tokens]
    non_modifiers = [token for token in tokens if token not in {"ctrl", "alt", "shift", "meta"}]
    return "+".join([*modifiers, *non_modifiers])


def normalize_key_token(token: str) -> str:
    normalized = token.strip().lower()
    aliases = {
        "control": "ctrl",
        "cmd": "meta",
        "win": "meta",
        "windows": "meta",
        "return": "enter",
        "escape": "esc",
        "delete": "del",
        "pageup": "page_up",
        "pagedown": "page_down",
    }
    return aliases.get(normalized, normalized)

