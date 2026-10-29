from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QHBoxLayout,
                               QLabel, QPushButton, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from . import config as C
from .wheel import WheelCanvas, WheelItem

_SAMPLE = [("Chrome", "#4f8cff"), ("Code", "#34c38f"), ("Discord", "#7c8cff"), ("Mail", "#ef5da8"),
           ("Spotify", "#22c55e"), ("Files", "#fbbf24"), ("Terminal", "#94a3b8"), ("Notes", "#fb7185"),
           ("Photos", "#38bdf8"), ("Word", "#2563eb"), ("Excel", "#16a34a"), ("Slack", "#a855f7"),
           ("Zoom", "#3b82f6"), ("Maps", "#f97316"), ("Paint", "#ec4899"), ("Calc", "#64748b")]


def _sample_items():
    out = []
    for name, col in _SAMPLE:
        pm = QPixmap(64, 64); pm.fill(Qt.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(col)); p.setPen(Qt.NoPen); p.drawRoundedRect(4, 4, 56, 56, 14, 14)
        p.setPen(Qt.white); p.setFont(QFont("Segoe UI", 24, QFont.Bold))
        p.drawText(pm.rect(), Qt.AlignCenter, name[0]); p.end()
        out.append(WheelItem(f"Jendela {name}", name, name.lower(), QIcon(pm)))
    return out


class HotkeyButton(QPushButton):
    changed = Signal(int, int)

    def __init__(self, mods, vk):
        super().__init__()
        self.mods, self.vk, self._rec = mods, vk, False
        self._refresh()
        self.clicked.connect(self._start)

    def _refresh(self):
        self.setText("Tekan kombinasi tombol…" if self._rec else C.hotkey_text(self.mods, self.vk))

    def _start(self):
        self._rec = True; self._refresh(); self.setFocus()

    def event(self, e):
        if self._rec and e.type() == QEvent.Type.ShortcutOverride:
            e.accept(); return True
        return super().event(e)

    def focusOutEvent(self, e):
        self._rec = False; self._refresh(); super().focusOutEvent(e)

    def keyPressEvent(self, e):
        if not self._rec:
            return super().keyPressEvent(e)
        if e.key() == Qt.Key_Escape:
            self._rec = False; self._refresh(); return
        if e.key() in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr):
            return
        m = e.modifiers()
        mods = ((C.MOD_ALT if m & Qt.AltModifier else 0) | (C.MOD_CTRL if m & Qt.ControlModifier else 0) |
                (C.MOD_SHIFT if m & Qt.ShiftModifier else 0) | (C.MOD_WIN if m & Qt.MetaModifier else 0))
        vk = e.nativeVirtualKey()
        if not mods or not vk:
            return          # wajib memakai minimal satu modifier
        self.mods, self.vk, self._rec = mods, vk, False
        self._refresh(); self.changed.emit(mods, vk)


