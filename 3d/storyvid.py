#!/usr/bin/env python3
"""storyvid: make tiny raytraced story videos from a JSON script.

Usage: python3 storyvid.py story.json out.mp4 [--jobs N]
Frames render in parallel (fork context where available); --jobs defaults
to min(8, cores) — tune to the machine, oversubscription slows it down.
Legacy beat: {"caption": "...", "red": x_or_null, "blue": x_or_null,
            "void": {"x": x, "r": r}_or_null, "hop": true_or_false}
Boundless beat: {"caption": "...", "camera": [x,y,z], "look": [x,y,z],
            "objects": [{"id": "hero", "shape": "person"|"sphere"|"box",
            "pos": [x,y,z], "x": x, "y": y, "z": z, "r": r,
            "size": [sx,sy,sz], "color": [r,g,b], "hop": bool}]}
Story may be a list of beats, or {"settings": {"W":..,"H":..,"FPS":..,"BEAT_FRAMES":..},
"beats": [...]}. Any count of objects, any positions, any colors.
People walk from their previous visible pos to the new pos over the beat.
"""
import struct, zlib, math, sys, os, json, subprocess, tempfile
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

try:
    _CTX = mp.get_context('fork')  # workers inherit state; no re-exec per worker
except ValueError:  # non-POSIX: fall back to the platform default
    _CTX = None

W, H, FPS, BEAT_FRAMES = 320, 200, 10, 12
FONT = "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf"
RED, BLUE, WHITE = (220, 70, 70), (70, 120, 230), (245, 245, 245)
NAMED = {'red': RED, 'blue': BLUE, 'white': WHITE, 'black': (12, 12, 16),
         'skin': (235, 200, 160), 'void': (12, 12, 16)}
DEF_CAM, DEF_LOOK = (0, 2.2, -7.0), (0, 1.2, 0)

def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def norm(v):
    l = math.sqrt(dot(v, v)); return (v[0]/l, v[1]/l, v[2]/l)

def render(cam, look, spheres, boxes, out):
    fwd = norm(sub(look, cam)); right = norm((fwd[2], 0, -fwd[0]))
    up = (fwd[1]*right[2]-fwd[2]*right[1], fwd[2]*right[0]-fwd[0]*right[2], fwd[0]*right[1]-fwd[1]*right[0])
    L = norm((0.5, 1.0, -0.5))
    def ray_box(o, d, c, s):
        tmin, tmax, axis = -1e9, 1e9, 0
        for i in range(3):
            lo, hi = c[i]-s[i]/2, c[i]+s[i]/2
            if abs(d[i]) < 1e-9:
                if o[i] < lo or o[i] > hi: return None
            else:
                t1, t2 = (lo-o[i])/d[i], (hi-o[i])/d[i]
                if t1 > t2: t1, t2 = t2, t1
                if t1 > tmin: tmin, axis = t1, i
                tmax = min(tmax, t2)
                if tmin > tmax: return None
        t = tmin if tmin > 1e-4 else (tmax if tmax > 1e-4 else None)
        return (t, axis) if t else None
    def hit(o, d):
        best = None
        if d[1] < -1e-6:
            tt = -o[1]/d[1]
            if tt > 1e-4: best = (tt, 'floor', None, 0)
        for c, r, col in spheres:
            oc = sub(o, c); b = dot(oc, d); cc = dot(oc, oc)-r*r; disc = b*b-cc
            if disc > 0:
                tt = -b-math.sqrt(disc)
                if tt > 1e-4 and (best is None or tt < best[0]): best = (tt, col, c, -1)
        for c, s, col in boxes:
            rb = ray_box(o, d, c, s)
            if rb and (best is None or rb[0] < best[0]): best = (rb[0], col, c, rb[1])
        return best
    def shade(o, d):
        h = hit(o, d)
        if h is None:
            s = max(0, d[1]); return (135+90*s, 170+60*s, 220)
        tt, col, c, kind = h
        p = (o[0]+tt*d[0], o[1]+tt*d[1], o[2]+tt*d[2])
        if col == 'floor':
            n = (0, 1, 0)
            col = (30, 30, 34) if (int(p[0])+int(p[2])) % 2 == 0 else (215, 215, 220)
        elif kind >= 0:
            n = [0, 0, 0]; n[kind] = 1 if d[kind] < 0 else -1; n = tuple(n)
        else:
            n = norm(sub(p, c))
        sp = (p[0]+n[0]*1e-3, p[1]+n[1]*1e-3, p[2]+n[2]*1e-3)
        sh = hit(sp, L)
        diff = max(0, dot(n, L))
        if sh is not None and sh[0] < 40: diff *= 0.15
        return tuple(min(255, ch*(0.18+0.82*diff)) for ch in col)
    rows = []
    for y in range(H):
        row = bytearray()
        for x in range(W):
            u = (x/W*2-1)*0.8; v = (1-y/H*2)*0.5
            d = norm((fwd[0]+u*right[0]+v*up[0], fwd[1]+u*right[1]+v*up[1], fwd[2]+u*right[2]+v*up[2]))
            r, g, b = shade(cam, d)
            row += bytes((int(r), int(g), int(b)))
        rows.append(b'\x00'+bytes(row))
    raw = b''.join(rows)
    def chunk(tag, data):
        c = struct.pack('>I', len(data))+tag+data
        return c+struct.pack('>I', zlib.crc32(tag+data)&0xffffffff)
    png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)) \
          + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')
    open(out, 'wb').write(png)

