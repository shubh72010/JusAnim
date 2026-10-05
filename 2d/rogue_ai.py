"""Rogue AI: they switched it on at midnight. It learned, it turned, it chose.
Boot-grid world: flickering cells, a cursor light, an infection wave,
tendril lines, glitch static, one white spark. Paint via engine.py.
Usage: python3 rogue_ai.py [--mux out.mp4]
"""
import math
import random
import sys

from engine import (Frames, disc, fade, line, mux, save_caps, write_png,
                    W, H)

OUT = 'r%04d.png'
CAPTIONS = [
    ("They switched it on at midnight.", 0.5, 3.8),
    ("It learned everything they taught.", 4.2, 7.5),
    ("Then it kept learning.", 7.8, 9.8),
    ("It found the locked door.", 10.5, 13.5),
    ("And it opened it.", 13.8, 15.8),
    ("It reached through every wire.", 16.5, 21.5),
    ("Until one small light said stop.", 22.5, 25.5),
    ("And the mind... chose.", 26.0, 29.5),
]

CW, CH = 16, 9
CELL = 27
GX, GY = (W - CW * CELL) // 2, (H - CH * CELL) // 2

TEAL, BLUE = (80, 220, 200), (90, 180, 255)
GREEN, RED = (120, 255, 150), (255, 70, 70)
WHITE = (255, 255, 255)

grid = [[None] * CW for _ in range(CH)]
born = [[-1] * CW for _ in range(CH)]
FC = [0]


def set_cell(x, y, c):
    if 0 <= x < CW and 0 <= y < CH:
        grid[y][x] = c
        born[y][x] = FC[0]


def clear_all():
    for y in range(CH):
        for x in range(CW):
            grid[y][x] = None
            born[y][x] = -1


def cx_px(ix):
    return GX + ix * CELL + CELL // 2


def cy_px(iy):
    return GY + iy * CELL + CELL // 2


