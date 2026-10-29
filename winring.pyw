"""WinRing – menu radial untuk berpindah antar window (seperti taskbar berbentuk roda)."""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtCore import QFileInfo
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QFileIconProvider, QMenu, QSystemTrayIcon

from winring import APP_NAME, config as C, winapi
from winring.hotkey import HotkeyHook
from winring.settings_dialog import SettingsDialog
from winring.wheel import WheelItem, WheelOverlay

SERVER_NAME = "WinRing-single-instance"


def make_tray_icon() -> QIcon:
    pm = QPixmap(64, 64); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#6ea8ff"), 8)); p.drawEllipse(10, 10, 44, 44)
    p.setPen(Qt.NoPen); p.setBrush(QColor("#6ea8ff")); p.drawEllipse(26, 26, 12, 12)
    p.end()
    return QIcon(pm)


class App:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
        self.cfg = C.load()
        self.icons = {}
        self.provider = QFileIconProvider()
        self.dialog = None

        self.overlay = WheelOverlay()
        self.overlay.cancel_requested.connect(self.cancel)
        self.apply_style()

        self.hook = HotkeyHook()
        self.hook.set_hotkey(self.cfg["mods"], self.cfg["vk"])
        self.hook.pressed.connect(self.open_wheel)
        self.hook.released.connect(self.choose)
        self.hook.cancelled.connect(self.cancel)
        self.hook.start()

        self.tray = QSystemTrayIcon(make_tray_icon())
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        self.hotkey_action = QAction(); self.hotkey_action.setEnabled(False)
        menu.addAction(self.hotkey_action)
        menu.addSeparator()
        menu.addAction("Pengaturan…", self.show_settings)
        menu.addAction("Keluar", self.quit)
        self.tray.setContextMenu(menu); self._menu = menu
        self.tray.activated.connect(lambda r: r == QSystemTrayIcon.Trigger and self.show_settings())
        self.tray.show()
        self.refresh_labels()

    # --- roda ---
    def apply_style(self):
        self.overlay.set_style(self.cfg)

    def refresh_labels(self):
        self.hotkey_action.setText("Hotkey: " + C.hotkey_text(self.cfg["mods"], self.cfg["vk"]))

    def icon_for(self, exe: str) -> QIcon:
        if exe not in self.icons:
            self.icons[exe] = self.provider.icon(QFileInfo(exe)) if exe else QIcon()
        return self.icons[exe]

    def collect(self) -> list[WheelItem]:
        wins = winapi.list_windows()
        if self.cfg["sort"] == "alpha":
            wins.sort(key=lambda w: w.title.lower())
        return [WheelItem(w.title, winapi.app_name(w.exe) or w.process_name, w.process_name,
                          self.icon_for(w.exe), w.hwnd) for w in wins]

    def open_wheel(self):
        self.overlay.open_at_cursor(self.collect())

    def choose(self):
        item = self.overlay.hovered_item()
        self.overlay.close_wheel()
        if self.cfg["mods"] & C.MOD_ALT:
            winapi.swallow_alt_menu()
        if item is not None:
            winapi.activate(item.payload)

    def cancel(self):
        self.hook.force_end()
        self.overlay.close_wheel()
        if self.cfg["mods"] & C.MOD_ALT:
            winapi.swallow_alt_menu()

    # --- pengaturan ---
    def show_settings(self):
        if self.dialog is not None:
            self.dialog.raise_(); self.dialog.activateWindow(); return
        self.hook.enabled = False          # supaya hotkey lama tidak mengganggu saat merekam
        self.dialog = SettingsDialog(self.cfg)
        self.dialog.applied.connect(self.apply_settings)
        self.dialog.finished.connect(self._dialog_closed)
        self.dialog.show(); self.dialog.activateWindow()

    def _dialog_closed(self, *_):
        self.hook.enabled = True
        self.dialog = None

    def apply_settings(self, cfg: dict):
        auto_changed = cfg["autostart"] != self.cfg["autostart"]
        self.cfg = cfg
        C.save(cfg)
        self.hook.set_hotkey(cfg["mods"], cfg["vk"])
        self.apply_style()
        self.refresh_labels()
        if auto_changed:
            try:
                C.set_autostart(cfg["autostart"])
            except OSError:
                pass

    def quit(self):
        self.hook.stop()
        self.tray.hide()
        self.qapp.quit()


def already_running() -> bool:
    s = QLocalSocket(); s.connectToServer(SERVER_NAME)
    if s.waitForConnected(200):
        s.disconnectFromServer()
        return True
    return False


def main():
    if sys.platform != "win32":
        print("WinRing hanya untuk Windows."); return 1
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setApplicationName(APP_NAME)
    if already_running():
        return 0
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer(); server.listen(SERVER_NAME)
    app = App(qapp)
    app.tray.showMessage(APP_NAME, "Berjalan di tray. Tahan " +
                         C.hotkey_text(app.cfg["mods"], app.cfg["vk"]) + " untuk membuka roda.",
                         QSystemTrayIcon.Information, 4000)
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
