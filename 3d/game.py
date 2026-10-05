#!/usr/bin/env python3
"""dodge the void: playable game on the storyvid raytracer. zero deps (tkinter).

run: python3 game.py  (fullscreen; W forward, A/D strafe, Shift sprint, Space jump,
grab coins, outrun the hunger, camera trails behind, wheel zoom, P/F11/R/Q)
reuses storyvid.render at 120x75 upscaled to fill the screen; ~25fps pooled.
"""
import math
import os
import random
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import storyvid as sv

import tkinter as tk

sv.W, sv.H = 120, 75  # ponytail: pool keeps this inside the 25fps tick
ZOOM = 4
TICK_MS = 40
HERO_SPEED, VOID_SPEED = 3.5, 1.2  # units/sec (same feel as 0.35/0.12 at 10fps)
GRAV, JUMP_V, CLEAR_H = 20.0, 6.5, 0.4  # jump clears the void above CLEAR_H


def fresh():
    return {"hero": -1.0, "hz": 0.0, "y": 0.0, "vy": 0.0, "void": 3.0,
            "vz": 0.0, "r": 0.9, "t": 0, "over": False, "paused": False,
            "vx": 0.0, "vhz": 0.0, "ax": 0.0, "az": 0.0, "yaw": 0.0, "dist": 7.0, "h": 2.2,
            "ph": 0.0, "fx": 0.0, "fz": -1.0,
            "cam": [0, 2.2, -7.0], "look": [0, 1.2, 0],
            "coins": [], "score": 0}


state = fresh()
_TGT = {"dist": 7.0, "h": 2.2}  # mouse input; tick eases state toward it
TMP = os.path.join(tempfile.mkdtemp(), "g.png")

_SUN = (255, 244, 214)
_FOGC, _FOGD = (170, 195, 228), 0.03
WORLD = [  # static scenery, never collides
    ((7.0, 9.0, 14.0), 1.6, _SUN),          # sun
]
CITY = [  # downtown flanks the main road; procedural streets run infinite
    ((-4.5, 1.5, -6.0), (3.0, 3.0, 3.0), (110, 116, 130)),
    ((4.5, 2.0, -6.0), (3.0, 4.0, 3.0), (90, 96, 112)),
    ((-4.5, 2.5, 6.0), (3.0, 5.0, 3.0), (130, 110, 95)),
    ((4.5, 1.5, 6.0), (3.0, 3.0, 3.0), (110, 116, 130)),
]  # ponytail: 4 near blocks only; far ones fogged out for ~nothing in return


def collide(s):
    """push the hero out of building footprints. pure, headless-testable."""
    for (bx, _, bz), (sx, _, sz), _ in CITY:
        dx, dz = s["hero"]-bx, s["hz"]-bz
        px, pz = sx/2+0.4-abs(dx), sz/2+0.4-abs(dz)
        if px > 0 and pz > 0:
            if px < pz:
                s["hero"] = bx+(sx/2+0.4 if dx > 0 else -sx/2-0.4)
            else:
                s["hz"] = bz+(sz/2+0.4 if dz > 0 else -sz/2-0.4)

SPRDIR = os.path.join(HERE, 'manuel_spr')
USE_SPR = False  # ponytail: FBX billboards creep; puppet it is. True restores them.
_HAVESPR = USE_SPR and os.path.isdir(SPRDIR)
_SPR, _SPRMETA = {}, None


def _read_png(path):
    import struct as _st
    import zlib as _z
    d = open(path, 'rb').read()
    i, ids, w, h = 8, b'', 0, 0
    while i < len(d):
        ln = int.from_bytes(d[i:i+4], 'big')
        tag = d[i+4:i+8]
        if tag == b'IHDR':
            w, h = _st.unpack('>II', d[i+8:i+16])
        elif tag == b'IDAT':
            ids += d[i+8:i+8+ln]
        i += 12+ln
    r = _z.decompress(ids)
    rows, p = [], 0
    for _ in range(h):  # our writer uses filter 0 throughout
        rows.append(r[p+1:p+1+w*3])
        p += w*3+1
    return w, h, rows


def _sprob(b, ph):
    """baked FBX sprite + mask + anchor. ponytail: baked once, blitted always."""
    global _SPRMETA
    key = (b, ph)
    if key not in _SPR:
        import json as _j
        if _SPRMETA is None:
            _SPRMETA = _j.load(open(os.path.join(SPRDIR, 'meta.json')))
        s = next(x for x in _SPRMETA['sprites'] if x['bin'] == b and x['ph'] == ph)
        _, _, rgb = _read_png(os.path.join(SPRDIR, s['file']))
        _, _, msk = _read_png(os.path.join(SPRDIR, s['file'].replace('.png', '.m.png')))
        _SPR[key] = (rgb, msk, s['w'], s['h'], s['ax'], s['ay'])
    return _SPR[key]


