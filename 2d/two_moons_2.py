"""Two Moons Part 2 - Five Skies: the seeds journey through changing worlds.
No grid cells anywhere: gradient bands, hill silhouettes, constellation
lines, ink-blob nebula, rain streaks, dawn sun.
Usage: python3 two_moons_2.py [--mux out.mp4]
"""
import math
import random
import sys

from engine import (Frames, disc, fade, hill, line, mux, save_caps, sky,
                    W, H)

OUT = 'k%04d.png'
CAPTIONS = [
    ("The garden was gone. Two seeds remained.", 0.5, 3.5),
    ("They watched their last sunset.", 3.8, 5.8),
    ("At night they followed the stars.", 6.5, 9.5),
    ("They drew their own road between them.", 9.5, 11.8),
    ("They hid inside a cloud to rest.", 12.5, 17.8),
    ("Rain carried them down to the sea.", 18.5, 21.5),
    ("In the morning they woke on a new hill.", 24.2, 27.0),
    ("Home, again.", 27.2, 29.6),
]

random.seed(4)
stars = [(random.randrange(W), random.randrange(170)) for _ in range(70)]
nodes = [(random.randrange(W), random.randrange(50, H - 40), random.random() * 6.28)
         for _ in range(14)]
drops = [(random.randrange(W), random.randrange(H), 8 + random.random() * 9)
         for _ in range(90)]
blob_cols = [(150, 90, 220), (90, 200, 220), (220, 110, 180), (110, 140, 255),
             (90, 220, 180), (230, 150, 110), (170, 120, 255)]
blobs = [(random.randrange(70, W - 70), random.randrange(50, H - 50),
          28 + random.random() * 26, c) for c in blob_cols]

RED, BLUE = (255, 90, 90), (90, 200, 255)
seq = Frames(OUT)
push = seq.push

# S1 0-6s: dusk hills, red sun setting
for i in range(60):
    t = i / 60
    img = sky([(0, (18, 10, 40)), (0.55, (110, 40, 100)), (0.8, (230, 90, 90)),
               (1, (255, 160, 90))])
    sy = 150 + t * 55
    disc(img, W // 2 - 60, sy, 26, (255, 120, 90), add=2)
    disc(img, W // 2 - 60, sy, 15, (255, 180, 130))
    hill(img, 195, 22, 0.02, 1.0, (8, 6, 16))
    for j, (sx, syy) in enumerate(stars):
        if (j + i) % 3 and t > 0.4:
            o = (syy * W + sx) * 3
            v = min(255, int(200 * t))
            img[o] = img[o + 1] = img[o + 2] = v
    push(img)

# S2 6-12s: constellation crossing, two seeds with trails
t1x, t1y, t2x, t2y = [], [], [], []
for i in range(60):
    t = i / 60
    img = sky([(0, (4, 4, 14)), (1, (8, 8, 26))])
    pts = [(x + 22 * math.sin(i * 0.08 + p), y + 14 * math.cos(i * 0.06 + p))
           for x, y, p in nodes]
    for a in range(len(pts)):
        for b in range(a + 1, len(pts)):
            if math.hypot(pts[a][0] - pts[b][0], pts[a][1] - pts[b][1]) < 130:
                line(img, *pts[a], *pts[b], (200, 200, 255), 4)
    for px, py in pts:
        disc(img, px, py, 2, (230, 230, 255))
    s1 = (40 + t * (W - 80), 90 + math.sin(t * 9) * 18)
    s2 = (40 + t * (W - 80), 170 + math.cos(t * 7) * 18)
    t1x.append(s1[0]); t1y.append(s1[1]); t2x.append(s2[0]); t2y.append(s2[1])
    for k in range(1, 6):
        if len(t1x) > k:
            disc(img, t1x[-k], t1y[-k], 2, RED, add=2)
            disc(img, t2x[-k], t2y[-k], 2, BLUE, add=2)
    disc(img, *s1, 5, RED)
    disc(img, *s2, 5, BLUE)
    push(img)

# S3 12-18s: ink nebula, seeds dreaming inside
for i in range(60):
    img = sky([(0, (10, 8, 26)), (1, (16, 10, 34))])
    for b, (bx, by, br, bc) in enumerate(blobs):
        mx = bx + 25 * math.sin(i * 0.07 + b * 1.7)
        my = by + 18 * math.cos(i * 0.09 + b * 2.3)
        disc(img, mx, my, br, tuple(v // 7 for v in bc), add=1)
        disc(img, mx, my, br * 0.6, tuple(v // 3 for v in bc), add=1)
        disc(img, mx, my, br * 0.3, bc, add=2)
    disc(img, W // 2 - 50 + 15 * math.sin(i * 0.1), H // 2, 7, RED)
    disc(img, W // 2 + 50 + 15 * math.cos(i * 0.1), H // 2, 7, BLUE)
    push(img)

# S4 18-24s: rain, seeds diving to the sea
rings = []
for i in range(60):
    img = sky([(0, (10, 22, 44)), (0.8, (6, 12, 26)), (1, (20, 40, 70))])
    for x, y, sp in drops:
        yy = (y + i * sp) % H
        line(img, x, yy, x, yy + 10, (150, 200, 255), 3)
    if i % 5 == 0:
        rings.append([random.randrange(W), H - 45, 3])
    for r in rings:
        r[2] += 2.5
    rings = [r for r in rings if r[2] < 40]
    for rx, ry, rr in rings:
        for xx in range(max(0, int(rx - rr)), min(W, int(rx + rr) + 1)):
            d = abs(math.hypot(xx - rx, 0) - rr)
            if d < 2 and 0 <= ry < H:
                o = (int(ry) * W + xx) * 3
                img[o + 1] = min(255, img[o + 1] + 60)
                img[o + 2] = min(255, img[o + 2] + 90)
    t = i / 60
    disc(img, 120 + t * 120, 60 + t * 150, 5, RED)
    disc(img, 360 - t * 120, 60 + t * 150, 5, BLUE)
    push(img)

# S5 24-30s: dawn, gold sun rising over the hills, fade out
for i in range(60):
    t = i / 60
    img = sky([(0, (30, 18, 60)), (0.55, (200, 100, 100)), (0.8, (255, 200, 140)),
               (1, (255, 230, 190))])
    sy = 205 - t * 85
    disc(img, W // 2, sy, 30, (255, 200, 130), add=2)
    disc(img, W // 2, sy, 17, (255, 235, 200))
    hill(img, 195, 22, 0.02, 1.0, (10, 8, 20))
    if i >= 40:
        fade(img, (i - 39) / 20)
    push(img)

print('frames:', seq.n)
if '--mux' in sys.argv:
    save_caps('caps.txt', CAPTIONS)
    mux(OUT, 'caps.txt', sys.argv[sys.argv.index('--mux') + 1])