class SettingsDialog(QDialog):
    applied = Signal(dict)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WinRing – Pengaturan")
        self.cfg = dict(cfg)
        self.accent = cfg["accent"]
        self._sliders = {}

        # ---- tab Umum
        self.hotkey = HotkeyButton(cfg["mods"], cfg["vk"])
        self.sort = QComboBox()
        self.sort.addItem("Terakhir dipakai", "recent")
        self.sort.addItem("Alfabet", "alpha")
        self.sort.setCurrentIndex(0 if cfg["sort"] == "recent" else 1)
        self.half = self._slider("half_until", 0, 12, cfg["half_until"], special0="Selalu penuh", unit=" app")
        self.auto = QCheckBox("Jalankan saat Windows start")
        self.auto.setChecked(cfg["autostart"])
        gen = QFormLayout()
        gen.addRow("Hotkey (tahan)", self.hotkey)
        gen.addRow("Urutan window", self.sort)
        gen.addRow("Setengah lingkaran sampai", self.half)
        gen.addRow("", self.auto)
        general = QWidget(); general.setLayout(gen)

        # ---- tab Tampilan
        self.theme = QComboBox()
        self.theme.addItems(list(C.THEMES))
        self.theme.setCurrentText(cfg["theme"])
        self.accent_btn = QPushButton()
        self.accent_btn.clicked.connect(self._pick_accent)
        reset_accent = QPushButton("Ikuti tema")
        reset_accent.clicked.connect(self._reset_accent)
        acc_row = QWidget(); ar = QHBoxLayout(acc_row); ar.setContentsMargins(0, 0, 0, 0)
        ar.addWidget(self.accent_btn, 1); ar.addWidget(reset_accent)

        look = QFormLayout()
        look.addRow("Tema", self.theme)
        look.addRow("Warna aksen", acc_row)
        look.addRow("Ukuran roda", self._slider("size", 60, 150, cfg["size"], unit="%"))
        look.addRow("Kepekatan kaca", self._slider("opacity", 30, 100, cfg["opacity"], unit="%"))
        look.addRow("Kilau kaca", self._slider("sheen", 0, 100, cfg["sheen"], unit="%"))
        look.addRow("Garis tepi", self._slider("border", 0, 100, cfg["border"], unit="%"))
        look.addRow("Sudut melengkung", self._slider("corner", 0, 28, cfg["corner"], unit=" px"))
        look.addRow("Jarak antar slot", self._slider("gap", 0, 16, cfg["gap"], unit=" px"))
        look.addRow("Lubang tengah", self._slider("ring_inner", 50, 120, cfg["ring_inner"], unit=" px"))
        look.addRow("Tebal cincin", self._slider("ring_width", 70, 140, cfg["ring_width"], unit=" px"))
        look.addRow("Ukuran ikon", self._slider("icon_size", 24, 64, cfg["icon_size"], unit=" px"))
        look.addRow("Ukuran nama", self._slider("label_size", 6, 14, cfg["label_size"], unit=" pt"))
        self.labels = QCheckBox("Nama aplikasi di bawah ikon"); self.labels.setChecked(cfg["show_labels"])
        self.proc = QCheckBox("Nama program di tengah roda"); self.proc.setChecked(cfg["show_process"])
        self.shadow = QCheckBox("Bayangan"); self.shadow.setChecked(cfg["shadow"])
        self.anim = QCheckBox("Animasi"); self.anim.setChecked(cfg["anim"])
        for chk in (self.labels, self.proc, self.shadow, self.anim):
            look.addRow("", chk)
        reset = QPushButton("Reset tampilan ke bawaan")
        reset.clicked.connect(self._reset_look)
        look.addRow("", reset)
        appearance = QWidget(); appearance.setLayout(look)

        tabs = QTabWidget()
        tabs.addTab(general, "Umum")
        tabs.addTab(appearance, "Tampilan")

        # ---- pratinjau
        self.preview = WheelCanvas()
        self._samples = _sample_items()
        self.count = QSpinBox(); self.count.setRange(1, 12); self.count.setValue(5)
        self.count.setPrefix("Contoh: "); self.count.setSuffix(" app")
        self.count.valueChanged.connect(self._update_preview)
        pv = QVBoxLayout()
        pv.addWidget(self.preview, 1, Qt.AlignCenter)
        pv.addWidget(self.count, 0, Qt.AlignCenter)
        top = QHBoxLayout(); top.addWidget(tabs, 1); top.addLayout(pv)

        ok = QPushButton("Simpan"); ok.setDefault(True); ok.clicked.connect(self._save)
        cancel = QPushButton("Batal"); cancel.clicked.connect(self.reject)
        btns = QHBoxLayout(); btns.addStretch(); btns.addWidget(cancel); btns.addWidget(ok)
        hint = QLabel("Tahan hotkey → arahkan mouse ke window → lepas untuk berpindah. "
                      "Esc / klik kanan membatalkan. Scroll untuk ganti halaman bila window > 12.")
        hint.setWordWrap(True); hint.setStyleSheet("color: gray")
        root = QVBoxLayout(self); root.addLayout(top); root.addWidget(hint); root.addLayout(btns)

        self.theme.currentTextChanged.connect(self._update_preview)
        for chk in (self.labels, self.proc, self.shadow, self.anim):
            chk.toggled.connect(self._update_preview)
        self._update_preview()

    # ---- helper
    def _slider(self, key, lo, hi, val, unit="", special0=""):
        s = QSlider(Qt.Horizontal); s.setRange(lo, hi); s.setValue(val); s.setMinimumWidth(160)
        lab = QLabel(); lab.setMinimumWidth(78)

        def show(v):
            lab.setText(special0 if (special0 and v == 0) else f"{v}{unit}")
        show(val)
        s.valueChanged.connect(show)
        s.valueChanged.connect(self._update_preview)
        box = QWidget(); l = QHBoxLayout(box); l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(s, 1); l.addWidget(lab)
        self._sliders[key] = s
        return box

    def _pick_accent(self):
        base = QColor(self.accent) if self.accent else QColor(C.THEMES[self.theme.currentText()]["accent"])
        col = QColorDialog.getColor(base, self, "Pilih warna aksen")
        if col.isValid():
            self.accent = col.name()
            self._update_preview()

    def _reset_accent(self):
        self.accent = ""
        self._update_preview()

    def _reset_look(self):
        d = C.APPEARANCE
        self.theme.setCurrentText(d["theme"]); self.accent = d["accent"]
        for k, s in self._sliders.items():
            if k in d:
                s.setValue(d[k])
        self.labels.setChecked(d["show_labels"]); self.proc.setChecked(d["show_process"])
        self.shadow.setChecked(d["shadow"]); self.anim.setChecked(d["anim"])
        self._update_preview()

    def _current(self) -> dict:
        c = dict(self.cfg)
        c.update({k: s.value() for k, s in self._sliders.items()})
        c.update(mods=self.hotkey.mods, vk=self.hotkey.vk, sort=self.sort.currentData(),
                 theme=self.theme.currentText(), accent=self.accent, autostart=self.auto.isChecked(),
                 show_labels=self.labels.isChecked(), show_process=self.proc.isChecked(),
                 shadow=self.shadow.isChecked(), anim=self.anim.isChecked())
        return c

    def _update_preview(self, *_):
        if not hasattr(self, "preview"):
            return
        c = self._current()
        t = C.THEMES[c["theme"]]
        shown = c["accent"] or t["accent"]
        self.accent_btn.setText(shown)
        self.accent_btn.setStyleSheet(f"background:{shown}; color:{'#000' if QColor(shown).lightnessF() > .6 else '#fff'}")
        pc = dict(c)
        pc["size"] = max(40, int(c["size"] * 0.72))      # pratinjau diperkecil
        self.preview.items = self._samples[:self.count.value()]
        self.preview.set_style(pc)
        self.preview.hover = min(1, self.count.value() - 1)
        self.preview._pop = 1.0
        self.preview.update()

    def _save(self):
        self.cfg = self._current()
        self.applied.emit(self.cfg)
        self.accept()
