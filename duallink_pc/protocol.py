from __future__ import annotations

import enum
import struct
import time
from dataclasses import dataclass


SERVICE_UUID = "7fae5ac7-55d2-4b91-9d88-8fd82c20d6e1"
SERVICE_NAME = "DualLink Keyboard RFCOMM"

MAGIC = b"DK"
VERSION = 1
HEADER = struct.Struct(">2sBBBHQH")
MAX_PAYLOAD = 4096


class PacketType(enum.IntEnum):
    TEXT = 1
    KEY = 2
    MEDIA = 3
    CONTROL = 4
    POINTER = 5
    CLIPBOARD = 6
    MACRO = 7


class KeyAction(enum.IntEnum):
    PRESS = 0
    DOWN = 1
    UP = 2


class ControlOp(enum.IntEnum):
    PING = 1
    PONG = 2
    HELLO = 3
    DISCONNECT = 4


@dataclass(frozen=True)
class InputEvent:
    kind: str
    text: str = ""
    key_id: int = 0
    action: KeyAction = KeyAction.PRESS
    modifiers: int = 0
    created_ns: int = 0

    @staticmethod
    def text_event(text: str) -> "InputEvent":
        return InputEvent(kind="text", text=text, created_ns=time.perf_counter_ns())

    @staticmethod
    def key_event(key_id: int, action: KeyAction, modifiers: int = 0) -> "InputEvent":
        return InputEvent(
            kind="key",
            key_id=key_id,
            action=action,
            modifiers=modifiers,
            created_ns=time.perf_counter_ns(),
        )

    @staticmethod
    def media_event(key_id: int, action: KeyAction = KeyAction.PRESS) -> "InputEvent":
        return InputEvent(
            kind="media",
            key_id=key_id,
            action=action,
            created_ns=time.perf_counter_ns(),
        )

    @staticmethod
    def clipboard_event(text: str) -> "InputEvent":
        return InputEvent(kind="clipboard", text=text, created_ns=time.perf_counter_ns())


class Sequence:
    def __init__(self) -> None:
        self._value = 1

    def next(self) -> int:
        value = self._value & 0xFFFF
        self._value = (self._value + 1) & 0xFFFF
        return value


def build_frame(packet_type: PacketType, payload: bytes, sequence: int, flags: int = 0) -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"payload too large: {len(payload)}")
    timestamp = time.perf_counter_ns()
    return HEADER.pack(MAGIC, VERSION, int(packet_type), flags, sequence, timestamp, len(payload)) + payload


def frame_for_event(event: InputEvent, sequence: int) -> bytes:
    if event.kind == "text":
        return build_frame(PacketType.TEXT, event.text.encode("utf-8"), sequence)
    if event.kind == "clipboard":
        return build_frame(PacketType.CLIPBOARD, event.text.encode("utf-8"), sequence)
    if event.kind == "media":
        payload = struct.pack(">HBB", event.key_id, int(event.action), event.modifiers & 0xFF)
        return build_frame(PacketType.MEDIA, payload, sequence)
    if event.kind == "key":
        payload = struct.pack(">HBB", event.key_id, int(event.action), event.modifiers & 0xFF)
        return build_frame(PacketType.KEY, payload, sequence)
    raise ValueError(f"unsupported input event kind: {event.kind}")


def ping_frame(sequence: int) -> tuple[bytes, int]:
    started_ns = time.perf_counter_ns()
    payload = struct.pack(">BQ", int(ControlOp.PING), started_ns)
    return build_frame(PacketType.CONTROL, payload, sequence), started_ns


def read_frame_from_recv(recv) -> tuple[PacketType, int, bytes]:
    header = _read_exact(recv, HEADER.size)
    magic, version, packet_type, _flags, sequence, _timestamp, payload_len = HEADER.unpack(header)
    if magic != MAGIC:
        raise ValueError("bad frame magic")
    if version != VERSION:
        raise ValueError(f"bad protocol version: {version}")
    if payload_len > MAX_PAYLOAD:
        raise ValueError(f"payload too large: {payload_len}")
    payload = _read_exact(recv, payload_len) if payload_len else b""
    return PacketType(packet_type), sequence, payload


def parse_control_payload(payload: bytes) -> tuple[ControlOp | None, bytes]:
    if not payload:
        return None, b""
    try:
        return ControlOp(payload[0]), payload[1:]
    except ValueError:
        return None, payload[1:]


def _read_exact(recv, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = recv(remaining)
        if not chunk:
            raise ConnectionError("socket closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)

