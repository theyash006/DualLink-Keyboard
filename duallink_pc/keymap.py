from __future__ import annotations

import re
from dataclasses import dataclass

from .protocol import KeyAction


class ProtocolKey:
    BACKSPACE = 8
    TAB = 9
    ENTER = 13
    ESCAPE = 27
    SPACE = 32

    ARROW_LEFT = 1000
    ARROW_RIGHT = 1001
    ARROW_UP = 1002
    ARROW_DOWN = 1003
    HOME = 1004
    END = 1005
    PAGE_UP = 1006
    PAGE_DOWN = 1007
    DELETE = 1008
    INSERT = 1009
    CAPS_LOCK = 1010
    NUM_LOCK = 1011
    SCROLL_LOCK = 1012
    PRINT_SCREEN = 1013
    PAUSE = 1014
    MENU = 1015

    CTRL = 1100
    SHIFT = 1101
    ALT = 1102
    META = 1103

    MEDIA_PLAY_PAUSE = 1200
    MEDIA_NEXT = 1201
    MEDIA_PREVIOUS = 1202
    MEDIA_STOP = 1203
    VOLUME_UP = 1204
    VOLUME_DOWN = 1205
    VOLUME_MUTE = 1206

    F1 = 1301
    F2 = 1302
    F3 = 1303
    F4 = 1304
    F5 = 1305
    F6 = 1306
    F7 = 1307
    F8 = 1308
    F9 = 1309
    F10 = 1310
    F11 = 1311
    F12 = 1312


class ProtocolModifier:
    SHIFT = 1
    CTRL = 1 << 1
    ALT = 1 << 2
    META = 1 << 3


ADB_KEYEVENTS = {
    ProtocolKey.BACKSPACE: 67,
    ProtocolKey.TAB: 61,
    ProtocolKey.ENTER: 66,
    ProtocolKey.ESCAPE: 111,
    ProtocolKey.SPACE: 62,
    ProtocolKey.ARROW_LEFT: 21,
    ProtocolKey.ARROW_RIGHT: 22,
    ProtocolKey.ARROW_UP: 19,
    ProtocolKey.ARROW_DOWN: 20,
    ProtocolKey.HOME: 122,
    ProtocolKey.END: 123,
    ProtocolKey.PAGE_UP: 92,
    ProtocolKey.PAGE_DOWN: 93,
    ProtocolKey.DELETE: 112,
    ProtocolKey.INSERT: 124,
    ProtocolKey.CAPS_LOCK: 115,
    ProtocolKey.SCROLL_LOCK: 116,
    ProtocolKey.PRINT_SCREEN: 120,
    ProtocolKey.PAUSE: 121,
    ProtocolKey.MENU: 82,
    ProtocolKey.NUM_LOCK: 143,
    ProtocolKey.MEDIA_PLAY_PAUSE: 85,
    ProtocolKey.MEDIA_NEXT: 87,
    ProtocolKey.MEDIA_PREVIOUS: 88,
    ProtocolKey.MEDIA_STOP: 86,
    ProtocolKey.VOLUME_UP: 24,
    ProtocolKey.VOLUME_DOWN: 25,
    ProtocolKey.VOLUME_MUTE: 164,
    ProtocolKey.F1: 131,
    ProtocolKey.F2: 132,
    ProtocolKey.F3: 133,
    ProtocolKey.F4: 134,
    ProtocolKey.F5: 135,
    ProtocolKey.F6: 136,
    ProtocolKey.F7: 137,
    ProtocolKey.F8: 138,
    ProtocolKey.F9: 139,
    ProtocolKey.F10: 140,
    ProtocolKey.F11: 141,
    ProtocolKey.F12: 142,
    ord(","): 55,
    ord("."): 56,
    ord("-"): 69,
    ord("="): 70,
    ord("["): 71,
    ord("]"): 72,
    ord("\\"): 73,
    ord(";"): 74,
    ord("'"): 75,
    ord("/"): 76,
    ord("`"): 68,
}


@dataclass(frozen=True)
class KeyDecision:
    key_id: int
    is_modifier: bool = False
    is_media: bool = False


CONTROL_CHAR_TO_KEY = {chr(index): chr(ord("a") + index - 1) for index in range(1, 27)}

SHIFTED_PRINTABLE_TO_BASE = {
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "(": "9",
    ")": "0",
    "_": "-",
    "+": "=",
    "{": "[",
    "}": "]",
    "|": "\\",
    ":": ";",
    '"': "'",
    "<": ",",
    ">": ".",
    "?": "/",
    "~": "`",
}

PRINTABLE_PROTOCOL_KEYS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "`-=[]\\;',./"
    "~!@#$%^&*()_+{}|:\"<>?"
)


def modifier_mask(pressed_modifiers: set[str]) -> int:
    mask = 0
    if "shift" in pressed_modifiers:
        mask |= ProtocolModifier.SHIFT
    if "ctrl" in pressed_modifiers:
        mask |= ProtocolModifier.CTRL
    if "alt" in pressed_modifiers:
        mask |= ProtocolModifier.ALT
    if "meta" in pressed_modifiers:
        mask |= ProtocolModifier.META
    return mask


def key_name(key) -> str:
    name = getattr(key, "name", None)
    if name:
        return name
    char = getattr(key, "char", None)
    if char in CONTROL_CHAR_TO_KEY:
        return CONTROL_CHAR_TO_KEY[char]
    return char or str(key)


