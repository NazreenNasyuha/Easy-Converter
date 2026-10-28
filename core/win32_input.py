"""Low-level Win32 `user32.dll` asynchronous key-state polling via `ctypes`."""

from __future__ import annotations

import ctypes
from typing import Final

from core.models import ModifierMode

user32 = ctypes.windll.user32

# Win32 Virtual-Key Codes & System Metrics
VK_LBUTTON: Final[int] = 0x01
VK_RBUTTON: Final[int] = 0x02
VK_SHIFT: Final[int] = 0x10
VK_CONTROL: Final[int] = 0x11
VK_MENU: Final[int] = 0x12   # Alt key
VK_ESCAPE: Final[int] = 0x1B
SM_SWAPBUTTON: Final[int] = 23


def is_vk_down(vk: int) -> bool:
    """Return True if the specified virtual key is currently depressed."""
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def is_primary_mouse_down() -> bool:
    """Return True if the primary (logical left) mouse button is held down."""
    swapped = bool(user32.GetSystemMetrics(SM_SWAPBUTTON))
    vk = VK_RBUTTON if swapped else VK_LBUTTON
    return is_vk_down(vk)


def detect_modifier_mode() -> ModifierMode | None:
    """Return the active `ModifierMode` if Shift, Alt, or Ctrl is currently pressed."""
    if is_vk_down(VK_SHIFT):
        return ModifierMode.SHIFT
    if is_vk_down(VK_MENU):
        return ModifierMode.ALT
    if is_vk_down(VK_CONTROL):
        return ModifierMode.CTRL
    return None
