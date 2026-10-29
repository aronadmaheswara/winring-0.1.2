"""Hitung-hitungan roda (tanpa Qt / Windows supaya mudah diuji).

Sudut diukur dalam radian, 0 = tepat di atas, positif = searah jarum jam.
"""
import math

PAGE_SIZE = 12
FULL = 2 * math.pi
PER_SLOT_FAN = math.radians(52)     # lebar tiap slot saat roda hanya setengah lingkaran
EDGE_TOLERANCE = math.radians(8)    # toleransi di ujung busur setengah lingkaran


def span_for(n: int, half_until: int) -> float:
    """Berapa besar busur yang dipakai: kipas/setengah lingkaran untuk sedikit app, penuh bila banyak."""
    if n <= 0:
        return math.pi
    if n <= half_until:
        return min(math.pi, n * PER_SLOT_FAN)
    return FULL


def layout(n: int, span: float):
    """(sudut awal, lebar tiap slot). Lingkaran penuh: slot 0 berpusat di atas."""
    n = max(n, 1)
    step = span / n
    start = -step / 2 if span >= FULL - 1e-9 else -span / 2
    return start, step


def slot_angle(i: int, n: int, span: float) -> float:
    start, step = layout(n, span)
    return start + step * (i + 0.5)


def slot_at(dx: float, dy: float, n: int, dead_radius: float, span: float = FULL) -> int:
    """Slot yang ditunjuk vektor (dx, dy) dari pusat roda; -1 = zona tengah / di luar busur."""
    if n <= 0 or math.hypot(dx, dy) < dead_radius:
        return -1
    start, step = layout(n, span)
    a = math.atan2(dx, -dy)
    if span >= FULL - 1e-9:
        return int(((a - start) % FULL) // step) % n
    rel = (a - start + math.pi) % FULL - math.pi        # (-pi, pi]
    if rel < -EDGE_TOLERANCE or rel > span + EDGE_TOLERANCE:
        return -1
    return min(max(int(rel // step), 0), n - 1)


def slot_center(i: int, n: int, radius: float, span: float = FULL):
    """Posisi tengah slot i relatif ke pusat roda."""
    a = slot_angle(i, n, span)
    return radius * math.sin(a), -radius * math.cos(a)


def page_count(total: int, page_size: int = PAGE_SIZE) -> int:
    return max(1, math.ceil(total / page_size))


def page_slice(items, page: int, page_size: int = PAGE_SIZE):
    return items[page * page_size:(page + 1) * page_size]
