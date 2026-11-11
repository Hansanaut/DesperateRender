from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QWidget


_SPACE_900 = "#080D20"
_TEXT_PRIMARY = "#F4F7FF"
_BORDER = "#7CEEFF"


def _hex_to_colorref(value: str) -> int:
    value = value.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return red | (green << 8) | (blue << 16)


def _set_dwm_color(hwnd: int, attribute: int, color: str) -> None:
    from ctypes import byref, c_int, c_void_p, windll
    from ctypes.wintypes import HWND, UINT

    value = c_int(_hex_to_colorref(color))
    fn = windll.dwmapi.DwmSetWindowAttribute
    fn.argtypes = [HWND, UINT, c_void_p, UINT]
    fn.restype = c_int
    result = fn(HWND(hwnd), UINT(attribute), byref(value), UINT(4))
    if result != 0:
        raise OSError(
            f"DwmSetWindowAttribute failed with HRESULT "
            f"0x{result & 0xFFFFFFFF:08X}"
        )


def apply_desperate_render_titlebar(window: QWidget) -> None:
    """Use the native title-bar styling on Windows; no-op elsewhere."""

    if sys.platform != "win32":
        return

    try:
        from ctypes import c_int, c_void_p, windll
        from ctypes.wintypes import HWND, LPCWSTR, UINT

        hwnd = int(window.winId())
        icon_path = Path(__file__).resolve().parents[1] / "icon.ico"
        user32 = windll.user32

        user32.LoadImageW.argtypes = [
            c_void_p, LPCWSTR, UINT, c_int, c_int, UINT
        ]
        user32.LoadImageW.restype = c_void_p
        user32.SendMessageW.argtypes = [
            HWND, UINT, c_void_p, c_void_p
        ]
        user32.SendMessageW.restype = c_void_p

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        if icon_path.is_file():
            small = user32.LoadImageW(
                None, str(icon_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE
            )
            big = user32.LoadImageW(
                None, str(icon_path), IMAGE_ICON, 32, 32, LR_LOADFROMFILE
            )
            if small:
                user32.SendMessageW(HWND(hwnd), WM_SETICON, ICON_SMALL, small)
            if big:
                user32.SendMessageW(HWND(hwnd), WM_SETICON, ICON_BIG, big)

        _set_dwm_color(hwnd, 35, _SPACE_900)
        _set_dwm_color(hwnd, 36, _TEXT_PRIMARY)
        _set_dwm_color(hwnd, 34, _BORDER)

    except (AttributeError, OSError, TypeError, ValueError):
        return
