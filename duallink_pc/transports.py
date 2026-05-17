from __future__ import annotations

import os
import shutil
import socket
import struct
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from .keymap import adb_escape_text, adb_keyevent_for_protocol
from .protocol import (
    ControlOp,
    InputEvent,
    KeyAction,
    PacketType,
    SERVICE_UUID,
    Sequence,
    frame_for_event,
    parse_control_payload,
    ping_frame,
    read_frame_from_recv,
)


class Transport(Protocol):
    name: str

    def connect(self) -> None:
        ...

    def send_event(self, event: InputEvent) -> None:
        ...

    def ping(self) -> None:
        ...

    def close(self) -> None:
        ...


class TransportError(RuntimeError):
    pass


@dataclass
class BluetoothRFCOMMTransport:
    address: str
    channel: int | None = None
    connect_timeout_s: float = 8.0
    debug: bool = False

    name: str = "bluetooth-rfcomm"

    def __post_init__(self) -> None:
        self._sock = None
        self._seq = Sequence()
        self._reader: threading.Thread | None = None
        self._closed = threading.Event()
        self.last_rtt_ms: float | None = None

    def connect(self) -> None:
        normalized = normalize_bluetooth_address(self.address)
        port = self.channel or self._discover_channel_with_pybluez(normalized)
        if port is not None:
            self._sock = self._connect_builtin_socket(normalized, port)
            self._start_reader()
            self._log(f"connected to {normalized} channel {port}")
            return

        last_error: Exception | None = None
        for candidate in self._channel_candidates():
            try:
                self._sock = self._connect_builtin_socket(normalized, candidate)
                self.channel = candidate
                self._start_reader()
                self._log(f"connected to {normalized} channel {candidate}")
                return
            except OSError as exc:
                last_error = exc

        detail = f" Last socket error: {last_error}" if last_error else ""
        raise TransportError(
            "Could not connect by Bluetooth address. Confirm the phone is paired, "
            "the Android DualLink service is started, and try entering the RFCOMM channel. "
            "If direct address mode still fails, use Windows Bluetooth COM mode."
            + detail
        ) from last_error

    def _start_reader(self) -> None:
        self._closed.clear()
        self._reader = threading.Thread(target=self._reader_loop, name="DualLink-BT-Reader", daemon=True)
        self._reader.start()

    def send_event(self, event: InputEvent) -> None:
        self._require_socket().sendall(frame_for_event(event, self._seq.next()))

    def ping(self) -> None:
        frame, _started = ping_frame(self._seq.next())
        self._require_socket().sendall(frame)

    def close(self) -> None:
        self._closed.set()
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def _connect_builtin_socket(self, address: str, channel: int):
        if not hasattr(socket, "AF_BLUETOOTH") or not hasattr(socket, "BTPROTO_RFCOMM"):
            raise TransportError("This Python build does not support built-in Bluetooth RFCOMM sockets.")
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        sock.settimeout(min(self.connect_timeout_s, 2.0))
        sock.connect((address, channel))
        sock.settimeout(1.0)
        return sock

    def _discover_channel_with_pybluez(self, address: str) -> int | None:
        try:
            import bluetooth
        except ImportError:
            return None
        try:
            services = bluetooth.find_service(uuid=SERVICE_UUID, address=address)
        except Exception as exc:
            self._log(f"SDP discovery failed: {exc}")
            return None
        if not services:
            return None
        port = int(services[0]["port"])
        self._log(f"discovered RFCOMM channel {port}")
        return port

    @staticmethod
    def _channel_candidates() -> list[int]:
        return [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, *range(13, 31)]

    def _reader_loop(self) -> None:
        sock = self._sock
        if sock is None:
            return
        while not self._closed.is_set():
            try:
                packet_type, _sequence, payload = read_frame_from_recv(sock.recv)
                if packet_type == PacketType.CONTROL:
                    op, rest = parse_control_payload(payload)
                    if op == ControlOp.PONG and len(rest) >= 8:
                        started = struct.unpack(">Q", rest[:8])[0]
                        self.last_rtt_ms = (time.perf_counter_ns() - started) / 1_000_000
                        self._log(f"rtt {self.last_rtt_ms:.2f} ms")
            except TimeoutError:
                continue
            except OSError:
                break
            except Exception as exc:
                self._log(f"reader stopped: {exc}")
                break

    def _require_socket(self):
        if self._sock is None:
            raise TransportError("Bluetooth socket is not connected")
        return self._sock

    def _log(self, message: str) -> None:
        if self.debug:
            print(f"[bt] {message}")