def person(x, y, col):
    return [((x, 1.05+y, 0), 0.42, col), ((x, 1.62+y, 0), 0.24, (235, 200, 160))]

def _col(v, default):
    if v is None: return default
    if isinstance(v, str): return NAMED.get(v, default)
    return tuple(v)


_TW = {}
def _font_measure():
    if 'm' in _TW: return _TW['m']
    try:
        import struct as _st
        d = open(FONT, 'rb').read()
        n = _st.unpack('>H', d[4:6])[0]
        t = {}
        for i in range(n):
            tag, _, off, _ln = _st.unpack('>4sIII', d[12+i*16:28+i*16])
            t[tag] = off
        upm = _st.unpack('>H', d[t[b'head']+18:t[b'head']+20])[0]
        nh = _st.unpack('>H', d[t[b'hhea']+34:t[b'hhea']+36])[0]
        adv = [_st.unpack('>H', d[t[b'hmtx']+i*4:t[b'hmtx']+i*4+2])[0] for i in range(nh)]
        co = t[b'cmap']
        nc = _st.unpack('>H', d[co+2:co+4])[0]
        cmap = {}
        for i in range(nc):
            sub = co + _st.unpack('>I', d[co+8+i*8:co+12+i*8])[0]
            if _st.unpack('>H', d[sub:sub+2])[0] != 4:
                continue
            seg = _st.unpack('>H', d[sub+6:sub+8])[0] // 2
            rb = sub + 14
            ends = _st.unpack('>'+'H'*seg, d[rb:rb+seg*2])
            starts = _st.unpack('>'+'H'*seg, d[rb+seg*2+2:rb+seg*4+2])
            deltas = _st.unpack('>'+'h'*seg, d[rb+seg*4+2:rb+seg*6+2])
            ro = _st.unpack('>'+'H'*seg, d[rb+seg*6+2:rb+seg*8+2])
            rob = rb + seg*6 + 2
            for s in range(seg):
                st, e = starts[s], ends[s]
                if st == 0xFFFF or e - st > 5000:
                    continue
                for c in range(st, e+1):
                    if ro[s] == 0:
                        g = (c + deltas[s]) & 0xFFFF
                    else:
                        a = rob + s*2 + ro[s] + 2*(c - st)
                        g = _st.unpack('>H', d[a:a+2])[0]
                        if g:
                            g = (g + deltas[s]) & 0xFFFF
                    if g:
                        cmap[c] = g
        _TW['m'] = (adv, upm, cmap)
    except Exception:
        _TW['m'] = None
    return _TW['m']

