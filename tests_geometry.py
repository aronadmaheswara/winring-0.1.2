import math
from winring.geometry import (FULL, page_count, page_slice, slot_at, slot_center, span_for)

# --- lingkaran penuh: slot 0 di atas, searah jarum jam
assert slot_at(0, -100, 8, 20) == 0
assert slot_at(100, 0, 8, 20) == 2
assert slot_at(0, 100, 8, 20) == 4
assert slot_at(-100, 0, 8, 20) == 6
assert slot_at(5, 5, 8, 20) == -1
assert slot_at(10, -10, 0, 0) == -1

# --- span otomatis
assert span_for(1, 6) < math.pi and abs(span_for(3, 6) - 3 * math.radians(52)) < 1e-9
assert abs(span_for(5, 6) - math.pi) < 1e-9 and abs(span_for(6, 6) - math.pi) < 1e-9
assert span_for(7, 6) == FULL and span_for(4, 0) == FULL

# --- setengah lingkaran: kiri -> kanan di atas, bawah = batal
n, sp = 4, span_for(4, 6)
assert slot_at(-100, -1, n, 20, sp) == 0       # kiri
assert slot_at(100, -1, n, 20, sp) == 3        # kanan
assert slot_at(-20, -100, n, 20, sp) == 1
assert slot_at(20, -100, n, 20, sp) == 2
assert slot_at(0, 100, n, 20, sp) == -1        # bawah = tidak memilih
# --- kipas kecil (1 & 2 app) tidak menangkap arah yang jauh
assert slot_at(0, -100, 1, 20, span_for(1, 6)) == 0
assert slot_at(100, 0, 1, 20, span_for(1, 6)) == -1

# --- pusat slot konsisten dengan hit-test untuk semua n dan kedua mode
for half_until in (0, 6, 12):
    for n in range(1, 13):
        sp = span_for(n, half_until)
        for i in range(n):
            x, y = slot_center(i, n, 100, sp)
            assert slot_at(x, y, n, 20, sp) == i, (half_until, n, i)

assert page_count(0) == 1 and page_count(12) == 1 and page_count(13) == 2
assert page_slice(list(range(30)), 2) == list(range(24, 30))
print("geometry OK")