@dataclass
class SerialRFCOMMTransport:
    port: str
    baudrate: int = 115200
    debug: bool = False

    name: str = "serial-rfcomm"

    def __post_init__(self) -> None:
        self._serial = None
        self._seq = Sequence()

    def connect(self) -> None:
        try:
            import serial
        except ImportError as exc:
            raise TransportError("pyserial is required for COM-port RFCOMM mode") from exc
        self._serial = serial.Serial(self.port, self.baudrate, timeout=0, write_timeout=2)
        self._log(f"opened {self.port}")

    def send_event(self, event: InputEvent) -> None:
        serial = self._require_serial()
        serial.write(frame_for_event(event, self._seq.next()))
        serial.flush()

    def ping(self) -> None:
        serial = self._require_serial()
        frame, _started = ping_frame(self._seq.next())
        serial.write(frame)
        serial.flush()

    def close(self) -> None:
        serial = self._serial
        self._serial = None
        if serial is not None:
            try:
                serial.close()
            except OSError:
                pass

    def _require_serial(self):
        if self._serial is None:
            raise TransportError("serial RFCOMM port is not connected")
        return self._serial

    def _log(self, message: str) -> None:
        if self.debug:
            print(f"[serial] {message}")


@dataclass
class AdbTransport:
    adb_path: str = "adb"
    device: str | None = None
    debug: bool = False

    name: str = "adb"

    def __post_init__(self) -> None:
        self._proc: subprocess.Popen[str] | None = None

    def connect(self) -> None:
        self._verify_device()
        adb = resolve_adb_path(self.adb_path)
        args = [adb]
        if self.device:
            args.extend(["-s", self.device])
        args.append("shell")
        self._proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            creationflags=_windows_no_window_flag(),
        )
        self._log("persistent adb shell ready")

    def send_event(self, event: InputEvent) -> None:
        if event.kind == "text":
            self._write_text(event.text)
            return
        if event.kind == "clipboard":
            self._write_clipboard(event.text)
            return
        if event.kind in {"key", "media"}:
            if event.action == KeyAction.UP:
                return
            keyevent = adb_keyevent_for_protocol(event.key_id)
            if keyevent is not None:
                self._write(f"input keyevent {keyevent}\n")

    def ping(self) -> None:
        return

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.write("exit\n")
                proc.stdin.flush()
        except OSError:
            pass
        try:
            proc.terminate()
        except OSError:
            pass

    def _verify_device(self) -> None:
        adb = resolve_adb_path(self.adb_path)
        args = [adb]
        if self.device:
            args.extend(["-s", self.device])
        args.extend(["get-state"])
        try:
            completed = subprocess.run(
                args,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=_windows_no_window_flag(),
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise TransportError(
                "ADB device is not available. Run `adb devices`, check the USB debugging popup, "
                "and pass --adb-path if Android Studio installed adb somewhere custom."
            ) from exc
        if completed.stdout.strip() != "device":
            raise TransportError(f"ADB state is not device: {completed.stdout.strip()}")

    def _write_text(self, text: str) -> None:
        if not text:
            return
        # adb shell input text does not handle newlines; send those as key events.
        for chunk in text.splitlines(keepends=True):
            if chunk == "\n":
                self._write("input keyevent 66\n")
            else:
                clean = chunk.replace("\n", "")
                if clean:
                    self._write(f"input text {adb_escape_text(clean)}\n")
                if chunk.endswith("\n"):
                    self._write("input keyevent 66\n")

    def _write_clipboard(self, text: str) -> None:
        escaped = adb_escape_text(text)
        self._write(f"cmd clipboard set {escaped}\n")

    def _write(self, command: str) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.poll() is not None:
            raise TransportError("ADB shell is not running")
        self._log(command.strip())
        proc.stdin.write(command)
        proc.stdin.flush()

    def _log(self, message: str) -> None:
        if self.debug:
            print(f"[adb] {message}")


def list_adb_devices(adb_path: str = "adb") -> list[str]:
    adb = resolve_adb_path(adb_path)
    try:
        completed = subprocess.run(
            [adb, "devices", "-l"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=_windows_no_window_flag(),
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    devices: list[str] = []
    for line in completed.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def resolve_adb_path(adb_path: str = "adb") -> str:
    if adb_path and adb_path != "adb":
        return adb_path
    found = shutil.which("adb")
    if found:
        return found

    candidates: list[str] = []
    for env_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        sdk_root = os.environ.get(env_name)
        if sdk_root:
            candidates.append(os.path.join(sdk_root, "platform-tools", "adb.exe"))

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(os.path.join(local_app_data, "Android", "Sdk", "platform-tools", "adb.exe"))

    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        candidates.append(os.path.join(user_profile, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"))

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return adb_path


def discover_bluetooth_devices(duration_s: int = 8) -> list[tuple[str, str]]:
    try:
        import bluetooth
    except ImportError as exc:
        raise TransportError("PyBluez is required to scan Bluetooth devices") from exc
    found = bluetooth.discover_devices(duration=duration_s, lookup_names=True)
    return [(address, name or "Unknown device") for address, name in found]


def normalize_bluetooth_address(address: str) -> str:
    cleaned = address.strip().replace("-", "").replace(":", "").replace(" ", "")
    if len(cleaned) == 12 and all(char in "0123456789abcdefABCDEF" for char in cleaned):
        return ":".join(cleaned[index : index + 2] for index in range(0, 12, 2)).upper()
    return address.strip().upper()


def _windows_no_window_flag() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)