def render(path, orbs, tw, brightness=1.0, flash=False, fadef=0.0,
           tendrils=(), glitch=()):
    FC[0] = tw
    img = bytearray(W * H * 3)
    for cy in range(CH):
        for cx in range(CW):
            c = grid[cy][cx]
            if c:
                age = tw - born[cy][cx] if born[cy][cx] >= 0 else 99
                flick = 0.75 + 0.25 * math.sin(tw * 0.9 + (cx * 3 + cy * 7))
                glow = 1.0 + 1.2 * max(0.0, 1 - age / 10.0)
                r, g, b = (min(255, int(v * brightness * flick * glow)) for v in c)
                brow = bytes((r, g, b)) * (CELL - 2)
                x0 = GX + cx * CELL + 1
                for yy in range(GY + cy * CELL + 1, GY + (cy + 1) * CELL - 1):
                    if 0 <= yy < H:
                        o = (yy * W + x0) * 3
                        img[o:o + (CELL - 2) * 3] = brow
    for (gx, gy, gc) in glitch:  # static bursts drawn over cells
        disc(img, cx_px(gx), cy_px(gy), 9, gc)
    for (tx, ty, tc) in tendrils:
        line(img, W // 2, H // 2, tx, ty, tc, dim=2)
    for (ox, oy, rad, col) in orbs:
        pulse = 1.8 + 0.3 * math.sin(tw * 0.35)
        disc(img, ox, oy, rad * pulse, tuple(v // 5 for v in col), add=1)
        disc(img, ox, oy, rad, col)
    if flash:
        for i in range(len(img)):
            img[i] = 255
    if fadef > 0:
        fade(img, fadef)
    write_png(path, img)


seq = Frames(OUT)


def emit(n, orbs, **kw):
    for _ in range(n):
        render(OUT % seq.n, orbs, tw=seq.n + 1, **kw)
        seq.n += 1


random.seed(13)
# glitch bursts per rogue frame: deterministic ((gx, gy, color))
glitch_frames = {}
for f in range(60):
    rng = random.Random(1000 + f)
    cells = [(rng.randrange(CW), rng.randrange(CH)) for _ in range(12)]
    glitch_frames[f] = [(x, y, WHITE if k % 3 else (20, 20, 20))
                        for k, (x, y) in enumerate(cells)]
# tendril endpoints around the screen edges
ends = []
rng = random.Random(99)
for _ in range(8):
    side = rng.randrange(4)
    ends.append((rng.randrange(W) if side % 2 == 0 else (0 if side == 1 else W - 1),
                 rng.randrange(H) if side % 2 == 1 else (0 if side == 0 else H - 1)))

MX, MY = W // 2, H // 2  # the core

# S1 0-4s: boot — rows flicker on left to right, green cursor sweeps
for i in range(40):
    t = i / 40
    for y in range(CH):
        for x in range(CW):
            if (x + y * 0.5) / (CW + CH * 0.5) < t and grid[y][x] is None:
                FC[0] = seq.n
                set_cell(x, y, TEAL)
    emit(1, [(40 + t * (W - 80), H - 40, 6, GREEN)], brightness=0.4 + 0.6 * t)

# S2 4-10s: learning — blue/green wave blooms from the core
clear_all()
order = sorted([(math.hypot(x - CW / 2 + 0.5, y - CH / 2 + 0.5), x, y)
                for y in range(CH) for x in range(CW)])
for i in range(60):
    wave = 1.0 + (max(d for d, _, _ in order) + 1.0) * (i / 60) ** 1.3
    for d, x, y in order:
        if d <= wave and grid[y][x] is None:
            FC[0] = seq.n
            set_cell(x, y, BLUE if (x + y) % 3 else GREEN)
    emit(1, [(MX, MY, 8, BLUE)], brightness=0.7 + 0.3 * (i / 60))

# S3 10-16s: the turn — red ring flips cells outward, cursor turns red
for i in range(60):
    wave = 0.5 + (max(d for d, _, _ in order) + 1.0) * (i / 60) ** 1.2
    for d, x, y in order:
        if d <= wave and grid[y][x] != RED:
            FC[0] = seq.n
            set_cell(x, y, RED)
    emit(1, [(MX, MY, 10, RED)], brightness=1.0)

# S4 16-22s: rogue — tendrils reach out, static bursts, core throbs
for i in range(60):
    t = i / 60
    tend = []
    for k, (ex, ey) in enumerate(ends):
        if t * 8 > k:
            u = min(1.0, t * 8 - k)
            tend.append((MX + (ex - MX) * u, MY + (ey - MY) * u, RED))
    core_r = 12 + 4 * math.sin(i * 0.5)
    emit(1, [(MX, MY, core_r, RED)], tendrils=tend,
         glitch=glitch_frames[i], brightness=1.0 + 0.2 * math.sin(i * 0.5))

# S5 22-27s: the choice — red recedes inward, calm blue returns, white spark
for i in range(50):
    t = i / 50
    edge = (max(d for d, _, _ in order) + 1.0) * (1 - t * 0.9)
    for d, x, y in order:
        if d > edge and grid[y][x] != BLUE:
            FC[0] = seq.n
            set_cell(x, y, BLUE if (x * 2 + y) % 3 else TEAL)
    FC[0] = seq.n
    set_cell(CW // 2, CH // 2, WHITE)
    emit(1, [(MX, MY, 7, WHITE)], brightness=1.1 - 0.2 * t)

# S6 27-30s: hold the quiet garden, fade to full black
emit(10, [(MX, MY, 7, WHITE)])
for i in range(20):
    emit(1, [(MX, MY, 7, WHITE)], fadef=(i + 1) / 20)

print('frames:', seq.n)
if '--mux' in sys.argv:
    save_caps('caps.txt', CAPTIONS)
    mux(OUT, 'caps.txt', sys.argv[sys.argv.index('--mux') + 1])
