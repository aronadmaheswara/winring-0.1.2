import json
import os
import sys
from pathlib import Path

MOD_ALT, MOD_CTRL, MOD_SHIFT, MOD_WIN = 1, 2, 4, 8

THEMES = {
    "Glass Dark":  dict(ring="#1b2030", slot="#2a3144", accent="#7cb2ff", text="#f4f7ff", sub="#9aa6c0"),
    "Glass Light": dict(ring="#ffffff", slot="#f4f7fc", accent="#3b82f6", text="#18202e", sub="#5b6678", edge="#8d9bb5"),
    "Midnight":    dict(ring="#171a21", slot="#232834", accent="#6ea8ff", text="#eef1f8", sub="#8b94a8"),
    "Graphite":    dict(ring="#1c1c1e", slot="#2b2b2e", accent="#ff9f43", text="#f2f2f2", sub="#9a9a9f"),
    "Aurora":      dict(ring="#0f1b24", slot="#16303a", accent="#2dd4bf", text="#e6fffb", sub="#7fb0aa"),
    "Ember":       dict(ring="#211413", slot="#321d1a", accent="#ff6b4a", text="#fff1ec", sub="#b88a80"),
    "Forest":      dict(ring="#131c16", slot="#1d2b21", accent="#7bd88f", text="#eaf7ee", sub="#86a68e"),
    "Rose":        dict(ring="#1f1520", slot="#2e1e30", accent="#f472b6", text="#fdeefa", sub="#b58aae"),
    "Violet":      dict(ring="#171527", slot="#242140", accent="#a78bfa", text="#f0ecff", sub="#9a93c4"),
    "Snow":        dict(ring="#f4f5f8", slot="#e3e6ee", accent="#3b82f6", text="#1b1f2a", sub="#667085", edge="#9aa3b5"),
}

# Pengaturan tampilan (dipisah supaya bisa di-reset sekaligus)
APPEARANCE = {
    "theme": "Glass Dark",
    "accent": "",          # "" = pakai warna aksen tema, atau "#rrggbb"
    "size": 100,           # skala keseluruhan (%)
    "opacity": 88,         # kepekatan kaca (%)
    "sheen": 55,           # kilau kaca (%)
    "border": 55,          # kuat garis tepi (%)
    "corner": 16,          # kelengkungan sudut (px)
    "gap": 6,              # jarak antar slot (px)
    "ring_inner": 78,      # jari-jari lubang tengah (px)
    "ring_width": 96,      # tebal cincin (px)
    "icon_size": 40,       # ukuran ikon (px)
    "label_size": 8,       # ukuran huruf nama di bawah ikon (pt)
    "show_labels": True,   # nama di bawah ikon
    "show_process": True,  # nama program di tengah roda
    "shadow": True,
    "anim": True,
}

DEFAULTS = {
    "mods": MOD_ALT,
    "vk": 0x51,            # Q  ->  Alt+Q
    "sort": "recent",      # recent | alpha
    "half_until": 6,       # setengah lingkaran sampai N app; 0 = selalu lingkaran penuh
    "autostart": False,
    **APPEARANCE,
}


def config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "WinRing" / "config.json"


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        for k in DEFAULTS:
            if k in data and isinstance(data[k], type(DEFAULTS[k])):
                cfg[k] = data[k]
    except (OSError, ValueError):
        pass
    if cfg["theme"] not in THEMES:
        cfg["theme"] = DEFAULTS["theme"]
    return cfg


def save(cfg: dict) -> None:
    p = config_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


_VK_NAMES = {
    0x20: "Space", 0x09: "Tab", 0x0D: "Enter", 0x2D: "Insert", 0x2E: "Delete",
    0x24: "Home", 0x23: "End", 0x21: "PgUp", 0x22: "PgDn",
    0xC0: "`", 0xBD: "-", 0xBB: "=", 0xDB: "[", 0xDD: "]", 0xDC: "\\",
    0xBA: ";", 0xDE: "'", 0xBC: ",", 0xBE: ".", 0xBF: "/",
}


def vk_name(vk: int) -> str:
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return _VK_NAMES.get(vk, f"VK{vk:#04x}")


def hotkey_text(mods: int, vk: int) -> str:
    parts = []
    if mods & MOD_CTRL: parts.append("Ctrl")
    if mods & MOD_ALT: parts.append("Alt")
    if mods & MOD_SHIFT: parts.append("Shift")
    if mods & MOD_WIN: parts.append("Win")
    parts.append(vk_name(vk))
    return " + ".join(parts)


def set_autostart(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    if getattr(sys, "frozen", False):
        cmd = f'"{sys.executable}"'
    else:
        pyw = Path(sys.executable).with_name("pythonw.exe")
        exe = pyw if pyw.exists() else Path(sys.executable)
        script = Path(sys.argv[0]).resolve()
        cmd = f'"{exe}" "{script}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, "WinRing", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, "WinRing")
            except FileNotFoundError:
                pass
