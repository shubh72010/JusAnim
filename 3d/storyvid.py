#!/usr/bin/env python3
"""storyvid: make tiny raytraced story videos from a JSON script.

Usage: python3 storyvid.py story.json out.mp4
Each beat: {"caption": "...", "red": x_or_null, "blue": x_or_null,
            "void": {"x": x, "r": r}_or_null, "hop": true_or_false}
People walk from their previous visible x to the new x over the beat; null hides them.
"""
import struct, zlib, math, sys, os, json, subprocess, tempfile

W, H, FPS, BEAT_FRAMES = 320, 200, 10, 12
FONT = "/usr/share/fonts/truetype/liberation-sans-fonts/LiberationSans-Regular.ttf"
RED, BLUE, WHITE = (220, 70, 70), (70, 120, 230), (245, 245, 245)

def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def norm(v):
    l = math.sqrt(dot(v, v)); return (v[0]/l, v[1]/l, v[2]/l)

def render(cam, spheres, out):
    look = (0, 1.2, 0)
    fwd = norm(sub(look, cam)); right = norm((fwd[2], 0, -fwd[0]))
    up = (fwd[1]*right[2]-fwd[2]*right[1], fwd[2]*right[0]-fwd[0]*right[2], fwd[0]*right[1]-fwd[1]*right[0])
    L = norm((0.5, 1.0, -0.5))
    def hit(o, d):
        best = None
        if d[1] < -1e-6:
            tt = -o[1]/d[1]
            if tt > 1e-4: best = (tt, 'floor', None)
        for c, r, col in spheres:
            oc = sub(o, c); b = dot(oc, d); cc = dot(oc, oc)-r*r; disc = b*b-cc
            if disc > 0:
                tt = -b-math.sqrt(disc)
                if tt > 1e-4 and (best is None or tt < best[0]): best = (tt, col, c)
        return best
    def shade(o, d):
        h = hit(o, d)
        if h is None:
            s = max(0, d[1]); return (135+90*s, 170+60*s, 220)
        tt, col, c = h
        p = (o[0]+tt*d[0], o[1]+tt*d[1], o[2]+tt*d[2])
        if col == 'floor':
            n = (0, 1, 0)
            col = (30, 30, 34) if (int(p[0])+int(p[2])) % 2 == 0 else (215, 215, 220)
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

def main():
    story = json.load(open(sys.argv[1]))
    out_mp4 = sys.argv[2]
    tmp = tempfile.mkdtemp()
    n = 0
    for i, b in enumerate(story):
        prev = {}
        for k, person_key in enumerate(('red', 'blue', 'white', 'void')):
            for pb in story[:i]:
                if pb.get(person_key) is not None: prev[person_key] = pb[person_key]
        for k in range(BEAT_FRAMES):
            t = k / BEAT_FRAMES
            spheres = []
            for key, col in (('red', RED), ('blue', BLUE), ('white', WHITE)):
                target = b.get(key)
                if target is None: continue
                start = prev[key] if key in prev else target
                x = start + (target - start) * t
                hop = abs(math.sin(k*0.5))*0.25 if b.get('hop') else 0.0
                spheres += person(x, hop, col)
            v = b.get('void')
            if v:
                pv = prev.get('void')
                sx = pv['x'] if pv else v['x']; sr = pv['r'] if pv else v['r']
                vx = sx + (v['x']-sx)*t; vr = sr + (v['r']-sr)*t
                spheres.append(((vx, vr*0.9, 0), vr, (12, 12, 16)))
            f = os.path.join(tmp, f'f{n:04d}.png')
            render((0, 2.2, -7.0), spheres, f)
            n += 1
    caps = []
    for i, b in enumerate(story):
        c = b.get('caption', '').replace("'", '').replace(':', '')
        if c:
            caps.append(f"drawtext=fontfile={FONT}:text='{c}':fontcolor=white:fontsize=18:x=(w-text_w)/2:y=h-38:enable='between(t,{i*BEAT_FRAMES/FPS},{(i+1)*BEAT_FRAMES/FPS})'")
    filt = os.path.join(tmp, 'caps.txt')
    open(filt, 'w').write(','.join(caps))
    subprocess.run(['ffmpeg', '-y', '-framerate', str(FPS), '-i', os.path.join(tmp, 'f%04d.png'),
                    '-filter_script:v', filt, '-pix_fmt', 'yuv420p', out_mp4], check=True)
    print('wrote', out_mp4)

if __name__ == '__main__':
    main()
