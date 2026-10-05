"""Two Moons Part 1: a spark paints the garden, the Rust consumes it, one
spark remembers. Grid-cell world + glow orbs + shockwave rings.
Paint ops (disc/ring/fade/PNG) live in engine.py; this file keeps only
its grid renderer and story beats.
Usage: python3 two_moons.py [--mux out.mp4]
"""
import math
import random
import sys

import engine
from engine import mux, save_caps, W, H

CW, CH = 16, 9
CELL = 27
GX, GY = (W - CW * CELL) // 2, (H - CH * CELL) // 2
OUT = 'j%04d.png'
CAPTIONS = [
    ("In the beginning, the garden of light was dark.", 0.5, 3.8),
    ("Then one spark decided to exist.", 4.2, 6.8),
    ("Wherever it went, colour dared to follow.", 7.0, 9.8),
    ("Then the Rust came.", 10.2, 12.0),
    ("It knew one trick. Silence.", 12.2, 14.0),
    ("So the spark ran.", 14.5, 17.0),
    ("For a while, it outran the end.", 17.2, 20.0),
    ("Then the garden forgot it ever stitched.", 20.5, 23.0),
    ("Until one spark remembered.", 23.5, 27.5),
    ("Maybe the world just needs a fresh start.", 28.0, 31.8),
]

