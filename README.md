# DualLink Keyboard

DualLink Keyboard is a low-latency Android + Windows keyboard bridge that allows a Windows laptop keyboard to type directly on Android devices using Bluetooth Classic RFCOMM or USB ADB.

The project is built for real-time typing, low input latency, and seamless cross-device interaction. It uses a custom Android IME (Input Method Editor) to provide global typing support across apps such as WhatsApp, Telegram, Instagram, Chrome, Discord, Notes, search bars, and more.

---

# Features

* Bluetooth Classic RFCOMM support
* USB ADB typing mode
* Global Android typing through custom IME
* Accessibility Service fallback
* Persistent low-latency connection
* Real-time keyboard event transmission
* Enter, Backspace, Space, Tab, Arrow keys
* Media key support
* Gaming mode key down/up packets
* Clipboard sync support
* Macro support
* Auto reconnect system
* Battery optimization handling
* Modular architecture for future expansion

---

# Architecture

DualLink Keyboard uses an IME-first architecture:

1. Windows captures physical keyboard events using Python.
2. Events are converted into compact packets.
3. Packets are sent through:

   * Bluetooth Classic RFCOMM
   * USB ADB
4. Android receives packets in a foreground service.
5. Events are routed into the active custom IME.
6. The IME injects text globally into editable Android fields.

Accessibility Service is included as a fallback mechanism when the IME is inactive.

---

# Project Structure

```text
DualLinkKeyboard/
 ├── android/
 ├── pc/
 └── docs/
```

---

# Setup

## Android

1. Open `DualLinkKeyboard/android` in Android Studio
2. Sync Gradle
3. Connect Android device
4. Enable USB Debugging
5. Install the app
6. Enable DualLink Keyboard in Android keyboard settings

## Windows

```powershell
cd DualLinkKeyboard/pc
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

# Bluetooth Mode

```powershell
python -m duallink_pc --mode bluetooth --address AA:BB:CC:DD:EE:FF --suppress-local
```

---

# USB ADB Mode

```powershell
adb devices
python -m duallink_pc --mode adb --adb-device DEVICE_SERIAL --suppress-local
```

---

# Latency

Target latency:

* Bluetooth RFCOMM: ~40–50ms
* USB ADB: device dependent

Latency depends on:

* Bluetooth drivers
* Android Bluetooth stack
* CPU load
* Target app behavior

---

# Future Plans

* Touchpad mode
* File transfer
* Encrypted communication
* Voice shortcuts
* Multi-device support
* Gesture controls
* Cross-platform support
* Advanced gaming input mode

---

# Technologies Used

## Android

* Kotlin
* Android IME API
* Accessibility Service
* Bluetooth RFCOMM
* Foreground Services

## Windows

* Python
* pynput
* pybluez
* ADB integration

---

# Disclaimer

Some Android apps and games may restrict input injection behavior due to Android security limitations. Full raw hardware-level injection would require privileged/system-level access.

---

# License

MIT License
