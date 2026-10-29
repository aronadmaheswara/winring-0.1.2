"""Pembungkus tipis Win32 (ctypes): daftar window, aktivasi, dan hook keyboard."""
import ctypes
import ctypes.wintypes as wt
import os
from dataclasses import dataclass

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
version = ctypes.WinDLL("version", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.EnumChildWindows.argtypes = [wt.HWND, WNDENUMPROC, wt.LPARAM]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindow.argtypes = [wt.HWND]
user32.IsIconic.argtypes = [wt.HWND]
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
user32.GetWindow.restype = wt.HWND
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetForegroundWindow.restype = wt.HWND
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wt.HHOOK]
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x80
WS_EX_APPWINDOW = 0x40000
WS_EX_NOACTIVATE = 0x08000000
GW_OWNER = 4
SW_RESTORE = 9
DWMWA_CLOAKED = 14
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_SKIP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                 "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow"}


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    exe: str           # path lengkap program ("" bila tidak diketahui)

    @property
    def process_name(self) -> str:
        return os.path.splitext(os.path.basename(self.exe))[0] if self.exe else ""


def _text(fn, hwnd, size=256) -> str:
    buf = ctypes.create_unicode_buffer(size)
    fn(hwnd, buf, size)
    return buf.value


def _pid(hwnd) -> int:
    pid = wt.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _exe_of(pid: int) -> str:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(h)


def _cloaked(hwnd) -> bool:
    v = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(wt.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(v), 4)
    return bool(v.value)


def _uwp_real_exe(hwnd, host_pid) -> str:
    """Aplikasi UWP dibungkus ApplicationFrameHost; cari proses aslinya di child window."""
    found = []

    @WNDENUMPROC
    def cb(child, _l):
        p = _pid(child)
        if p and p != host_pid:
            found.append(p)
            return False
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return _exe_of(found[0]) if found else ""


def list_windows(own_pid: int | None = None) -> list[WindowInfo]:
    """Window yang muncul di taskbar/Alt+Tab, urutan = terakhir dipakai dulu (z-order)."""
    own_pid = own_pid or os.getpid()
    out: list[WindowInfo] = []
    exe_cache: dict[int, str] = {}

    @WNDENUMPROC
    def cb(hwnd, _l):
        if not user32.IsWindowVisible(hwnd) or _cloaked(hwnd):
            return True
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if ex & WS_EX_TOOLWINDOW and not ex & WS_EX_APPWINDOW:
            return True
        if ex & WS_EX_NOACTIVATE:
            return True
        if user32.GetWindow(hwnd, GW_OWNER) and not ex & WS_EX_APPWINDOW:
            return True
        if _text(user32.GetClassNameW, hwnd) in _SKIP_CLASSES:
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        title = _text(user32.GetWindowTextW, hwnd, n + 1)
        pid = _pid(hwnd)
        if pid == own_pid:
            return True
        if pid not in exe_cache:
            exe_cache[pid] = _exe_of(pid)
        exe = exe_cache[pid]
        if os.path.basename(exe).lower() == "applicationframehost.exe":
            exe = _uwp_real_exe(hwnd, pid) or exe
        out.append(WindowInfo(int(hwnd), title, pid, exe))
        return True

    user32.EnumWindows(cb, 0)
    return out


def activate(hwnd: int) -> None:
    """Bawa window ke depan (dan pulihkan bila diminimalkan)."""
    if not user32.IsWindow(hwnd):
        return
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    fg = user32.GetForegroundWindow()
    cur = kernel32.GetCurrentThreadId()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = bool(fg_thread and fg_thread != cur and user32.AttachThreadInput(cur, fg_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur, fg_thread, False)


def swallow_alt_menu() -> None:
    """Ketik tombol 'kosong' supaya Alt yang dilepas tidak mengaktifkan menu bar aplikasi."""
    KEYEVENTF_KEYUP = 2
    user32.keybd_event(0xE8, 0, 0, 0)
    user32.keybd_event(0xE8, 0, KEYEVENTF_KEYUP, 0)


version.GetFileVersionInfoSizeW.argtypes = [wt.LPCWSTR, ctypes.POINTER(wt.DWORD)]
version.GetFileVersionInfoSizeW.restype = wt.DWORD
version.GetFileVersionInfoW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p]
version.VerQueryValueW.argtypes = [ctypes.c_void_p, wt.LPCWSTR, ctypes.POINTER(ctypes.c_void_p),
                                   ctypes.POINTER(wt.UINT)]
_name_cache: dict[str, str] = {}


def app_name(exe: str) -> str:
    """Nama aplikasi yang ramah (mis. "Google Chrome") dari info versi file exe; "" bila tak ada."""
    if not exe:
        return ""
    if exe in _name_cache:
        return _name_cache[exe]
    name = ""
    try:
        size = version.GetFileVersionInfoSizeW(exe, None)
        if size:
            buf = ctypes.create_string_buffer(size)
            if version.GetFileVersionInfoW(exe, 0, size, buf):
                p, n = ctypes.c_void_p(), wt.UINT()
                langs = []
                if version.VerQueryValueW(buf, "\\VarFileInfo\\Translation", ctypes.byref(p),
                                          ctypes.byref(n)) and n.value >= 4:
                    lang, cp = ctypes.cast(p, ctypes.POINTER(wt.WORD))[0:2]
                    langs.append(f"{lang:04x}{cp:04x}")
                langs += ["040904b0", "040904e4"]
                for lg in langs:
                    for key in ("FileDescription", "ProductName"):
                        if version.VerQueryValueW(buf, f"\\StringFileInfo\\{lg}\\{key}",
                                                  ctypes.byref(p), ctypes.byref(n)) and n.value:
                            name = ctypes.wstring_at(p.value).strip()
                            if name:
                                break
                    if name:
                        break
    except Exception:
        name = ""
    if not name:
        name = os.path.splitext(os.path.basename(exe))[0].replace("_", " ").title()
    _name_cache[exe] = name
    return name
