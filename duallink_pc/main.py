from __future__ import annotations

import argparse
import sys
import time
from typing import Callable

from .keyboard_capture import CaptureConfig, KeyboardCapture
from .macros import MacroEngine
from .sender import LowLatencySender
from .transports import (
    AdbTransport,
    BluetoothRFCOMMTransport,
    SerialRFCOMMTransport,
    Transport,
    TransportError,
    discover_bluetooth_devices,
    list_adb_devices,
)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_adb:
        print_adb_devices(args.adb_path)
        return 0
    if args.list_bt:
        print_bluetooth_devices()
        return 0

    mode = args.mode or choose_mode()
    try:
        factory = transport_factory(mode, args)
    except TransportError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    macros = MacroEngine.from_file(args.macros)
    sender = LowLatencySender(factory, debug=args.debug)
    capture = KeyboardCapture(
        sender,
        macros,
        CaptureConfig(
            gaming_mode=args.gaming,
            suppress_local=args.suppress_local,
            clipboard_hotkey=args.clipboard_hotkey,
            debug=args.debug,
        ),
    )

    print("DualLink Keyboard PC sender")
    print(f"Mode: {mode}")
    print("Press Ctrl+C in this terminal to stop.")
    if args.suppress_local:
        print("Local keyboard suppression is enabled.")
    if args.gaming:
        print("Gaming mode is enabled: down/up events are sent for mapped keys.")

    sender.start()
    try:
        capture.start()
        status_loop(sender)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        capture.stop()
        sender.stop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DualLink Keyboard Windows sender")
    parser.add_argument("--mode", choices=["bluetooth", "serial", "adb"], help="Transport mode")
    parser.add_argument("--address", help="Android Bluetooth MAC address for RFCOMM mode")
    parser.add_argument("--channel", type=int, help="RFCOMM channel; omit for SDP discovery")
    parser.add_argument("--serial-port", help="Windows outgoing Bluetooth COM port, for example COM7")
    parser.add_argument("--adb-path", default="adb", help="Path to adb executable")
    parser.add_argument("--adb-device", help="ADB serial from `adb devices -l`")
    parser.add_argument("--gaming", action="store_true", help="Send key down/up packets instead of text commits")
    parser.add_argument("--suppress-local", action="store_true", help="Prevent keystrokes from reaching Windows apps")
    parser.add_argument("--clipboard-hotkey", default="ctrl+alt+v", help="Hotkey that sends PC clipboard to Android")
    parser.add_argument("--macros", help="JSON file mapping hotkeys such as ctrl+alt+h to text")
    parser.add_argument("--list-adb", action="store_true", help="List connected ADB devices")
    parser.add_argument("--list-bt", action="store_true", help="Scan Bluetooth devices with PyBluez")
    parser.add_argument("--debug", action="store_true", help="Verbose transport logging")
    return parser


def transport_factory(mode: str, args) -> Callable[[], Transport]:
    if mode == "bluetooth":
        address = args.address or prompt("Android Bluetooth address")
        if not address:
            raise TransportError("Bluetooth mode requires --address")
        return lambda: BluetoothRFCOMMTransport(address=address, channel=args.channel, debug=args.debug)
    if mode == "serial":
        port = args.serial_port or prompt("Outgoing Bluetooth COM port")
        if not port:
            raise TransportError("serial mode requires --serial-port")
        return lambda: SerialRFCOMMTransport(port=port, debug=args.debug)
    if mode == "adb":
        device = args.adb_device or auto_adb_device(args.adb_path)
        return lambda: AdbTransport(adb_path=args.adb_path, device=device, debug=args.debug)
    raise TransportError(f"unknown mode: {mode}")


def auto_adb_device(adb_path: str) -> str | None:
    devices = list_adb_devices(adb_path)
    if len(devices) == 1:
        print(f"Using ADB device {devices[0]}")
        return devices[0]
    if len(devices) > 1:
        print("Multiple ADB devices found:")
        for index, device in enumerate(devices, start=1):
            print(f"  {index}. {device}")
        selected = prompt("Select device number")
        try:
            return devices[int(selected) - 1]
        except (ValueError, IndexError):
            raise TransportError("invalid ADB device selection")
    return None


def choose_mode() -> str:
    print("Choose transport:")
    print("  1. Bluetooth RFCOMM")
    print("  2. USB ADB")
    print("  3. Bluetooth COM port")
    selected = prompt("Mode")
    return {"1": "bluetooth", "2": "adb", "3": "serial"}.get(selected, selected)


def print_adb_devices(adb_path: str) -> None:
    devices = list_adb_devices(adb_path)
    if not devices:
        print("No authorized ADB devices found.")
        return
    for device in devices:
        print(device)


def print_bluetooth_devices() -> None:
    try:
        for address, name in discover_bluetooth_devices():
            print(f"{address}  {name}")
    except TransportError as exc:
        print(exc, file=sys.stderr)


def status_loop(sender: LowLatencySender) -> None:
    last_sent = -1
    while True:
        time.sleep(1)
        stats = sender.stats
        if stats.sent != last_sent or stats.last_error:
            state = "connected" if stats.connected else "connecting"
            print(
                f"[{state}] sent={stats.sent} queued={stats.queued} "
                f"dropped={stats.dropped} reconnects={stats.reconnects} {stats.last_error}"
            )
            last_sent = stats.sent


def prompt(label: str) -> str:
    return input(f"{label}: ").strip()


if __name__ == "__main__":
    raise SystemExit(main())