def _text_w(s, fs):
    m = _font_measure()
    if m is None:
        return len(s)*fs*0.55
    adv, upm, cmap = m
    w = 0
    for c in s:
        g = cmap.get(ord(c), 0)
        w += adv[g] if g < len(adv) else adv[-1]
    return w/upm*fs

def _fit_lines(text, fs, max_w):
    lines, cur = [], ''
    for w in text.split():
        t = f'{cur} {w}'.strip()
        if _text_w(t, fs) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            while _text_w(w, fs) > max_w:
                k = next((i for i in range(len(w), 0, -1) if _text_w(w[:i], fs) <= max_w), 1)
                lines.append(w[:k])
                w = w[k:]
            cur = w
    if cur:
        lines.append(cur)
    return lines or ['']

def caption_filters(raw, i):
    raw = raw.replace("'", '').replace(':', '')
    if not raw.strip():
        return []
    fs, lines = 10, _fit_lines(raw, 10, W-16)
    for f in range(18, 9, -2):
        cand = _fit_lines(raw, f, W-16)
        if len(cand)*(f+6) <= max(60, H*0.45):
            fs, lines = f, cand
            break
    out, L = [], len(lines)
    for j, ln in enumerate(lines):
        y = H-38-(L-1-j)*(fs+6)
        out.append(f"drawtext=fontfile={FONT}:text='{ln}':fontcolor=white:fontsize={fs}:x=(w-text_w)/2:y={y}:enable='between(t,{i*BEAT_FRAMES/FPS},{(i+1)*BEAT_FRAMES/FPS})'")
    return out

def _pos(o):
    if 'pos' in o:
        p = list(o['pos']) + [0, 0, 0]
        return [float(p[0]), float(p[1]), float(p[2])]
    return [float(o.get('x', 0)), float(o.get('y', 0)), float(o.get('z', 0))]

def _lerp(a, b, t):
    return [ai+(bi-ai)*t for ai, bi in zip(a, b)]

def legacy_objects(b):
    objs = []
    for key, col in (('red', RED), ('blue', BLUE), ('white', WHITE)):
        if b.get(key) is not None:
            objs.append({'id': key, 'shape': 'person', 'x': b[key], 'color': list(col),
                         'hop': bool(b.get('hop'))})
    v = b.get('void')
    if v:
        objs.append({'id': 'void', 'shape': 'sphere', 'x': v['x'], 'y': v['r']*0.9,
                     'z': 0, 'r': v['r'], 'color': [12, 12, 16]})
    return objs

def _jobs(args):
    if '--jobs' in args:
        return int(args[args.index('--jobs') + 1])
    return min(8, os.cpu_count() or 2)


def _render_job(job):
    n, cam, look, spheres, boxes, path = job
    render(cam, look, spheres, boxes, path)
    return n