def key_decision(key) -> KeyDecision | None:
    try:
        from pynput import keyboard
    except ImportError as exc:
        raise RuntimeError("pynput is required for keyboard capture. Install pc/requirements.txt") from exc

    mapping = {}
    for attr, key_id in {
        "backspace": ProtocolKey.BACKSPACE,
        "tab": ProtocolKey.TAB,
        "enter": ProtocolKey.ENTER,
        "esc": ProtocolKey.ESCAPE,
        "space": ProtocolKey.SPACE,
        "left": ProtocolKey.ARROW_LEFT,
        "right": ProtocolKey.ARROW_RIGHT,
        "up": ProtocolKey.ARROW_UP,
        "down": ProtocolKey.ARROW_DOWN,
        "home": ProtocolKey.HOME,
        "end": ProtocolKey.END,
        "page_up": ProtocolKey.PAGE_UP,
        "page_down": ProtocolKey.PAGE_DOWN,
        "delete": ProtocolKey.DELETE,
        "insert": ProtocolKey.INSERT,
        "caps_lock": ProtocolKey.CAPS_LOCK,
        "num_lock": ProtocolKey.NUM_LOCK,
        "scroll_lock": ProtocolKey.SCROLL_LOCK,
        "print_screen": ProtocolKey.PRINT_SCREEN,
        "pause": ProtocolKey.PAUSE,
        "menu": ProtocolKey.MENU,
        "f1": ProtocolKey.F1,
        "f2": ProtocolKey.F2,
        "f3": ProtocolKey.F3,
        "f4": ProtocolKey.F4,
        "f5": ProtocolKey.F5,
        "f6": ProtocolKey.F6,
        "f7": ProtocolKey.F7,
        "f8": ProtocolKey.F8,
        "f9": ProtocolKey.F9,
        "f10": ProtocolKey.F10,
        "f11": ProtocolKey.F11,
        "f12": ProtocolKey.F12,
    }.items():
        if hasattr(keyboard.Key, attr):
            mapping[getattr(keyboard.Key, attr)] = key_id

    modifier_mapping = {}
    for attr, key_id in {
        "shift": ProtocolKey.SHIFT,
        "shift_l": ProtocolKey.SHIFT,
        "shift_r": ProtocolKey.SHIFT,
        "ctrl": ProtocolKey.CTRL,
        "ctrl_l": ProtocolKey.CTRL,
        "ctrl_r": ProtocolKey.CTRL,
        "alt": ProtocolKey.ALT,
        "alt_l": ProtocolKey.ALT,
        "alt_r": ProtocolKey.ALT,
        "cmd": ProtocolKey.META,
        "cmd_l": ProtocolKey.META,
        "cmd_r": ProtocolKey.META,
    }.items():
        if hasattr(keyboard.Key, attr):
            modifier_mapping[getattr(keyboard.Key, attr)] = key_id
    media_mapping = {}
    for attr, key_id in {
        "media_play_pause": ProtocolKey.MEDIA_PLAY_PAUSE,
        "media_next": ProtocolKey.MEDIA_NEXT,
        "media_previous": ProtocolKey.MEDIA_PREVIOUS,
        "media_stop": ProtocolKey.MEDIA_STOP,
        "media_volume_up": ProtocolKey.VOLUME_UP,
        "media_volume_down": ProtocolKey.VOLUME_DOWN,
        "media_volume_mute": ProtocolKey.VOLUME_MUTE,
    }.items():
        if hasattr(keyboard.Key, attr):
            media_mapping[getattr(keyboard.Key, attr)] = key_id

    if key in modifier_mapping:
        return KeyDecision(modifier_mapping[key], is_modifier=True)
    if key in media_mapping:
        return KeyDecision(media_mapping[key], is_media=True)
    if key in mapping:
        return KeyDecision(mapping[key])

    char = getattr(key, "char", None)
    if char in CONTROL_CHAR_TO_KEY:
        char = CONTROL_CHAR_TO_KEY[char]
    if char and len(char) == 1 and char in PRINTABLE_PROTOCOL_KEYS:
        base = SHIFTED_PRINTABLE_TO_BASE.get(char, char)
        if re.match(r"[A-Za-z]", base):
            return KeyDecision(ord(base.upper()))
        return KeyDecision(ord(base))
    return None


def modifier_name_for_key(key) -> str | None:
    name = key_name(key).lower()
    if name.startswith("shift"):
        return "shift"
    if name.startswith("ctrl"):
        return "ctrl"
    if name.startswith("alt"):
        return "alt"
    if name.startswith("cmd") or name.startswith("meta") or name.startswith("win"):
        return "meta"
    return None


def should_send_char_text(char: str | None, modifiers: set[str]) -> bool:
    if not char:
        return False
    if len(char) != 1:
        return False
    return "ctrl" not in modifiers and "alt" not in modifiers and "meta" not in modifiers


def adb_keyevent_for_protocol(key_id: int) -> int | None:
    if key_id in ADB_KEYEVENTS:
        return ADB_KEYEVENTS[key_id]
    if 65 <= key_id <= 90:
        return 29 + (key_id - 65)
    if 48 <= key_id <= 57:
        return 7 + (key_id - 48)
    return None


def adb_escape_text(text: str) -> str:
    result: list[str] = []
    for char in text:
        if char == " ":
            result.append("%s")
        elif char == "\n":
            result.append("\\n")
        elif char in {'"', "'", "\\", "&", "|", ";", "<", ">", "(", ")", "$", "`", "*", "!", "#"}:
            result.append("\\" + char)
        else:
            result.append(char)
    return "".join(result)


def event_action_for_capture(gaming_mode: bool, pressed: bool) -> KeyAction:
    if not gaming_mode:
        return KeyAction.PRESS
    return KeyAction.DOWN if pressed else KeyAction.UP
