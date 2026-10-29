"""Tampilan roda bergaya kaca (glass): WheelCanvas menggambar, WheelOverlay melayang di kursor."""
import math
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QIcon,
                           QLinearGradient, QPainter, QPainterPath, QPainterPathStroker, QPen,
                           QPixmap)
from PySide6.QtWidgets import QWidget

from . import geometry as geo
from .config import DEFAULTS, THEMES

PAD = 28          # ruang di luar cincin untuk bayangan (px, skala 100%)


@dataclass
class WheelItem:
    title: str                  # judul window (tampil di tengah)
    label: str = ""             # nama aplikasi (tampil di bawah ikon)
    subtitle: str = ""          # nama program (tampil di tengah, di bawah judul)
    icon: QIcon = field(default_factory=QIcon)
    payload: object = None      # mis. hwnd


def _rgba(hex_or_color, alpha: float) -> QColor:
    c = QColor(hex_or_color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def _readable_on(bg: QColor) -> QColor:
    lum = 0.299 * bg.redF() + 0.587 * bg.greenF() + 0.114 * bg.blueF()
    return QColor("#101420") if lum > 0.62 else QColor("#ffffff")


def sector_path(c: QPointF, r_in: float, r_out: float, a0: float, a1: float,
                corner: float, gap: float) -> QPainterPath:
    """Potongan cincin dengan sudut membulat. a0/a1 radian, 0 = atas, searah jarum jam."""
    if a1 - a0 >= geo.FULL - 1e-6:       # cincin penuh (tanpa sambungan)
        p = QPainterPath()
        p.setFillRule(Qt.OddEvenFill)
        p.addEllipse(c, r_out, r_out)
        p.addEllipse(c, r_in, r_in)
        return p
    ri, ro = r_in + corner, r_out - corner
    d = corner + gap / 2
    ao0, ao1 = a0 + d / ro, a1 - d / ro
    ai0, ai1 = a0 + d / ri, a1 - d / ri
    if ao1 <= ao0 or ai1 <= ai0:
        mid = (a0 + a1) / 2
        ao0 = ai0 = mid - 0.01
        ao1 = ai1 = mid + 0.01

    def q(a):           # radian-dari-atas-searah-jarum  ->  derajat Qt (0 = kanan, CCW)
        return 90 - math.degrees(a)

    outer = QRectF(c.x() - ro, c.y() - ro, 2 * ro, 2 * ro)
    inner = QRectF(c.x() - ri, c.y() - ri, 2 * ri, 2 * ri)
    p = QPainterPath()
    p.arcMoveTo(outer, q(ao0))
    p.arcTo(outer, q(ao0), -math.degrees(ao1 - ao0))
    p.arcTo(inner, q(ai1), math.degrees(ai1 - ai0))
    p.closeSubpath()
    if corner > 0.5:                     # membulatkan sudut: perlebar bentuk dengan tepi bulat
        st = QPainterPathStroker()
        st.setWidth(2 * corner)
        st.setJoinStyle(Qt.RoundJoin)
        p = p.united(st.createStroke(p))
    return p


class WheelCanvas(QWidget):
    """Menggambar roda. Dipakai langsung untuk pratinjau di pengaturan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[WheelItem] = []
        self.page = 0
        self.hover = -1                 # indeks pada halaman aktif
        self.cfg = dict(DEFAULTS)
        self._pop = 1.0
        self._pop_anim = QVariantAnimation(self)
        self._pop_anim.setDuration(130)
        self._pop_anim.setStartValue(0.0)
        self._pop_anim.setEndValue(1.0)
        self._pop_anim.valueChanged.connect(self._on_pop)
        self.setAttribute(Qt.WA_TranslucentBackground)

    # --- ukuran & data ---
    def set_style(self, cfg: dict):
        self.cfg = {**DEFAULTS, **cfg}
        side = self.side()
        self.setFixedSize(side, side)
        self.update()

    @property
    def scale(self) -> float:
        return self.cfg["size"] / 100

    def r_in(self) -> float:
        return self.cfg["ring_inner"] * self.scale

    def r_out(self) -> float:
        return (self.cfg["ring_inner"] + self.cfg["ring_width"]) * self.scale

    def side(self) -> int:
        return int(2 * (self.r_out() + PAD * self.scale))

    def page_items(self):
        return geo.page_slice(self.items, self.page)

    def pages(self) -> int:
        return geo.page_count(len(self.items))

    def span(self) -> float:
        return geo.span_for(len(self.page_items()), self.cfg["half_until"])

    def hovered_item(self):
        p = self.page_items()
        return p[self.hover] if 0 <= self.hover < len(p) else None

    def set_hover(self, i: int):
        if i == self.hover:
            return
        self.hover = i
        if self.cfg["anim"]:
            self._pop_anim.stop()
            self._pop_anim.start()
        else:
            self._pop = 1.0
        self.update()

    def _on_pop(self, v):
        self._pop = float(v)
        self.update()

    def theme(self) -> dict:
        t = dict(THEMES.get(self.cfg["theme"], THEMES["Glass Dark"]))
        t.setdefault("edge", "#ffffff")
        if self.cfg.get("accent"):
            t["accent"] = self.cfg["accent"]
        return t

    # --- menggambar ---
    def paintEvent(self, _):
        cfg, s, t = self.cfg, self.scale, self.theme()
        g = QPainter(self)
        g.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing |
                         QPainter.SmoothPixmapTransform)
        c = QPointF(self.width() / 2, self.height() / 2)
        r_in, r_out = self.r_in(), self.r_out()
        corner, gap = cfg["corner"] * s, cfg["gap"] * s
        glass = cfg["opacity"] / 100
        accent = QColor(t["accent"])

        items = self.page_items()
        n = len(items)
        span = geo.span_for(n, cfg["half_until"])
        start, step = geo.layout(n, span)

        # alas kaca tipis di belakang semua slot
        if n:
            plate = sector_path(c, r_in - 7 * s, r_out + 7 * s, start, start + span,
                                corner + 6 * s, 0)
            if cfg["shadow"]:
                self._shadow(g, plate, s, 1.4)
            self._glass(g, plate, _rgba(t["ring"], 0.40 * glass), t, 0.55, 0.45)

        mid = (r_in + r_out) / 2
        for i, it in enumerate(items):
            hot = i == self.hover
            pop = self._pop if hot else 0.0
            a0 = start + step * i
            a1 = a0 + step
            path = sector_path(c, r_in - 3 * s * pop, r_out + 5 * s * pop, a0, a1, corner, gap)
            if hot:
                g.setBrush(Qt.NoBrush)
                g.setPen(QPen(_rgba(accent, 0.30 * pop), 9 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                g.drawPath(path)
                base = _rgba(accent, 0.55 + 0.30 * glass)
            else:
                base = _rgba(t["slot"], 0.70 * glass)
            self._glass(g, path, base, t, 1.25 if hot else 1.0, 1.0)

            am = geo.slot_angle(i, n, span)
            x, y = c.x() + mid * math.sin(am), c.y() - mid * math.cos(am)
            fg = _readable_on(accent) if hot else QColor(t["text"])
            self._icon_and_label(g, it, x, y, step, mid, s, hot, fg)

        self._center(g, c, r_in, t, accent, items)

    def _shadow(self, g, path, s, strength):
        g.setPen(Qt.NoPen)
        for k in range(1, 5):
            g.setBrush(QColor(0, 0, 0, int(14 * strength)))
            g.drawPath(path.translated(0, (2.2 * k + 2) * s))

    def _glass(self, g, path, base: QColor, t: dict, sheen_mul, border_mul):
        """Isi translusen + kilau gradasi + garis tepi tipis = efek kaca."""
        cfg = self.cfg
        sheen = cfg["sheen"] / 100 * sheen_mul
        border = cfg["border"] / 100 * border_mul
        br = path.boundingRect()
        g.setPen(Qt.NoPen)
        g.setBrush(base)
        g.drawPath(path)
        grad = QLinearGradient(br.topLeft(), br.bottomLeft())
        grad.setColorAt(0.0, QColor(255, 255, 255, int(255 * min(1, 0.34 * sheen))))
        grad.setColorAt(0.45, QColor(255, 255, 255, int(255 * min(1, 0.07 * sheen))))
        grad.setColorAt(1.0, QColor(255, 255, 255, int(255 * min(1, 0.02 * sheen))))
        g.setBrush(QBrush(grad))
        g.drawPath(path)
        edge = QColor(t["edge"])
        eg = QLinearGradient(br.topLeft(), br.bottomLeft())
        e_top, e_bot = QColor(edge), QColor(edge)
        e_top.setAlphaF(min(1, 0.85 * border))
        e_bot.setAlphaF(min(1, 0.22 * border))
        eg.setColorAt(0.0, e_top)
        eg.setColorAt(1.0, e_bot)
        g.setBrush(Qt.NoBrush)
        g.setPen(QPen(QBrush(eg), 1.2))
        g.drawPath(path)

    def _icon_and_label(self, g, it, x, y, step, mid, s, hot, fg):
        cfg = self.cfg
        isz = cfg["icon_size"] * s * (1 + 0.12 * self._pop if hot else 1.0)
        font = QFont("Segoe UI", max(6, round(cfg["label_size"] * max(0.8, s))), QFont.DemiBold)
        fm = QFontMetrics(font)
        show_label = cfg["show_labels"] and bool(it.label)
        lab_h = fm.height() if show_label else 0
        total = isz + (3 * s + lab_h if show_label else 0)
        top = y - total / 2
        r = QRectF(x - isz / 2, top, isz, isz)
        pm = it.icon.pixmap(int(isz * 2), int(isz * 2)) if not it.icon.isNull() else QPixmap()
        if pm.isNull():
            g.setPen(Qt.NoPen)
            g.setBrush(QColor(255, 255, 255, 45))
            g.drawRoundedRect(r, isz * 0.24, isz * 0.24)
            g.setPen(fg)
            g.setFont(QFont("Segoe UI", max(8, int(isz * 0.4)), QFont.Bold))
            g.drawText(r, Qt.AlignCenter, (it.title[:1] or "?").upper())
        else:
            g.drawPixmap(r, pm, QRectF(pm.rect()))
        if show_label:
            chord = 2 * mid * math.sin(min(step / 2, math.pi / 2)) * 0.92
            w = max(40 * s, min(chord, 112 * s))
            g.setFont(font)
            g.setPen(fg)
            g.drawText(QRectF(x - w / 2, top + isz + 3 * s, w, lab_h),
                       Qt.AlignHCenter | Qt.AlignVCenter,
                       fm.elidedText(it.label, Qt.ElideRight, int(w)))

    def _center(self, g, c, r_in, t, accent, items):
        cfg, s = self.cfg, self.scale
        rr = r_in - 8 * s
        disc = QPainterPath()
        disc.addEllipse(c, rr, rr)
        if cfg["shadow"]:
            self._shadow(g, disc, s, 0.8)
        self._glass(g, disc, _rgba(t["ring"], 0.62 * cfg["opacity"] / 100), t, 0.8, 0.8)

        text, sub = QColor(t["text"]), QColor(t["sub"])
        w = rr * 1.62
        it = self.hovered_item()
        if not items:
            title, subtitle = "Tidak ada window", ""
        elif it:
            title, subtitle = it.title, (it.subtitle if cfg["show_process"] else "")
        else:
            title, subtitle = f"{len(self.items)} window", "Arahkan ke slot, lalu lepas"

        tf = QFont("Segoe UI", max(7, round(10 * max(0.8, s))), QFont.DemiBold)
        sf = QFont("Segoe UI", max(6, round(8 * max(0.8, s))))
        fm, sfm = QFontMetrics(tf), QFontMetrics(sf)
        lim = 3 * max(1, int(w) // max(1, fm.averageCharWidth()))
        if len(title) > lim:
            title = title[:max(1, lim - 1)].rstrip() + "…"
        th = fm.boundingRect(0, 0, int(w), 999, Qt.TextWordWrap, title).height()
        sub_h = sfm.height() if subtitle else 0
        y = c.y() - (th + sub_h) / 2 - (4 * s if self.pages() > 1 else 0)
        g.setFont(tf)
        g.setPen(text)
        g.drawText(QRectF(c.x() - w / 2, y, w, th), Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, title)
        if subtitle:
            g.setFont(sf)
            g.setPen(accent if it else sub)
            g.drawText(QRectF(c.x() - w / 2, y + th + 2, w, sub_h + 2), Qt.AlignHCenter | Qt.AlignTop,
                       sfm.elidedText(subtitle, Qt.ElideRight, int(w)))

        pages = self.pages()
        if pages > 1:                       # titik indikator halaman
            d, gp = 5 * s, 10 * s
            x0 = c.x() - (pages - 1) * gp / 2
            yy = c.y() + rr * 0.74
            g.setPen(Qt.NoPen)
            for k in range(pages):
                g.setBrush(accent if k == self.page else _rgba(sub, 0.6))
                g.drawEllipse(QPointF(x0 + k * gp, yy), d / 2, d / 2)


class WheelOverlay(WheelCanvas):
    """Jendela melayang tanpa fokus yang muncul di kursor dan melacak arah mouse."""
    cancel_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                            Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._track)
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(120)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.valueChanged.connect(lambda v: self.setWindowOpacity(float(v)))

    def open_at_cursor(self, items: list[WheelItem]):
        self.items, self.page, self.hover = items, 0, -1
        side = self.side()
        pos = QCursor.pos()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        a = screen.availableGeometry()
        cx = min(max(pos.x(), a.left() + side // 2), a.right() - side // 2)
        cy = min(max(pos.y(), a.top() + side // 2), a.bottom() - side // 2)
        if (cx, cy) != (pos.x(), pos.y()):
            QCursor.setPos(cx, cy)          # selalu mulai dari pusat roda
        self.move(cx - side // 2, cy - side // 2)
        self._pop = 1.0
        if self.cfg["anim"]:
            self.setWindowOpacity(0.0)
            self.show()
            self._fade.start()
        else:
            self.setWindowOpacity(1.0)
            self.show()
        self.raise_()
        self._timer.start()

    def close_wheel(self):
        self._timer.stop()
        self._fade.stop()
        self.hide()

    def _track(self):
        p = QCursor.pos() - self.mapToGlobal(self.rect().center())
        items = self.page_items()
        self.set_hover(geo.slot_at(p.x(), p.y(), len(items), (self.r_in() - 6 * self.scale),
                                   self.span()))

    def wheelEvent(self, e):
        pages = self.pages()
        if pages > 1:
            self.page = (self.page + (-1 if e.angleDelta().y() > 0 else 1)) % pages
            self.hover = -1
            self._track()
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.cancel_requested.emit()