def main():
    global W, H, FPS, BEAT_FRAMES
    if '--selftest' in sys.argv:  # ponytail: one runnable check for the box math
        assert render.__code__.co_name == 'render'
        import subprocess as _s
        _s.run([sys.executable, '-c',
            'import sys; sys.argv=["x"]; exec(open("storyvid.py").read().split("def main")[0])'
            '\nassert _pos({"x":1})==[1.0,0,0] and _pos({"pos":[1,2]})==[1.0,2.0,0]'
            '\nassert _col("red",None)==(220,70,70) and _col([1,2,3],None)==(1,2,3)'], check=True)
        nasty = 'WWWWWWWWWW ' + 'This caption is far too long for one line. ' * 6
        for f in range(10, 19, 2):
            for ln in _fit_lines(nasty, f, W-16):
                assert _text_w(ln, f) <= W-16 + 1e-6, (f, ln)
        assert len(caption_filters(nasty, 0)) >= 2
        print('selftest ok')
        return
    args = []
    skip = False
    for a in sys.argv[1:]:
        if skip:
            skip = False
            continue
        if a == '--jobs':
            skip = True
            continue
        args.append(a)
    doc = json.load(open(args[0]))
    beats = doc['beats'] if isinstance(doc, dict) and 'beats' in doc else doc
    cfg = doc.get('settings', {}) if isinstance(doc, dict) else {}
    W, H, FPS = cfg.get('W', W), cfg.get('H', H), cfg.get('FPS', FPS)
    BEAT_FRAMES = cfg.get('BEAT_FRAMES', BEAT_FRAMES)
    out_mp4 = args[1]
    tmp = tempfile.mkdtemp()
    n = 0
    prev, prev_r = {}, {}
    prev_cam_p = list(cfg.get('camera', list(DEF_CAM)))
    prev_look_p = list(cfg.get('look', list(DEF_LOOK)))
    jobs = []  # frames are independent once interpolated: render in parallel
    for i, b in enumerate(beats):
        objs = list(b.get('objects', [])) + legacy_objects(b)
        cam_t = list(b.get('camera', prev_cam_p))
        look_t = list(b.get('look', prev_look_p))
        cam_s, look_s = (prev_cam_p, prev_look_p) if i else (cam_t, look_t)
        for k in range(BEAT_FRAMES):
            t = k / BEAT_FRAMES
            spheres, boxes = [], []
            for j, o in enumerate(objs):
                oid = o.get('id', f'obj{j}')
                shape = o.get('shape', 'sphere')
                tgt = _pos(o)
                hop = (abs(math.sin(k*0.5))*0.25
                       if o.get('hop', b.get('hop', False)) else 0.0)
                cur = _lerp(prev.get(oid, tgt), tgt, t)
                cur[1] += hop if shape == 'person' else 0.0
                col = _col(o.get('color'), (245, 245, 245))
                if shape == 'person':
                    spheres.append(((cur[0], 1.05+cur[1], cur[2]), 0.42, col))
                    spheres.append(((cur[0], 1.62+cur[1], cur[2]), 0.24, (235, 200, 160)))
                elif shape == 'box':
                    s = list(o.get('size', [1, 1, 1])) + [1, 1, 1]
                    boxes.append((tuple(cur), tuple(float(x) for x in s[:3]), col))
                else:
                    _r = float(o.get('r', 0.5))
                    cur_r = prev_r.get(oid, _r) + (_r - prev_r.get(oid, _r)) * t
                    spheres.append((tuple(cur), cur_r, col))
            f = os.path.join(tmp, f'f{n:04d}.png')
            jobs.append((n, tuple(_lerp(cam_s, cam_t, t)), tuple(_lerp(look_s, look_t, t)),
                         spheres, boxes, f))
            n += 1
        for j, o in enumerate(objs):
            prev[o.get('id', f'obj{j}')] = _pos(o)
            prev_r[o.get('id', f'obj{j}')] = float(o.get('r', 0.5))
        prev_cam_p, prev_look_p = cam_t, look_t
    with ProcessPoolExecutor(mp_context=_CTX, max_workers=_jobs(sys.argv)) as ex:  # map keeps order; same bytes as serial
        for _ in ex.map(_render_job, jobs):
            pass
    caps = []
    for i, b in enumerate(beats):
        caps += caption_filters(b.get('caption', ''), i)
    cmd = ['ffmpeg', '-y', '-framerate', str(FPS), '-i', os.path.join(tmp, 'f%04d.png')]
    if caps:  # empty filter script makes ffmpeg exit 234
        filt = os.path.join(tmp, 'caps.txt')
        open(filt, 'w').write(','.join(caps))
        cmd += ['-filter_script:v', filt]
    subprocess.run(cmd + ['-pix_fmt', 'yuv420p', out_mp4], check=True)
    print('wrote', out_mp4)

if __name__ == '__main__':
    main()