random.seed(7)
stars = [(random.randrange(W), random.randrange(H // 2)) for _ in range(60)]

grid = [[None] * CW for _ in range(CH)]
born = [[-1] * CW for _ in range(CH)]
FC = [0]


def set_cell(x, y, c):
    if 0 <= x < CW and 0 <= y < CH:
        grid[y][x] = c
        born[y][x] = FC[0]


def gp(cx, cy):
    return (GX + cx * CELL + CELL // 2, GY + cy * CELL + CELL // 2)


def render(path, orbs, brightness=1.0, flash=False, fade=0.0, tw=0, rings=()):
    FC[0] = tw
    img = bytearray(W * H * 3)
    for i, (sx, sy) in enumerate(stars):
        if (i + tw) % 3 == 0:
            continue
        o = (sy * W + sx) * 3
        v = min(255, int(180 * brightness))
        img[o] = img[o + 1] = img[o + 2] = v
    # garden cells with pop-in scale + bloom glow + breathing
    for cy in range(CH):
        for cx in range(CW):
            c = grid[cy][cx]
            if c:
                age = tw - born[cy][cx] if born[cy][cx] >= 0 else 99
                u = min(1.0, max(0.05, age / 7.0))
                s = 1 + 2.2 * (u - 1) ** 3 + 1.4 * (u - 1) ** 2  # ease-out-back pop
                s = max(0.05, min(1.0, s))
                glow = 1.0 + 1.3 * max(0.0, 1 - age / 12.0)  # hot at birth
                breathe = 1.0 + 0.06 * math.sin(tw * 0.25 + (cx + cy) * 0.7)
                r, g, b = (min(255, int(v * brightness * glow * breathe)) for v in c)
                inset = int((1 - s) * (CELL / 2))
                w = CELL - 2 - inset * 2
                if w <= 0:
                    continue
                brow = bytes((r, g, b)) * w  # one C fill per row, not per pixel
                x0 = GX + cx * CELL + 1 + inset
                for yy in range(max(0, GY + cy * CELL + 1 + inset),
                                 min(H, GY + (cy + 1) * CELL - 1 - inset)):
                    a = max(0, x0)
                    b = min(W, x0 + w)
                    if b > a:
                        o = (yy * W + a) * 3
                        img[o:o + (b - a) * 3] = brow[(a - x0) * 3:(b - x0) * 3]
    for (ox, oy, rad, col) in orbs:
        pulse = 1.8 + 0.25 * math.sin(tw * 0.3)
        engine.disc(img, ox, oy, rad * pulse, tuple(v // 5 for v in col))
        engine.disc(img, ox, oy, rad * 1.3, tuple(min(255, v // 2 + 60) for v in col))
        engine.disc(img, ox, oy, rad, col)
    for (rx, ry, rr, rgb, dim) in rings:
        engine.ring(img, rx, ry, rr, rgb, dim)
    if flash:
        for i in range(len(img)):
            img[i] = 255
    if fade > 0:
        engine.fade(img, fade)
    engine.write_png(path, img)


frames = []


def emit(n, orbs, **kw):
    for k in range(n):
        f = OUT % len(frames)
        frames.append(f)
        render(f, orbs, tw=len(frames), **kw)


RED, BLUE = (255, 90, 90), (90, 200, 255)
GOLD, LEAF = (255, 220, 90), (140, 255, 140)
PURP = (220, 140, 255)


def lerp(a, b, t):
    t = t * t * (3 - 2 * t)
    return a + (b - a) * t


# S1 0-4s: night, empty garden fades in
for i in range(40):
    emit(1, [], brightness=0.3 + 0.7 * (i / 40))

# S2 4-10s: red moon rises left, paints red trail
rx0, ry0 = 40, H - 30
rx1, ry1 = W // 2 - 60, H // 2
for i in range(60):
    t = i / 60
    rx, ry = lerp(rx0, rx1, t), lerp(ry0, ry1, t) - math.sin(t * 3.14) * 30
    if i % 6 == 0:
        set_cell(int((rx - GX) / CELL), int((ry - GY) / CELL), RED)
    emit(1, [(rx, ry, 12, RED)])

# S3 10-16s: blue moon rises right, paints blue trail
bx0, by0 = W - 40, H - 30
bx1, by1 = W // 2 + 60, H // 2
for i in range(60):
    t = i / 60
    bx, by = lerp(bx0, bx1, t), lerp(by0, by1, t) - math.sin(t * 3.14) * 30
    if i % 6 == 0:
        set_cell(int((bx - GX) / CELL), int((by - GY) / CELL), BLUE)
    emit(1, [(rx1, ry1, 12, RED), (bx, by, 12, BLUE)])

# S4 16-22s: orbit around center
cx, cy = W // 2, H // 2
for i in range(60):
    a = i / 60 * 2 * 3.14159
    r1 = (cx + math.cos(a) * 70, cy + math.sin(a) * 40 - 10)
    r2 = (cx - math.cos(a) * 70, cy - math.sin(a) * 40 - 10)
    emit(1, [(r1[0], r1[1], 12, RED), (r2[0], r2[1], 12, BLUE)])

# S5 22-29s: meet + flash, garden blooms in a wave
for i in range(20):  # approach
    t = i / 20
    mx = lerp(cx - 70, cx, t)
    emit(1, [(mx, cy - 10, 12, RED), (2 * cx - mx, cy - 10, 12, BLUE)])
emit(2, [(cx, cy - 10, 16, (255, 255, 255))], flash=True)
# clear trails for a fresh bloom
for yy in range(CH):
    for xx in range(CW):
        grid[yy][xx] = None
        born[yy][xx] = -1


def bloom_col(ix, iy):
    dx, dy = ix - CW / 2 + 0.5, (iy - CH / 2 + 0.5) * 1.4
    d = math.hypot(dx, dy)
    ang = math.atan2(dy, dx)
    h = (math.sin(ix * 12.9 + iy * 7.7) * 0.5 + 0.5)
    if d < 1.2:
        return (255, 250, 235)  # white heart
    blends = [GOLD, (255, 170, 120), (250, 130, 180), PURP, BLUE, LEAF, (110, 230, 170)]
    return blends[int((ang / 6.283 + 0.5) * len(blends) + d * 0.9 + h * 1.5) % len(blends)]


order = sorted([(math.hypot(x - CW / 2 + 0.5, (y - CH / 2 + 0.5) * 1.4), x, y)
                for y in range(CH) for x in range(CW)])
wave_frames = 34
for i in range(wave_frames):
    wave_r = 1.0 + (max(d for d, _, _ in order) + 1.5) * (i / wave_frames) ** 1.4
    for d, x, y in order:
        if d <= wave_r and grid[y][x] is None:
            FC[0] = len(frames)  # stamp birth = this frame
            set_cell(x, y, bloom_col(x, y))
    rings = []
    for k, sp in enumerate((9.0, 6.5, 4.5)):
        rr = (i - k * 3) * sp
        if rr > 4:
            rings.append((cx, cy - 10, rr, (255, 220, 180), 2 + k))
    sun_r = 14 + 3 * math.sin(i * 0.4)
    emit(1, [(cx, cy - 10, sun_r, (255, 240, 210))], rings=rings,
         brightness=1.0 + 0.5 * max(0.0, 1 - i / 10))
emit(8, [(cx, cy - 10, 14, PURP)], brightness=1.15)  # settle glow

# S6 29-33s: hold + fade to full black
emit(20, [(cx, cy - 10, 14, PURP)])
for i in range(20):
    emit(1, [(cx, cy - 10, 14, PURP)], fade=(i + 1) / 20)

print('frames:', len(frames))
if '--mux' in sys.argv:
    save_caps('caps.txt', CAPTIONS)
    mux(OUT, 'caps.txt', sys.argv[sys.argv.index('--mux') + 1])
