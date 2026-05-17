from __future__ import annotations

import threading
from dataclasses import dataclass

from .clipboard_sync import read_clipboard_text
from .keymap import (
    event_action_for_capture,
    key_decision,
    key_name,
    modifier_mask,
    modifier_name_for_key,
    should_send_char_text,
)
from .macros import MacroEngine, normalize_combo
from .protocol import InputEvent, KeyAction
from .sender import LowLatencySender


@dataclass
class CaptureConfig:
    gaming_mode: bool = False
    suppress_local: bool = False
    clipboard_hotkey: str | None = "ctrl+alt+v"
    debug: bool = False


class KeyboardCapture:
    def __init__(self, sender: LowLatencySender, macros: MacroEngine, config: CaptureConfig) -> None:
        self._sender = sender
        self._macros = macros
        self._config = config
        self._modifiers: set[str] = set()
        self._down_tokens: set[str] = set()
        self._listener = None
        self._stopped = threading.Event()

    def start(self) -> None:
        try:
            from pynput import keyboard
        except ImportError as exc:
            raise RuntimeError("pynput is required. Install with: pip install -r pc/requirements.txt") from exc

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=self._config.suppress_local,
        )
        self._listener.start()

    def join(self) -> None:
        if self._listener is not None:
            self._listener.join()

    def stop(self) -> None:
        self._stopped.set()
        if self._listener is not None:
            self._listener.stop()

    def _on_press(self, key) -> None:
        modifier = modifier_name_for_key(key)
        if modifier:
            self._modifiers.add(modifier)
            if self._config.gaming_mode:
                self._send_key_decision(key, pressed=True)
            return

        if self._handle_clipboard_hotkey(key):
            return

        macro_text = self._macros.match(self._modifiers, key)
        if macro_text is not None:
            self._sender.send(InputEvent.text_event(macro_text))
            self._log(f"macro {key_name(key)} -> {len(macro_text)} chars")
            return

        char = getattr(key, "char", None)
        if not self._config.gaming_mode and should_send_char_text(char, self._modifiers):
            self._sender.send(InputEvent.text_event(char))
            return

        self._send_key_decision(key, pressed=True)

    def _on_release(self, key) -> None:
        if self._config.gaming_mode:
            self._send_key_decision(key, pressed=False)
        modifier = modifier_name_for_key(key)
        if modifier:
            self._modifiers.discard(modifier)

    def _send_key_decision(self, key, *, pressed: bool) -> None:
        decision = key_decision(key)
        if decision is None:
            return
        token = key_name(key)
        if self._config.gaming_mode and pressed:
            if token in self._down_tokens:
                return
            self._down_tokens.add(token)
        if self._config.gaming_mode and not pressed:
            self._down_tokens.discard(token)

        action = event_action_for_capture(self._config.gaming_mode, pressed)
        if not self._config.gaming_mode and action != KeyAction.PRESS:
            return
        modifiers = modifier_mask(self._modifiers)
        event = (
            InputEvent.media_event(decision.key_id, action)
            if decision.is_media
            else InputEvent.key_event(decision.key_id, action, modifiers)
        )
        self._sender.send(event)

    def _handle_clipboard_hotkey(self, key) -> bool:
        if not self._config.clipboard_hotkey:
            return False
        combo = normalize_combo("+".join([*sorted(self._modifiers), key_name(key)]))
        if combo != normalize_combo(self._config.clipboard_hotkey):
            return False
        text = read_clipboard_text()
        if text:
            self._sender.send(InputEvent.clipboard_event(text))
            self._log(f"clipboard sync {len(text)} chars")
        return True

    def _log(self, message: str) -> None:
        if self._config.debug:
            print(f"[keys] {message}")

