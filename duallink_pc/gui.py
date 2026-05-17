from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .keyboard_capture import CaptureConfig, KeyboardCapture
from .macros import MacroEngine
from .sender import LowLatencySender
from .transports import (
    AdbTransport,
    BluetoothRFCOMMTransport,
    SerialRFCOMMTransport,
    Transport,
    list_adb_devices,
    normalize_bluetooth_address,
    resolve_adb_path,
)


class DualLinkPcApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DualLink Keyboard PC")
        self.geometry("920x620")
        self.minsize(820, 560)
        self.configure(bg="#071018")

        self.sender: LowLatencySender | None = None
        self.capture: KeyboardCapture | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.running = False

        self.mode_var = tk.StringVar(value="adb")
        self.adb_path_var = tk.StringVar(value=resolve_adb_path("adb"))
        self.adb_device_var = tk.StringVar()
        self.bluetooth_address_var = tk.StringVar()
        self.bluetooth_channel_var = tk.StringVar()
        self.serial_port_var = tk.StringVar(value="COM7")
        self.suppress_var = tk.BooleanVar(value=False)
        self.gaming_var = tk.BooleanVar(value=False)
        self.clipboard_hotkey_var = tk.StringVar(value="ctrl+alt+v")
        self.macros_path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Stopped")
        self.stats_var = tk.StringVar(value="sent=0 queued=0 dropped=0 reconnects=0")
        self._last_error_logged = ""

        self._style()
        self._build_ui()
        self._poll_ui()

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#071018")
        style.configure("Panel.TFrame", background="#111c29", relief="flat")
        style.configure("TLabel", background="#071018", foreground="#e9f2ff", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background="#071018", foreground="#9cafc4", font=("Segoe UI", 9))
        style.configure("Panel.TLabel", background="#111c29", foreground="#e9f2ff", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#071018", foreground="#f7fbff", font=("Segoe UI", 22, "bold"))
        style.configure("Status.TLabel", background="#111c29", foreground="#2ee6a6", font=("Segoe UI", 12, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.configure("Accent.TButton", background="#2ee6a6", foreground="#06120f", font=("Segoe UI", 10, "bold"))
        style.configure("Danger.TButton", background="#ff647c", foreground="#20060b", font=("Segoe UI", 10, "bold"))
        style.configure("TCheckbutton", background="#111c29", foreground="#e9f2ff", font=("Segoe UI", 10))
        style.configure("TRadiobutton", background="#111c29", foreground="#e9f2ff", font=("Segoe UI", 10))
        style.configure("TEntry", fieldbackground="#0b1420", foreground="#e9f2ff", insertcolor="#e9f2ff")
        style.configure("TCombobox", fieldbackground="#0b1420", foreground="#e9f2ff")

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X)
        ttk.Label(header, text="DualLink Keyboard PC", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, text="Windows sender app", style="Muted.TLabel").pack(side=tk.LEFT, padx=(14, 0), pady=(12, 0))

        main = ttk.Frame(root)
        main.pack(fill=tk.BOTH, expand=True, pady=(18, 0))

        left_shell = ttk.Frame(main, style="Panel.TFrame")
        left_shell.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        left_shell.pack_propagate(False)
        left_shell.configure(width=590)
        left = self._build_scrollable_panel(left_shell)
        right = ttk.Frame(main, style="Panel.TFrame", padding=16)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(14, 0))

        self._build_control_panel(left)
        self._build_connection_panel(left)
        self._build_options_panel(left)
        self._build_log_panel(right)

    def _build_scrollable_panel(self, parent: ttk.Frame) -> ttk.Frame:
        container = ttk.Frame(parent, style="Panel.TFrame")
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(
            container,
            bg="#111c29",
            highlightthickness=0,
            borderwidth=0,
            width=570,
        )
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        content = ttk.Frame(canvas, style="Panel.TFrame", padding=16)
        window_id = canvas.create_window((0, 0), window=content, anchor=tk.NW)

        def update_scroll_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def bind_wheel(_event=None) -> None:
            canvas.bind_all("<MouseWheel>", on_mouse_wheel)

        def unbind_wheel(_event=None) -> None:
            canvas.unbind_all("<MouseWheel>")

        def on_mouse_wheel(event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        canvas.bind("<Enter>", bind_wheel)
        canvas.bind("<Leave>", unbind_wheel)
        return content

    def _build_connection_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Connection", style="Panel.TLabel", font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)

        mode_box = ttk.Frame(parent, style="Panel.TFrame")
        mode_box.pack(fill=tk.X, pady=(10, 4))
        ttk.Radiobutton(mode_box, text="USB ADB", variable=self.mode_var, value="adb").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_box, text="Bluetooth Address", variable=self.mode_var, value="bluetooth").pack(side=tk.LEFT, padx=(14, 0))
        ttk.Radiobutton(mode_box, text="Bluetooth COM", variable=self.mode_var, value="serial").pack(side=tk.LEFT, padx=(14, 0))

        ttk.Label(parent, text="ADB path", style="Panel.TLabel").pack(anchor=tk.W, pady=(12, 3))
        adb_row = ttk.Frame(parent, style="Panel.TFrame")
        adb_row.pack(fill=tk.X)
        ttk.Entry(adb_row, textvariable=self.adb_path_var, width=38).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(adb_row, text="Browse", command=self._browse_adb).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(parent, text="ADB device", style="Panel.TLabel").pack(anchor=tk.W, pady=(12, 3))
        device_row = ttk.Frame(parent, style="Panel.TFrame")
        device_row.pack(fill=tk.X)
        self.adb_device_combo = ttk.Combobox(device_row, textvariable=self.adb_device_var, width=30)
        self.adb_device_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(device_row, text="Refresh", command=self._refresh_adb_devices).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(parent, text="Bluetooth address", style="Panel.TLabel").pack(anchor=tk.W, pady=(12, 3))
        ttk.Entry(parent, textvariable=self.bluetooth_address_var, width=42).pack(fill=tk.X)

        ttk.Label(parent, text="RFCOMM channel, optional", style="Panel.TLabel").pack(anchor=tk.W, pady=(12, 3))
        ttk.Entry(parent, textvariable=self.bluetooth_channel_var, width=42).pack(fill=tk.X)
        ttk.Label(
            parent,
            text="Example address: AA:BB:CC:DD:EE:FF. Leave channel empty for auto-scan.",
            style="Panel.TLabel",
        ).pack(anchor=tk.W, pady=(6, 0))
        ttk.Button(parent, text="Test Bluetooth Address", command=self._test_bluetooth_address).pack(fill=tk.X, pady=(8, 0))

        ttk.Label(parent, text="Bluetooth COM port", style="Panel.TLabel").pack(anchor=tk.W, pady=(12, 3))
        ttk.Entry(parent, textvariable=self.serial_port_var, width=42).pack(fill=tk.X)
        ttk.Label(
            parent,
            text="Use Windows Bluetooth settings to create an outgoing COM port.",
            style="Panel.TLabel",
        ).pack(anchor=tk.W, pady=(6, 0))

    def _build_options_panel(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent).pack(fill=tk.X, pady=16)
        ttk.Label(parent, text="Options", style="Panel.TLabel", font=("Segoe UI", 14, "bold")).pack(anchor=tk.W)
        ttk.Checkbutton(parent, text="Suppress typing on Windows", variable=self.suppress_var).pack(anchor=tk.W, pady=(10, 0))
        ttk.Checkbutton(parent, text="Gaming mode", variable=self.gaming_var).pack(anchor=tk.W, pady=(6, 0))

        ttk.Label(parent, text="Clipboard hotkey", style="Panel.TLabel").pack(anchor=tk.W, pady=(12, 3))
        ttk.Entry(parent, textvariable=self.clipboard_hotkey_var, width=42).pack(fill=tk.X)

        ttk.Label(parent, text="Macros JSON file", style="Panel.TLabel").pack(anchor=tk.W, pady=(12, 3))
        macro_row = ttk.Frame(parent, style="Panel.TFrame")
        macro_row.pack(fill=tk.X)
        ttk.Entry(macro_row, textvariable=self.macros_path_var, width=34).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(macro_row, text="Browse", command=self._browse_macros).pack(side=tk.LEFT, padx=(8, 0))

    def _build_control_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, textvariable=self.status_var, style="Status.TLabel").pack(anchor=tk.W)
        ttk.Label(parent, textvariable=self.stats_var, style="Panel.TLabel").pack(anchor=tk.W, pady=(4, 10))

        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill=tk.X)
        self.start_button = ttk.Button(row, text="Start", style="Accent.TButton", command=self._start)
        self.start_button.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.stop_button = ttk.Button(row, text="Stop", style="Danger.TButton", command=self._stop, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

    def _build_log_panel(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent, style="Panel.TFrame")
        top.pack(fill=tk.X)
        ttk.Label(top, text="Live Log", style="Panel.TLabel", font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        ttk.Button(top, text="Clear", command=lambda: self.log_text.delete("1.0", tk.END)).pack(side=tk.RIGHT)

        self.log_text = tk.Text(
            parent,
            bg="#071018",
            fg="#d8e8ff",
            insertbackground="#d8e8ff",
            relief=tk.FLAT,
            height=22,
            wrap=tk.WORD,
            font=("Consolas", 10),
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self._log("Open the Android app, tap Start, then start this PC app.")
        self._log("ADB mode is recommended first because your phone is already connected by USB.")

    def _browse_adb(self) -> None:
        path = filedialog.askopenfilename(
            title="Select adb.exe",
            filetypes=[("ADB executable", "adb.exe"), ("Executables", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.adb_path_var.set(path)

    def _browse_macros(self) -> None:
        path = filedialog.askopenfilename(
            title="Select macros JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.macros_path_var.set(path)

    def _refresh_adb_devices(self) -> None:
        adb_path = self.adb_path_var.get().strip() or "adb"
        self._log("Refreshing ADB devices...")
        devices = list_adb_devices(adb_path)
        self.adb_device_combo["values"] = devices
        if len(devices) == 1:
            self.adb_device_var.set(devices[0])
            self._log(f"Found ADB device: {devices[0]}")
        elif devices:
            self._log(f"Found {len(devices)} ADB devices. Select one.")
        else:
            self._log("No ADB devices found. Check USB debugging authorization on the phone.")

    def _test_bluetooth_address(self) -> None:
        address = normalize_bluetooth_address(self.bluetooth_address_var.get())
        if not address:
            messagebox.showwarning("DualLink Keyboard PC", "Enter the phone Bluetooth address first.")
            return
        try:
            channel = self._bluetooth_channel_or_none()
        except ValueError as exc:
            messagebox.showwarning("DualLink Keyboard PC", str(exc))
            return

        def worker() -> None:
            transport = BluetoothRFCOMMTransport(address=address, channel=channel, debug=False)
            self._log(f"Testing Bluetooth address {address}...")
            try:
                transport.connect()
                transport.ping()
                self._log("Bluetooth address test connected successfully. This test disconnects immediately.")
                self._log("Click Start to keep the phone connected and send keyboard input.")
            except Exception as exc:
                self._log(f"Bluetooth address test failed: {exc}")
            finally:
                transport.close()

        threading.Thread(target=worker, name="DualLink-Bluetooth-Test", daemon=True).start()

    def _start(self) -> None:
        if self.running:
            return
        try:
            factory = self._transport_factory()
            macros = MacroEngine.from_file(self.macros_path_var.get().strip() or None)
            self.sender = LowLatencySender(factory, debug=False)
            self.capture = KeyboardCapture(
                self.sender,
                macros,
                CaptureConfig(
                    gaming_mode=self.gaming_var.get(),
                    suppress_local=self.suppress_var.get(),
                    clipboard_hotkey=self.clipboard_hotkey_var.get().strip() or None,
                    debug=False,
                ),
            )
            self.sender.start()
            self.capture.start()
            self.running = True
            self.status_var.set("Starting...")
            self.start_button.configure(state=tk.DISABLED)
            self.stop_button.configure(state=tk.NORMAL)
            self._log("PC sender started.")
        except Exception as exc:
            self._stop()
            messagebox.showerror("DualLink Keyboard PC", str(exc))
            self._log(f"Start failed: {exc}")

    def _stop(self) -> None:
        capture = self.capture
        sender = self.sender
        self.capture = None
        self.sender = None
        self.running = False
        if capture is not None:
            capture.stop()
        if sender is not None:
            sender.stop()
        self.status_var.set("Stopped")
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self._log("PC sender stopped.")

    def _transport_factory(self) -> Callable[[], Transport]:
        mode = self.mode_var.get()
        if mode == "adb":
            adb_path = self.adb_path_var.get().strip() or "adb"
            device = self.adb_device_var.get().strip() or None
            return lambda: AdbTransport(adb_path=adb_path, device=device, debug=False)
        if mode == "bluetooth":
            address = normalize_bluetooth_address(self.bluetooth_address_var.get())
            if not address:
                raise ValueError("Enter the phone Bluetooth address, for example AA:BB:CC:DD:EE:FF.")
            channel = self._bluetooth_channel_or_none()
            return lambda: BluetoothRFCOMMTransport(address=address, channel=channel, debug=False)
        if mode == "serial":
            port = self.serial_port_var.get().strip()
            if not port:
                raise ValueError("Enter a Bluetooth COM port, for example COM7.")
            return lambda: SerialRFCOMMTransport(port=port, debug=False)
        raise ValueError(f"Unknown mode: {mode}")

    def _bluetooth_channel_or_none(self) -> int | None:
        channel_text = self.bluetooth_channel_var.get().strip()
        if not channel_text:
            return None
        try:
            channel = int(channel_text)
        except ValueError as exc:
            raise ValueError("RFCOMM channel must be a number, for example 1.") from exc
        if channel < 1 or channel > 30:
            raise ValueError("RFCOMM channel must be between 1 and 30.")
        return channel

    def _poll_ui(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)

        sender = self.sender
        if sender is not None:
            stats = sender.stats
            state = "Connected" if stats.connected else "Connecting..."
            if stats.last_error:
                state = "Connecting - " + stats.last_error
                if stats.last_error != self._last_error_logged:
                    self._last_error_logged = stats.last_error
                    self._log("Connection error: " + stats.last_error)
            self.status_var.set(state)
            self.stats_var.set(
                f"sent={stats.sent} queued={stats.queued} dropped={stats.dropped} reconnects={stats.reconnects}"
            )
        self.after(500, self._poll_ui)

    def _log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")

    def destroy(self) -> None:
        self._stop()
        super().destroy()


def main() -> int:
    app = DualLinkPcApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
