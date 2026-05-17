from __future__ import annotations


def read_clipboard_text() -> str | None:
    try:
        import tkinter
    except ImportError:
        return None
    root = tkinter.Tk()
    root.withdraw()
    try:
        value = root.clipboard_get()
        return value if isinstance(value, str) and value else None
    except tkinter.TclError:
        return None
    finally:
        root.destroy()

