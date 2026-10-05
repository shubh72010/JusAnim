"""Two Moons Part 3 - Seasons: the seeds grow, the year turns, they rise as moons.
One readable painterly style: gradient skies, hill silhouette, two trees,
falling leaves, snow, twin moons.
Usage: python3 two_moons_3.py [--mux out.mp4]
"""
import math
import random
import sys

from engine import (Frames, disc, fade, hill, lerp3, line, mux, save_caps,
                    sky, W, H)

OUT = 'm%04d.png'
CAPTIONS = [
    ("On the new hill, the seeds took root.", 0.5, 3.5),
    ("Spring taught them green.", 4.5, 7.0),
    ("Summer made them tall.", 8.5, 10.5),
    ("Autumn gave them colors.", 12.5, 14.5),
    ("Winter took it all back.", 17.0, 19.0),
    ("But roots remember.", 19.5, 21.5),
    ("They rose as twin moons.", 22.5, 26.0),
    ("And the story starts again.", 27.0, 29.5),
]

random.seed(9)
stars = [(random.randrange(W), random.randrange(170)) for _ in range(70)]
leaves = [(random.random(), random.randrange(W), random.randrange(-40, H),
           1 + random.random() * 2) for _ in range(24)]
snow = [(random.randrange(W), random.randrange(H), 1 + random.random() * 2)
        for _ in range(70)]
# canopy blobs per tree: (dx, dy, r)
canopy = [(dx, dy, 10 + ((dx * 7 + dy * 13) % 9)) for dy in (-46, -34, -22)
          for dx in (-26, -12, 0, 12, 26)]
TX = (180, 300)  # tree x positions
TOP = 200  # hilltop line approx

TRUNK = (70, 45, 30)
GREENS = [(90, 200, 120), (120, 220, 130), (70, 180, 110)]
AUTUMN = [(230, 130, 60), (240, 180, 80), (200, 90, 70)]

seq = Frames(OUT)
push = seq.push


def tree(img, tx, height, canopy_cols, sway=0, bare=False):
    base = TOP + 8
    line(img, tx, base, tx + sway, base - height, TRUNK, wdt=2)
    line(img, tx + sway, base - height, tx + sway - 14, base - height + 22,
         TRUNK, wdt=1)
    line(img, tx + sway, base - height, tx + sway + 14, base - height + 22,
         TRUNK, wdt=1)
    if not bare:
        for k, (dx, dy, r) in enumerate(canopy):
            disc(img, tx + sway + dx, base - height + dy, r,
                 canopy_cols[k % len(canopy_cols)])


# S1 0-4s: sprouts take root on the new hill
for i in range(40):
    t = i / 40
    img = sky([(0, (40, 30, 70)), (0.6, (150, 110, 130)), (1, (240, 200, 160))])
    hill(img, TOP, 18, 0.02, 1.0, (30, 40, 30))
    for tx in TX:
        line(img, tx, TOP + 8, tx, TOP + 8 - int(22 * t), (90, 160, 90), wdt=1)
        if t > 0.6:
            disc(img, tx - 4, TOP - 14, 4, GREENS[0])
            disc(img, tx + 4, TOP - 12, 4, GREENS[1])
    push(img)

# S2 4-8s: spring green, canopies fill in
for i in range(40):
    t = i / 40
    img = sky([(0, (60, 120, 180)), (0.6, (160, 210, 220)), (1, (240, 240, 200))])
    disc(img, 400, 50, 16, (255, 245, 200))
    hill(img, TOP, 18, 0.02, 1.0, (40, 130, 70))
    n = int(t * len(canopy)) + 1
    for tx in TX:
        line(img, tx, TOP + 8, tx, TOP - 54, TRUNK, wdt=2)
        for k, (dx, dy, r) in enumerate(canopy[:n]):
            disc(img, tx + dx, TOP - 54 + dy, r, GREENS[k % 3])
    push(img)

