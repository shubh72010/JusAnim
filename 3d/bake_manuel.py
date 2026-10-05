#!/usr/bin/env python3
"""bake_manuel: sprite sheet for game Manuel from the real FBX dance.

Usage: python3 bake_manuel.py [fbx] [outdir]
Renders NBIN yaw bins x NPH dance phases (small, pooled) plus one empty
frame; each sprite = cropped RGB + mask (mask = diff vs empty). Outdir is a
build artifact (gitignored); the game falls back to the puppet without it.
"""
import math
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fbx_rig import (_load_rig, _load_mesh, _pose_globals, _mat_inv4, _mmul,
                     _winit, _wframe)
from multiprocessing import Pool

SKIN = (235, 200, 160)


def game_col(nm):
    """natural palette for game Manuel. films keep their marker colors."""
    if nm in ('head', 'neck', 'jaw', 'eye_l', 'eye_r', 'eyebrow_l', 'eyebrow_r',
              'eyelid_l', 'eyelid_r', 'mouth_l', 'mouth_r'):
        return SKIN
    if 'hand' in nm or 'lowerarm' in nm or \
            any(f in nm for f in ('index', 'middle', 'ring', 'pinky', 'thumb')):
        return SKIN
    if 'upperleg' in nm or 'lowerleg' in nm:
        return (45, 50, 65)  # jeans
    if 'foot' in nm or 'ball' in nm:
        return (60, 48, 38)  # boots
    return (80, 130, 220)  # shirt

FBX = '/tmp/opencode/rp_manuel_animated_001_dancing.fbx'
NBIN, NPH = 8, 16
SW, SH = 128, 128
CAM, LOOK = (0, 2.2, -7.0), (0, 1.2, 0)


def chunk(tag, data):
    c = struct.pack('>I', len(data))+tag+data
    return c+struct.pack('>I', zlib.crc32(tag+data) & 0xffffffff)


def write_png(path, w, h, raw):
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def read_png(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n'
    i, ids, w, h = 8, b'', 0, 0
    while i < len(d):
        ln = int.from_bytes(d[i:i+4], 'big')
        tag = d[i+4:i+8]
        if tag == b'IHDR':
            w, h = struct.unpack('>II', d[i+8:i+16])
        elif tag == b'IDAT':
            ids += d[i+8:i+8+ln]
        i += 12+ln
    r = zlib.decompress(ids)
    rows, p = [], 0
    for _ in range(h):
        assert r[p] == 0
        rows.append(r[p+1:p+1+w*3])
        p += w*3+1
    return w, h, rows


def main():
    fbx = sys.argv[1] if len(sys.argv) > 1 else FBX
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'manuel_spr')
    os.makedirs(out, exist_ok=True)
    rig = _load_rig(fbx)
    models = rig['models']
    mesh = _load_mesh(fbx)
    print(f"mesh: {len(mesh['verts'])} verts, {len(mesh['tris'])} tris")
    blist = mesh['bones']
    bnames = [models[b]['name'].split('dancing_')[-1] for b in blist]
    dom = {}
    for vi, lst in mesh['infl'].items():
        dom[vi] = max(lst, key=lambda t: t[1])[0]
    tris = []
    for a, b, c in mesh['tris']:
        votes = [dom.get(a, 0), dom.get(b, 0), dom.get(c, 0)]
        tris.append((a, b, c, tuple(game_col(bnames[max(set(votes), key=votes.count)]))))
    n = int(rig['tmax'] * 10)
    beats = [min(b, n-1) for b in range(0, min(n, 48), 3)][:NPH]
    Gmap = {bi: _pose_globals(rig, bi/10) for bi in beats}
    stop = blist[0]
    while stop in rig['parent']:
        stop = rig['parent'][stop]
    ys = []
    for _G in Gmap.values():
        for i in blist:
            ys.append(_G[i][1][3])
    y0, sc = min(ys), 1.65/(max(ys)-min(ys))
    G0 = _pose_globals(rig, 0.0)
    inv = [_mat_inv4(G0[b]) for b in blist]
    ll = math.sqrt(0.5*0.5+1+0.25)
    tmp = os.path.join(out, 'tmp')
    os.makedirs(tmp, exist_ok=True)
    static = {'W': SW, 'H': SH, 'cam': CAM, 'look': LOOK,
              'L': (0.5/ll, 1.0/ll, -0.5/ll), 'norm': (sc, y0),
              'verts': mesh['verts'], 'infl': mesh['infl'], 'tris': tris,
              'nbones': len(blist), 'out': os.path.join(tmp, 'f%04d.png')}
    jobs, flats, idx_of = [], [], {}
    for b in range(NBIN):
        for j, bi in enumerate(beats):
            G = Gmap[bi]
            rx, rz = G[stop][0][3], G[stop][2][3]
            SHF = [[1, 0, 0, -rx], [0, 1, 0, 0], [0, 0, 1, -rz], [0, 0, 0, 1]]
            f = []
            for i, bo in enumerate(blist):
                Gb, Ib = _mmul(SHF, G[bo]), inv[i]
                M = [[sum(Gb[r][k]*Ib[k][c] for k in range(4)) for c in range(4)]
                     for r in range(4)]
                f += [M[r][c] for r in range(4) for c in range(4)]
            idx = b*NPH+j
            idx_of[idx] = (b, j)
            flats.append([(f, 0.0, 0.0, b*2*math.pi/NBIN)])
            jobs.append(idx)
    jobs.append(NBIN*NPH)
    flats.append([])
    with Pool(8, initializer=_winit, initargs=(static,)) as pool:
        pool.map(_wframe, list(zip(jobs, flats)))
    print(f'rendered {len(jobs)} frames')
    ew, eh, empty = read_png(os.path.join(tmp, f'f{NBIN*NPH:04d}.png'))
    meta = {'nbin': NBIN, 'nph': NPH, 'sprites': []}
    for idx, (b, j) in idx_of.items():
        w, h, rows = read_png(os.path.join(tmp, f'f{idx:04d}.png'))
        diff = [(x, y) for y in range(h) for x in range(w)
                if rows[y][x*3:x*3+3] != empty[y][x*3:x*3+3]]
        if not diff:
            continue
        x0 = max(0, min(x for x, y in diff)-1)
        x1 = min(w-1, max(x for x, y in diff)+1)
        y0 = max(0, min(y for x, y in diff)-1)
        y1 = min(h-1, max(y for x, y in diff)+1)
        cw, ch = x1-x0+1, y1-y0+1
        diffset = set(diff)
        rgb_rows, msk_rows = [], []
        for y in range(y0, y1+1):
            rgb, msk = bytearray(), bytearray()
            for x in range(x0, x1+1):
                rgb += rows[y][x*3:x*3+3]
                v = 255 if (x, y) in diffset else 0
                msk += bytes((v, v, v))
            rgb_rows.append(b'\x00'+bytes(rgb))
            msk_rows.append(b'\x00'+bytes(msk))
        fn = f'm_{b}_{j}'
        write_png(os.path.join(out, fn+'.png'), cw, ch, b''.join(rgb_rows))
        write_png(os.path.join(out, fn+'.m.png'), cw, ch, b''.join(msk_rows))
        meta['sprites'].append({'bin': b, 'ph': j, 'file': fn+'.png',
                                'w': cw, 'h': ch, 'ax': (x0+x1)//2-x0, 'ay': y1-y0})
    import json as _j
    _j.dump(meta, open(os.path.join(out, 'meta.json'), 'w'))
    print(f'baked {len(meta["sprites"])} sprites -> {out}')


if __name__ == '__main__':
    main()
