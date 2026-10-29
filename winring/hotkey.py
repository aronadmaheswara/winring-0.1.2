"""Hook keyboard global: tahan kombinasi untuk membuka roda, lepas untuk memilih."""
import ctypes
import ctypes.wintypes as wt
import threading

from PySide6.QtCore import QObject, Signal

from . import winapi as w
from .config import MOD_ALT, MOD_CTRL, MOD_SHIFT, MOD_WIN

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_QUIT = 0x12
LLKHF_INJECTED = 0x10
VK_ESCAPE = 0x1B

_MOD_VKS = {
    MOD_ALT: (0x12, 0xA4, 0xA5),
    MOD_CTRL: (0x11, 0xA2, 0xA3),
    MOD_SHIFT: (0x10, 0xA0, 0xA1),
    MOD_WIN: (0x5B, 0x5C),
}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


def _mods_held() -> int:
    m = 0
    for flag, vks in _MOD_VKS.items():
        if w.user32.GetAsyncKeyState(vks[0]) & 0x8000:
            m |= flag
    return m


class HotkeyHook(QObject):
    pressed = Signal()
    released = Signal()
    cancelled = Signal()

    def __init__(self):
        super().__init__()
        self.mods = MOD_ALT
        self.vk = 0x51
        self.enabled = True
        self._active = False
        self._swallow_up = False   # telan sisa auto-repeat/key-up setelah roda ditutup
        self._tid = 0
        self._thread = None
        self._proc = None

    # --- API ---
    def set_hotkey(self, mods: int, vk: int):
        self.mods, self.vk = mods, vk

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._tid:
            w.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)

    def force_end(self):
        """Dipanggil UI saat roda dibatalkan lewat klik kanan."""
        if self._active:
            self._active = False
            self._swallow_up = True

    # --- thread hook ---
    def _run(self):
        self._tid = w.kernel32.GetCurrentThreadId()
        self._proc = w.HOOKPROC(self._hook)
        hook = w.user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc,
                                          w.kernel32.GetModuleHandleW(None), 0)
        if not hook:
            return
        msg = wt.MSG()
        while w.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        w.user32.UnhookWindowsHookEx(hook)

    def _hook(self, n_code, w_param, l_param):
        try:
            if n_code >= 0 and self.enabled:
                r = self._handle(KBDLLHOOKSTRUCT.from_address(l_param), w_param)
                if r:
                    return 1
        except Exception:
            pass
        return w.user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _handle(self, kb, w_param) -> bool:
        """True = tombol ditelan (tidak diteruskan ke aplikasi)."""
        if kb.flags & LLKHF_INJECTED:
            return False
        vk = kb.vkCode
        down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
        up = w_param in (WM_KEYUP, WM_SYSKEYUP)

        if self._active:
            if vk == self.vk:
                if up:
                    self._active = False
                    self.released.emit()
                return True
            if vk == VK_ESCAPE and down:
                self._active = False
                self._swallow_up = True
                self.cancelled.emit()
                return True
            if up and any(vk in vks and flag & self.mods for flag, vks in _MOD_VKS.items()):
                # modifier dilepas lebih dulu -> anggap selesai
                self._active = False
                self._swallow_up = True
                self.released.emit()
            return False

        if vk == self.vk:
            if self._swallow_up:
                if up:
                    self._swallow_up = False
                return True
            if down and _mods_held() == self.mods:
                self._active = True
                self.pressed.emit()
                return True
        return False