# S3 8-12s: summer height, tall trees sway
for i in range(40):
    sway = int(3 * math.sin(i * 0.3))
    img = sky([(0, (50, 140, 230)), (0.6, (170, 220, 240)), (1, (255, 250, 210))])
    disc(img, 400, 45, 20, (255, 250, 210), add=2)
    disc(img, 400, 45, 13, (255, 250, 215))
    hill(img, TOP, 18, 0.02, 1.0, (45, 140, 75))
    for tx in TX:
        tree(img, tx, 62, GREENS, sway=sway)
    push(img)

# S4 12-17s: autumn colors, leaves fall
for i in range(50):
    t = i / 50
    img = sky([(0, (70, 60, 120)), (0.6, (220, 140, 100)), (1, (250, 220, 170))])
    disc(img, 90, 60, 14, (255, 200, 140))
    hill(img, TOP, 18, 0.02, 1.0, (120, 90, 50))
    for tx in TX:
        tree(img, tx, 62, AUTUMN)
    for seed, lx, ly, sp in leaves:
        if seed < t:
            yy = int(ly + (i * sp * 2) % (H - ly + 40))
            xx = int(lx + 12 * math.sin(i * 0.2 + seed * 20))
            if yy < H - 10:
                disc(img, xx, yy, 2, AUTUMN[int(seed * 3) % 3])
    push(img)

# S5 17-22s: winter, bare branches, snow
for i in range(50):
    img = sky([(0, (120, 150, 190)), (0.7, (200, 215, 230)), (1, (235, 240, 245))])
    hill(img, TOP, 18, 0.02, 1.0, (215, 225, 235))
    for tx in TX:
        tree(img, tx, 62, [], bare=True)
    for sx, sy, sp in snow:
        yy = int((sy + i * sp * 2.5) % H)
        xx = int(sx + 8 * math.sin(i * 0.15 + sx))
        o = (yy * W + xx) * 3
        img[o] = img[o + 1] = img[o + 2] = 255
    push(img)

# S6 22-27s: night falls, the two rise as twin moons
for i in range(50):
    t = i / 50
    img = sky([(0, lerp3((120, 150, 190), (5, 5, 18), t)),
               (1, lerp3((235, 240, 245), (12, 12, 34), t))])
    hill(img, TOP, 18, 0.02, 1.0, lerp3((215, 225, 235), (8, 8, 18), t))
    for tx in TX:
        tree(img, tx, 62, [], bare=True)
    if t > 0.3:
        for j, (sx, syy) in enumerate(stars):
            if (j + i) % 3:
                o = (syy * W + sx) * 3
                v = int(220 * (t - 0.3) / 0.7)
                img[o] = img[o + 1] = img[o + 2] = v
    rise = max(0.0, (t - 0.35) / 0.65)
    rise = rise * rise * (3 - 2 * rise)
    for mx, col in zip(TX, [(255, 150, 130), (150, 200, 255)]):
        my = (TOP - 10) - rise * 130
        disc(img, mx, my, 22, tuple(v // 5 for v in col), add=1)
        disc(img, mx, my, 13, col)
    push(img)

# S7 27-30s: hold twin moons, fade to full black
for i in range(30):
    img = sky([(0, (5, 5, 18)), (1, (12, 12, 34))])
    hill(img, TOP, 18, 0.02, 1.0, (8, 8, 18))
    for j, (sx, syy) in enumerate(stars):
        if (j + i) % 3:
            o = (syy * W + sx) * 3
            img[o] = img[o + 1] = img[o + 2] = 220
    for mx, col in zip(TX, [(255, 150, 130), (150, 200, 255)]):
        disc(img, mx, TOP - 140, 22, tuple(v // 5 for v in col), add=1)
        disc(img, mx, TOP - 140, 13, col)
    if i >= 10:
        fade(img, (i - 9) / 20)
    push(img)

print('frames:', seq.n)
if '--mux' in sys.argv:
    save_caps('caps.txt', CAPTIONS)
    mux(OUT, 'caps.txt', sys.argv[sys.argv.index('--mux') + 1])