def bin_of(fx, fz):
    """facing -> sprite yaw bin. bake bin b faces (sin, cos): bin 4 = camera."""
    return int(round(math.atan2(fx, fz)/(math.pi/4))) % 8


def project(cam, look, p):
    """world -> screen px, mirroring the raytracer basis. None behind camera."""
    fwd = sv.norm(sv.sub(look, cam))
    right = sv.norm((fwd[2], 0, -fwd[0]))
    up = (fwd[1]*right[2]-fwd[2]*right[1], fwd[2]*right[0]-fwd[0]*right[2],
          fwd[0]*right[1]-fwd[1]*right[0])
    vx, vy, vz = p[0]-cam[0], p[1]-cam[1], p[2]-cam[2]
    zd = vx*fwd[0]+vy*fwd[1]+vz*fwd[2]
    if zd < 0.2:
        return None
    xr = vx*right[0]+vy*right[1]+vz*right[2]
    yu = vx*up[0]+vy*up[1]+vz*up[2]
    return ((xr/zd/0.8+1)*sv.W/2, (1-yu/zd/0.5)*sv.H/2, zd)


def _paste(raw, W, H, ov):
    """billboard Manuel + blob shadow into PNG rows (filter bytes kept)."""
    rgb, msk, sw, sh, dx, dy, tw, th, shx, shy, shrx, shry = ov
    for ty in range(th):
        sy = dy+ty
        if 0 <= sy < H:
            o = sy*(W*3+1)+1
            srcy = ty*sh//th
            for tx in range(tw):
                sx = dx+tx
                if 0 <= sx < W:
                    srcx = tx*sw//tw
                    if msk[srcy][srcx*3]:
                        q = o+sx*3
                        raw[q:q+3] = rgb[srcy][srcx*3:srcx*3+3]
    for oy in range(-shry, shry+1):  # contact shadow grounds him
        sy = shy+oy
        if 0 <= sy < H:
            o = sy*(W*3+1)+1
            for ox in range(-shrx, shrx+1):
                if ox*ox*shry*shry+oy*oy*shrx*shrx < shrx*shrx*shry*shry:
                    sx = shx+ox
                    if 0 <= sx < W:
                        q = o+sx*3
                        raw[q] = raw[q]*2//3
                        raw[q+1] = raw[q+1]*2//3
                        raw[q+2] = raw[q+2]*2//3


_LEAD = 0.6  # gaze this many seconds ahead of motion


def cam_move(ix, iz, yaw):
    """camera-relative input: W means away from the camera at any yaw."""
    return (ix*math.cos(yaw)-iz*math.sin(yaw), ix*math.sin(yaw)+iz*math.cos(yaw))


def cam_for(hx, hz, yaw, dist, h, lx=None, lz=None):
    """third-person orbit: yaw 0/dist 7/h 2.2 reproduces the classic view."""
    return ((hx+dist*math.sin(yaw), h, hz-dist*math.cos(yaw)),
            (hx if lx is None else lx, 1.2, hz if lz is None else lz))


def move_cam(s, tgt, dt, fwd=False):
    """chase cam: ease dist/height, swing yaw behind travel, gaze ahead.

    fwd gates the swing to pure-forward running: with camera-relative
    controls any sustained non-forward input would chase its own tail.
    """
    k = min(1.0, 6*dt)
    for key in ("dist", "h"):
        s[key] += (tgt[key]-s[key])*k
    if fwd and math.hypot(s["vx"], s["vhz"]) > 0.5:
        k2 = min(1.0, 0.6*dt)  # slow heading: jukes average out, runs swing it
        s["ax"] += (s["vx"]-s["ax"])*k2
        s["az"] += (s["vhz"]-s["az"])*k2
    if math.hypot(s["ax"], s["az"]) > 0.8:  # hold last angle when idle
        want = math.atan2(-s["ax"], s["az"])
        s["yaw"] += ((want-s["yaw"]+math.pi) % (2*math.pi)-math.pi)*min(1.0, 3.5*dt)
    lx, lz = s["hero"]+s["vx"]*_LEAD, s["hz"]+s["vhz"]*_LEAD
    want_c, want_l = cam_for(s["hero"], s["hz"], s["yaw"], s["dist"], s["h"], lx, lz)
    s["cam"] = [a+(b-a)*k for a, b in zip(s["cam"], want_c)]
    s["look"] = [a+(b-a)*k for a, b in zip(s["look"], want_l)]

_DIRS = None  # dirs cached per (cam, look); recomputed only when it moves
_DCAM = None
_L = None


def _band_dirs(cam, look, y0, y1):
    """ray dirs for scanlines y0..y1. one formula everywhere: identical floats."""
    fwd = sv.norm(sv.sub(look, cam))
    right = sv.norm((fwd[2], 0, -fwd[0]))
    up = (fwd[1]*right[2]-fwd[2]*right[1], fwd[2]*right[0]-fwd[0]*right[2],
          fwd[0]*right[1]-fwd[1]*right[0])
    W, H = sv.W, sv.H
    return [sv.norm((fwd[0]+(x/W*2-1)*0.8*right[0]+(1-y/H*2)*0.5*up[0],
                     fwd[1]+(x/W*2-1)*0.8*right[1]+(1-y/H*2)*0.5*up[1],
                     fwd[2]+(x/W*2-1)*0.8*right[2]+(1-y/H*2)*0.5*up[2]))
            for y in range(y0, y1) for x in range(W)]


def _setup():
    global _DIRS, _DCAM, _L
    _L = sv.norm((0.5, 1.0, -0.5))
    _DIRS = _band_dirs(sv.DEF_CAM, sv.DEF_LOOK, 0, sv.H)
    _DCAM = (tuple(sv.DEF_CAM), tuple(sv.DEF_LOOK))


def _prows(y0, spheres, boxes, casters, dirs, cam, fog):
    """raw PNG rows for scanlines y0... worker-safe, cam-threaded.

    fog None: pixel-identical to storyvid.render. fog (color, density):
    linear depth cueing + arena border + horizon melt. storyvid.py untouched.
    """
    Lx, Ly, Lz = _L
    ox, oy, oz = cam
    W = sv.W
    fc = fog[0] if fog is not None else None
    _sqrt = math.sqrt  # hoisted attr lookup; unpack stays: it beats indexing
    rows = []
    for i in range(len(dirs)//W):
        j = y0+i
        row = bytearray()
        for k in range(W):
            dx, dy, dz = dirs[i*W+k]
            bt, floor, col, sb, isbox, bax = -1.0, False, None, False, False, 0
            scx = scy = scz = 0.0
            if dy < -1e-6:
                tt = -oy/dy
                if tt > 1e-4:
                    bt, floor = tt, True
            for (sx, sy, sz), r, c in spheres:  # unpack beats indexing
                ocx, ocy, ocz = ox-sx, oy-sy, oz-sz
                b = ocx*dx+ocy*dy+ocz*dz
                disc = b*b-(ocx*ocx+ocy*ocy+ocz*ocz-r*r)
                if disc > 0:
                    tt = -b-_sqrt(disc)
                    if tt > 1e-4 and (bt < 0 or tt < bt):
                        bt, floor = tt, False
                        col, sb = c, c == _SUN
                        scx, scy, scz = sx, sy, sz
                        isbox = False
            for (bx, by, bz), (sx, sy, sz), bc in boxes:  # unrolled slab, same ops
                tmin, tmax, ba, hit = -1e9, 1e9, 0, True
                lo, hi = bx-sx/2, bx+sx/2
                if abs(dx) < 1e-9:
                    if ox < lo or ox > hi:
                        hit = False
                else:
                    t1, t2 = (lo-ox)/dx, (hi-ox)/dx
                    if t1 > t2:
                        t1, t2 = t2, t1
                    if t1 > tmin:
                        tmin, ba = t1, 0
                    if t2 < tmax:
                        tmax = t2
                    if tmin > tmax:
                        hit = False
                if hit:
                    lo, hi = by-sy/2, by+sy/2
                    if abs(dy) < 1e-9:
                        if oy < lo or oy > hi:
                            hit = False
                    else:
                        t1, t2 = (lo-oy)/dy, (hi-oy)/dy
                        if t1 > t2:
                            t1, t2 = t2, t1
                        if t1 > tmin:
                            tmin, ba = t1, 1
                        if t2 < tmax:
                            tmax = t2
                        if tmin > tmax:
                            hit = False
                if hit:
                    lo, hi = bz-sz/2, bz+sz/2
                    if abs(dz) < 1e-9:
                        if oz < lo or oz > hi:
                            hit = False
                    else:
                        t1, t2 = (lo-oz)/dz, (hi-oz)/dz
                        if t1 > t2:
                            t1, t2 = t2, t1
                        if t1 > tmin:
                            tmin, ba = t1, 2
                        if t2 < tmax:
                            tmax = t2
                        if tmin > tmax:
                            hit = False
                if hit:
                    tt = tmin if tmin > 1e-4 else (tmax if tmax > 1e-4 else 0.0)
                    if tt and (bt < 0 or tt < bt):
                        bt, floor, col, sb, isbox, bax = tt, False, bc, False, True, ba
            if bt < 0:
                s = dy if dy > 0 else 0
                cr, cg, cb = 135+90*s, 170+60*s, 220
                if fc is not None:
                    if s < 0.22:  # near horizon: downtown skyline blocks
                        az = math.atan2(dx, dz)
                        q = int(math.floor(az*3.0))
                        if s < 0.03+0.13*((q*73+41) % 16)/16:
                            win = (int(math.floor(az*36.0))+int(s*220.0)) % 9 == 0
                            cr, cg, cb = ((255, 200, 130) if win else (74, 80, 100))
                            f = max(0.0, 1.0-s*2.5)*0.5
                        else:
                            f = max(0.0, 1.0-s*2.5)
                    else:
                        f = max(0.0, 1.0-s*2.5)
                    cr += (fc[0]-cr)*f
                    cg += (fc[1]-cg)*f
                    cb += (fc[2]-cb)*f
                row += bytes((int(cr), int(cg), int(cb)))
                continue
            px, py, pz = ox+bt*dx, oy+bt*dy, oz+bt*dz
            if floor:
                nx, ny, nz = (0, 1, 0)
                col = (30, 30, 34) if (int(px)+int(pz)) % 2 == 0 else (215, 215, 220)
                if fc is not None:  # downtown grid: asphalt, dashes, sidewalks
                    on_x, on_z = abs(px) < 1.6, abs(pz) < 1.6
                    if on_x or on_z:
                        col = (36, 36, 44)
                        if (on_x and abs(px) < 0.12 and int(pz*1.2) % 2 == 0) or \
                           (on_z and abs(pz) < 0.12 and int(px*1.2) % 2 == 0):
                            col = (210, 180, 90)
                    elif abs(px) < 2.4 or abs(pz) < 2.4:
                        col = (140, 140, 148)
            elif isbox:
                n = [0, 0, 0]
                n[bax] = 1 if (dx, dy, dz)[bax] < 0 else -1
                nx, ny, nz = n
            else:
                l = math.sqrt((px-scx)*(px-scx)+(py-scy)*(py-scy)+(pz-scz)*(pz-scz))
                nx, ny, nz = (px-scx)/l, (py-scy)/l, (pz-scz)/l
            spx, spy, spz = px+nx*1e-3, py+ny*1e-3, pz+nz*1e-3
            sht = -1.0  # blocked under 40 is all shading needs; nearest iff all over
            if Ly < -1e-6:
                tt = -spy/Ly
                if tt > 1e-4:
                    sht = 0.5 if tt < 40 else tt
            if sht != 0.5:
                for (sx, sy, sz), r, c in casters:
                    ocx, ocy, ocz = spx-sx, spy-sy, spz-sz
                    b = ocx*Lx+ocy*Ly+ocz*Lz
                    disc = b*b-(ocx*ocx+ocy*ocy+ocz*ocz-r*r)
                    if disc > 0:
                        tt = -b-_sqrt(disc)
                        if tt > 1e-4:
                            if tt < 40:
                                sht = 0.5
                                break
                            elif sht < 0 or tt < sht:
                                sht = tt
            if sht != 0.5:
                for (bx, by, bz), (sx, sy, sz), bc in boxes:  # buildings throw shade
                    tmin, tmax, hit = -1e9, 1e9, True
                    lo, hi = bx-sx/2, bx+sx/2
                    if abs(Lx) < 1e-9:
                        if spx < lo or spx > hi:
                            hit = False
                    else:
                        t1, t2 = (lo-spx)/Lx, (hi-spx)/Lx
                        if t1 > t2:
                            t1, t2 = t2, t1
                        if t1 > tmin:
                            tmin = t1
                        if t2 < tmax:
                            tmax = t2
                        if tmin > tmax:
                            hit = False
                    if hit:
                        lo, hi = by-sy/2, by+sy/2
                        if abs(Ly) < 1e-9:
                            if spy < lo or spy > hi:
                                hit = False
                        else:
                            t1, t2 = (lo-spy)/Ly, (hi-spy)/Ly
                            if t1 > t2:
                                t1, t2 = t2, t1
                            if t1 > tmin:
                                tmin = t1
                            if t2 < tmax:
                                tmax = t2
                            if tmin > tmax:
                                hit = False
                    if hit:
                        lo, hi = bz-sz/2, bz+sz/2
                        if abs(Lz) < 1e-9:
                            if spz < lo or spz > hi:
                                hit = False
                        else:
                            t1, t2 = (lo-spz)/Lz, (hi-spz)/Lz
                            if t1 > t2:
                                t1, t2 = t2, t1
                            if t1 > tmin:
                                tmin = t1
                            if t2 < tmax:
                                tmax = t2
                            if tmin > tmax:
                                hit = False
                    if hit:
                        tt = tmin if tmin > 1e-4 else (tmax if tmax > 1e-4 else 0.0)
                        if tt:
                            if tt < 40:
                                sht = 0.5
                                break
                            elif sht < 0 or tt < sht:
                                sht = tt
            diff = nx*Lx+ny*Ly+nz*Lz
            if diff < 0:
                diff = 0
            if sht == 0.5 or (sht > 0 and sht < 40):
                diff *= 0.15
            m = 0.18+0.82*diff
            cr, cg, cb = col[0]*m, col[1]*m, col[2]*m
            if fc is not None and not sb:  # the sun burns through fog
                f = bt*fog[1] if bt*fog[1] < 1.0 else 1.0
                cr += (fc[0]-cr)*f
                cg += (fc[1]-cg)*f
                cb += (fc[2]-cb)*f
            row += bytes((min(255, int(cr)), min(255, int(cg)), min(255, int(cb))))
        rows.append(b'\x00'+bytes(row))
    return rows


def _write_png(raw, out):
    import struct as _st
    import zlib as _z

    def chunk(tag, data):
        c = _st.pack('>I', len(data))+tag+data
        return c+_st.pack('>I', _z.crc32(tag+data) & 0xffffffff)
    open(out, 'wb').write(b'\x89PNG\r\n\x1a\n'
          + chunk(b'IHDR', _st.pack('>IIBBBBB', sv.W, sv.H, 8, 2, 0, 0, 0))
          + chunk(b'IDAT', _z.compress(raw, 6)) + chunk(b'IEND', b''))


def fastrender(spheres, boxes, casters, out, cam, look, fog, ov=None):
    """storyvid.render inlined for the game: same pixels, no per-pixel calls.

    ponytail: spheres+floor only, boxes omitted — the game never spawns any.
    storyvid.py itself is untouched, so film rebuilds stay byte-identical.
    """
    global _DIRS, _DCAM
    key = (tuple(cam), tuple(look))
    if _DIRS is None or _DCAM != key:
        if _L is None:
            _setup()
        _DIRS = _band_dirs(cam, look, 0, sv.H)
        _DCAM = key
    raw = bytearray(b''.join(_prows(0, spheres, boxes, casters, _DIRS, cam, fog)))
    if ov is not None:
        _paste(raw, sv.W, sv.H, ov)
    _write_png(bytes(raw), out)


_WKEY, _WDIRS = None, None


def _band(job):
    y0, y1, cam, look, spheres, boxes, casters, fog = job
    global _WKEY, _WDIRS, _L
    if _L is None:  # spawn context: no fork inheritance
        _L = sv.norm((0.5, 1.0, -0.5))
    key = (y0, y1, tuple(cam), tuple(look))
    if _WKEY != key:
        _WDIRS = _band_dirs(cam, look, y0, y1)
        _WKEY = key
    return b''.join(_prows(y0, spheres, boxes, casters, _WDIRS, cam, fog))


_POOL = None
_BANDS = None


def pararender(spheres, boxes, casters, out, cam, look, fog, ov=None):
    """fastrender across a persistent pool; map keeps order, same bytes."""
    global _POOL, _BANDS
    from concurrent.futures import ProcessPoolExecutor
    if _POOL is None:
        _setup()  # fork inherits dirs+light; spawn workers rebuild lazily
        n = min(16, os.cpu_count() or 2)
        _POOL = ProcessPoolExecutor(mp_context=sv._CTX, max_workers=n)
        _BANDS = [(i*sv.H//n, (i+1)*sv.H//n) for i in range(n)]
    raw = bytearray(b''.join(_POOL.map(_band, [(a, b, cam, look, spheres, boxes, casters, fog)
                                               for a, b in _BANDS])))
    if ov is not None:
        _paste(raw, sv.W, sv.H, ov)
    _write_png(bytes(raw), out)


def step(s, mv, dt):
    """pure game logic (headless-testable). mv: dx scalar or (dx, dz, jump)."""
    if s["over"]:
        return True
    if s.get("paused"):
        return False
    dx, dz, jump = (mv, 0, False) if isinstance(mv, (int, float)) else mv
    s["hero"] += dx * HERO_SPEED * dt  # ponytail: unclamped, the camera follows
    s["hz"] += dz * HERO_SPEED * dt
    collide(s)  # buildings are solid
    k = min(1.0, 10*dt)  # smoothed velocity drives the camera lead
    s["vx"] += (dx*HERO_SPEED-s["vx"])*k
    s["vhz"] += (dz*HERO_SPEED-s["vhz"])*k
    spd = math.hypot(s["vx"], s["vhz"])  # stride phase + facing for the puppet
    s["ph"] += spd*dt*2.4
    if spd > 0.5:
        s["fx"], s["fz"] = s["vx"]/spd, s["vhz"]/spd
    if jump and s["y"] == 0:
        s["vy"] = JUMP_V
    if s["y"] > 0 or s["vy"] > 0:
        s["y"] = max(0.0, s["y"] + s["vy"] * dt)
        s["vy"] -= GRAV * dt
    d = math.hypot(s["hero"] - s["void"], s["hz"] - s["vz"]) or 1.0
    spd = VOID_SPEED + min(2.0, s["t"]*0.02)  # it hungers
    s["void"] += (s["hero"] - s["void"]) / d * spd * dt
    s["vz"] += (s["hz"] - s["vz"]) / d * spd * dt
    kept = []
    for cx, cz in s["coins"]:
        if math.hypot(s["hero"]-cx, s["hz"]-cz) < 0.7:
            s["score"] += 1
        else:
            kept.append((cx, cz))
    s["coins"] = kept
    s["t"] += dt
    if d < s["r"] * 0.9 and s["y"] < CLEAR_H:
        s["over"] = True
    return s["over"]


def manuel(hx, hy, hz, fx, fz, ph):
    """6-sphere puppet, torso first (it + head cast shadows). hands swing,
    feet scissor with stride phase; faces (fx, fz)."""
    sw, c = math.sin(ph), math.cos(ph)
    sx, sz = -fz, fx
    return [((hx, 1.05+hy, hz), 0.42, sv.RED),
            ((hx+fx*0.08, 1.62+hy, hz+fz*0.08), 0.24, (235, 200, 160)),
            ((hx+sx*0.45+fx*0.25*sw, 1.0+hy, hz+sz*0.45+fz*0.25*sw),
             0.13, (235, 200, 160)),
            ((hx-sx*0.45-fx*0.25*sw, 1.0+hy, hz-sz*0.45-fz*0.25*sw),
             0.13, (235, 200, 160)),
            ((hx+sx*0.18+fx*0.32*sw, 0.16+hy+0.18*max(0.0, c), hz+sz*0.18+fz*0.32*sw),
             0.15, (60, 50, 44)),
            ((hx-sx*0.18-fx*0.32*sw, 0.16+hy+0.18*max(0.0, -c), hz-sz*0.18-fz*0.32*sw),
             0.15, (60, 50, 44))]


def draw(root, canvas, img_label, score_label):
    hx, hz = state["hero"], state["hz"]
    bob = abs((time.monotonic()*10 % 6) - 3) * 0.08
    hy = state["y"] + bob
    void = ((state["void"], state["r"] * 0.9, state["vz"]), state["r"], (12, 12, 16))
    coins = [((cx, 0.3+0.1*math.sin(time.monotonic()*4+i*1.7), cz), 0.22, (255, 210, 90))
             for i, (cx, cz) in enumerate(state["coins"])]
    cam, look = tuple(state["cam"]), tuple(state["look"])
    fog = (_FOGC, _FOGD)
    ov = None
    if _HAVESPR:  # full FBX Manuel billboard; no puppet spheres in the scene
        b = bin_of(state["fx"], state["fz"])
        rgb, msk, sw, sh, ax, ay = _sprob(b, int(time.monotonic()*4) % 16)
        feet = project(cam, look, (hx, hy, hz))
        gnd = project(cam, look, (hx, 0.0, hz))
        actors = [void]
        casters = actors + list(WORLD[1:4])  # void + mountains only
        if feet is not None and gnd is not None:
            sc = 7.0/feet[2]
            tw, th = max(1, round(sw*sc)), max(1, round(sh*sc))
            ov = (rgb, msk, sw, sh, round(feet[0]-ax*sc), round(feet[1]-ay*sc),
                  tw, th, round(gnd[0]), round(gnd[1])+2,
                  max(2, round(8*sc)), max(1, round(3*sc)))
    else:
        actors = manuel(hx, hy, hz, state["fx"], state["fz"], state["ph"]) + [void]
        casters = actors[:2] + [actors[6]] + list(WORLD[1:4])
    spheres = list(WORLD) + actors + coins
    try:
        pararender(spheres, CITY, casters, TMP, cam, look, fog, ov)
    except Exception:
        fastrender(spheres, CITY, casters, TMP, cam, look, fog, ov)  # pool: serial
    img = tk.PhotoImage(file=TMP).zoom(ZOOM, ZOOM)
    img_label.configure(image=img)
    img_label.image = img  # keep ref
    if state["over"]:
        msg = "THE VOID GOT MANUEL - R restart, Q quit"
    elif state.get("paused"):
        msg = "PAUSED - P resume"
    else:
        msg = "W fwd  A/D strafe  Shift sprint  Space jump  wheel zoom"
    score_label.configure(text=f"t={state['t']:.1f}s  coins={state['score']}  {msg}")


def main():
    global ZOOM
    root = tk.Tk()
    root.title("dodge the void")
    root.configure(bg="black")
    root.attributes("-fullscreen", True)
    ZOOM = max(2, (root.winfo_screenheight() - 60) // sv.H)
    score = tk.Label(root, text="", font=("monospace", 10), bg="black", fg="white")
    score.pack()
    img_label = tk.Label(root, bg="black")
    img_label.pack(expand=True)
    canvas = None
    held, jump = set(), {"go": False}

    def on_key(e):
        k = e.keysym.lower()
        if k == "f11":
            root.attributes("-fullscreen", not root.attributes("-fullscreen"))
        elif k == "escape":
            root.attributes("-fullscreen", False) if root.attributes("-fullscreen") else root.destroy()
        elif k == "q":
            root.destroy()
        elif k == "p" and not state["over"]:
            state["paused"] = not state["paused"]
        elif k in ("r", "space", "return") and state["over"]:
            keep = {k2: state[k2] for k2 in ("yaw", "dist", "h", "cam", "look")}
            state.update(fresh())
            state.update(keep)  # camera survives restart
        elif k == "space":
            jump["go"] = True
        else:
            held.add(k)

    def on_release(e):
        held.discard(e.keysym.lower())

    root.bind("<KeyPress>", on_key)
    root.bind("<KeyRelease>", on_release)
    SH = root.winfo_screenheight()

    def on_move(e):  # mouse height; yaw trails behind motion, wheel dollies
        _TGT["h"] = 1.0+(e.y/SH)*2.5

    def on_wheel(e, d):
        _TGT["dist"] = max(4.0, min(10.0, _TGT["dist"]+d))

    root.bind("<Motion>", on_move)
    root.bind("<Button-4>", lambda e: on_wheel(e, -0.5))
    root.bind("<Button-5>", lambda e: on_wheel(e, 0.5))
    root.bind("<MouseWheel>", lambda e: on_wheel(e, -0.5 if e.delta > 0 else 0.5))

    def tick():
        t0 = time.monotonic()
        ix = (("d" in held or "right" in held) - ("a" in held or "left" in held))
        iz = (("w" in held or "up" in held) - ("s" in held or "down" in held))
        j, jump["go"] = jump["go"], False
        mult = 1.6 if ("shift_l" in held or "shift_r" in held) else 1.0
        dx, dz = cam_move(ix, iz, state["yaw"])
        while len(state["coins"]) < 5:  # the world restocks around you
            a = random.uniform(0, 6.283)
            r = random.uniform(6.0, 10.0)
            state["coins"].append((state["hero"]+r*math.cos(a), state["hz"]+r*math.sin(a)))
        move_cam(state, _TGT, TICK_MS/1000, fwd=(iz == 1 and ix == 0))
        step(state, (dx*mult, dz*mult, j), TICK_MS/1000)
        draw(root, canvas, img_label, score)
        root.after(max(1, int(TICK_MS-(time.monotonic()-t0)*1000)), tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    if "--selftest" in sys.argv:  # ponytail: one runnable check for step + bands
        s = fresh()
        assert step(s, 0, 0.1) is False and abs(s["t"]-0.1) < 1e-9
        s = fresh()
        s.update(hero=0.0, void=0.1)
        assert step(s, (0, 0, False), 0.033) is True
        s = fresh()
        step(s, (0, 0, True), 0.033)
        assert s["y"] > 0  # jump leaves the ground
        s.update(hero=0.0, void=0.1)
        s["y"] = 1.0
        assert step(s, (0, 0, False), 0.033) is False  # jump clears the void
        s = fresh()
        s["paused"] = True
        assert step(s, 1, 0.033) is False and s["t"] == 0
        sph = [((0, 1.05, 0), 0.42, sv.RED)]
        dc, dl = tuple(sv.DEF_CAM), tuple(sv.DEF_LOOK)
        fastrender(sph, [], sph, '/tmp/s.png', dc, dl, None)
        pararender(sph, [], sph, '/tmp/p.png', dc, dl, None)
        assert open('/tmp/s.png', 'rb').read() == open('/tmp/p.png', 'rb').read()
        c, l = cam_for(1.5, -1.0, 0.6, 8.0, 3.0)  # moved orbit cam
        fastrender(sph, [], sph, '/tmp/s2.png', c, l, None)
        pararender(sph, [], sph, '/tmp/p2.png', c, l, None)
        assert open('/tmp/s2.png', 'rb').read() == open('/tmp/p2.png', 'rb').read()
        sv.render(c, l, sph, [], '/tmp/r2.png')
        assert open('/tmp/s2.png', 'rb').read() == open('/tmp/r2.png', 'rb').read()
        f = (_FOGC, _FOGD)
        full = list(WORLD) + sph
        fastrender(full, [], full, '/tmp/s3.png', c, l, f)
        pararender(full, [], full, '/tmp/p3.png', c, l, f)
        assert open('/tmp/s3.png', 'rb').read() == open('/tmp/p3.png', 'rb').read()
        fastrender(full, [], full, '/tmp/s4.png', c, l, None)
        assert open('/tmp/s3.png', 'rb').read() != open('/tmp/s4.png', 'rb').read()
        split = sph + list(WORLD[1:4])  # actors + mountains cast; rest don't
        fastrender(full, [], split, '/tmp/s5.png', c, l, f)
        pararender(full, [], split, '/tmp/p5.png', c, l, f)
        assert open('/tmp/s5.png', 'rb').read() == open('/tmp/p5.png', 'rb').read()
        bx2 = [((3.0, 1.0, 2.0), (2.0, 2.0, 2.0), (120, 120, 130)),
               ((-3.0, 0.5, -2.0), (1.0, 1.0, 1.0), (100, 100, 110))]
        fastrender(sph, bx2, sph, '/tmp/s6.png', c, l, None)
        pararender(sph, bx2, sph, '/tmp/p6.png', c, l, None)
        assert open('/tmp/s6.png', 'rb').read() == open('/tmp/p6.png', 'rb').read()
        sv.render(c, l, sph, bx2, '/tmp/r6.png')
        assert open('/tmp/s6.png', 'rb').read() == open('/tmp/r6.png', 'rb').read()
        hit = fresh()  # buildings are solid
        hit.update(hero=-4.5, hz=-6.0)
        collide(hit)
        assert abs(hit["hero"]+4.5) > 0.1 or abs(hit["hz"]+6.0) > 0.1
        c0, l0 = cam_for(0, 0, 0, 7, 2.2)
        assert abs(c0[0]-dc[0]) < 1e-9 and abs(l0[1]-1.2) < 1e-9  # classic view
        m = fresh()
        m.update(hero=1.5, hz=-1.0, vx=-math.sin(0.6)*3.5, vhz=math.cos(0.6)*3.5)
        for _ in range(200):
            move_cam(m, {"dist": 8.0, "h": 3.0}, 0.033, fwd=True)
        assert abs(m["yaw"]-0.6) < 1e-3 and abs(m["cam"][0]-c[0]) < 1e-3
        idle = fresh()
        idle["yaw"] = 0.3
        move_cam(idle, {"dist": 7.0, "h": 2.2}, 0.033)
        assert idle["yaw"] == 0.3  # idle holds the angle
        juke = fresh()
        for i in range(120):  # rapid direction flips, strafe-style: no fwd
            juke["vx"] = 3.5 if i % 10 < 5 else -3.5
            move_cam(juke, {"dist": 7.0, "h": 2.2}, 0.04)
        assert abs(juke["yaw"]) < 0.05  # strafes never spin the camera
        spin = fresh()  # the old bug: sustained strafe velocity spun it 360
        spin.update(vx=3.5, vhz=0.0)
        for _ in range(300):
            move_cam(spin, {"dist": 7.0, "h": 2.2}, 0.04)
        assert abs(spin["yaw"]) < 0.05
        assert bin_of(0, -1) == 4 and bin_of(0, 1) == 0  # camera / away
        assert bin_of(1, 0) == 2 and bin_of(-1, 0) == 6
        pc = project(tuple(sv.DEF_CAM), tuple(sv.DEF_LOOK), (0, 0, 0))
        assert abs(pc[0]-sv.W/2) < 1e-9 and 0 < pc[1] < sv.H  # origin centers
        raw = bytearray(b'\x00'+b'\x00'*6+b'\x00'+b'\x00'*6)  # 2x2 black rows
        rgb = [bytes((255, 0, 0, 0, 255, 0)), bytes((0, 0, 255, 255, 255, 255))]
        msk = [bytes((255, 255, 255, 0, 0, 0)), bytes((0, 0, 0, 255, 255, 255))]
        _paste(raw, 2, 2, (rgb, msk, 2, 2, 0, 0, 2, 2, 0, 5, 0, 0))
        assert raw[1:4] == bytes((255, 0, 0)) and raw[4:7] == bytes(3)
        assert raw[8:11] == bytes(3) and raw[11:14] == bytes((255, 255, 255))
        assert cam_move(0, 1, 0) == (0, 1)  # W means away from camera
        assert cam_move(1, 0, 0) == (1, 0)  # D strafes screen-right
        dx, dz = cam_move(0, 1, -math.pi/2)
        assert abs(dx-1) < 1e-9 and abs(dz) < 1e-9  # still forward after swing
        g = fresh()  # coins: grab the near one, keep the far one
        g.update(hero=0.0, hz=0.0, coins=[(0.3, 0.0), (5.0, 5.0)])
        step(g, (0, 0, False), 0.04)
        assert g["score"] == 1 and g["coins"] == [(5.0, 5.0)]
        r1, r2 = fresh(), fresh()  # the hunger ramps with age
        r2["t"] = 100.0
        step(r1, (0, 0, False), 1.0)
        step(r2, (0, 0, False), 1.0)
        assert r2["void"] < r1["void"]
        pup = manuel(0, 0, 0, 0, 1, math.pi/2)  # facing +z, mid-stride
        assert len(pup) == 6 and pup[0][1] == 0.42  # torso first (casts shadow)
        assert abs(pup[4][0][2]-0.32) < 1e-9 and abs(pup[5][0][2]+0.32) < 1e-9
        side = manuel(0, 0, 0, 1, 0, math.pi/2)  # facing rotates the stride
        assert abs(side[4][0][0]-0.32) < 1e-9 and abs(side[5][0][0]+0.32) < 1e-9
        v = fresh()  # velocity tracks input, gaze leads motion
        step(v, (1, 0, False), 0.04)
        assert v["vx"] > 0 and v["vhz"] == 0
        v.update(vx=3.5, vhz=0.0, hero=0.0, hz=0.0)
        for _ in range(200):
            move_cam(v, {"dist": 7.0, "h": 2.2}, 0.033, fwd=True)
        assert abs(v["look"][0]-3.5*_LEAD) < 1e-3 and abs(v["look"][2]) < 1e-3
        assert abs(v["yaw"]+math.pi/2) < 0.05  # swung behind +x motion
        print("selftest ok")
    else:
        main()
