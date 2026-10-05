#!/usr/bin/env python3
"""fbx_rig: probe + bake a binary FBX character rig to JusAnim JSON markers.

Usage: python3 fbx_rig.py --probe file.fbx
       python3 fbx_rig.py file.fbx [out.json]
Stdlib only (struct, zlib). Handles FBX 7.x binary node graphs.
"""
import struct, sys, zlib, json, math, os

FBX_TIME = 46186158000


def read_node(d, pos, wide):
    if wide:
        e, n, pl = struct.unpack_from('<QQQ', d, pos)
        pos += 24
    else:
        e, n, pl = struct.unpack_from('<III', d, pos)
        pos += 12
    nl = d[pos]
    pos += 1
    if e == 0 and n == 0 and pl == 0 and nl == 0:
        return None, pos
    name = d[pos:pos + nl].decode('ascii', 'replace')
    pos += nl
    props = []
    for _ in range(n):
        t = chr(d[pos])
        pos += 1
        if t == 'Y':
            v = struct.unpack_from('<h', d, pos)[0]; pos += 2
        elif t == 'C':
            v = bool(d[pos]); pos += 1
        elif t == 'I':
            v = struct.unpack_from('<i', d, pos)[0]; pos += 4
        elif t == 'F':
            v = struct.unpack_from('<f', d, pos)[0]; pos += 4
        elif t == 'D':
            v = struct.unpack_from('<d', d, pos)[0]; pos += 8
        elif t == 'L':
            v = struct.unpack_from('<q', d, pos)[0]; pos += 8
        elif t in 'SR':
            ln = struct.unpack_from('<I', d, pos)[0]; pos += 4
            v = d[pos:pos + ln]; pos += ln
            if t == 'S':
                v = v.split(b'\x00\x01')[0].decode('utf-8', 'replace')
        else:  # array types f d l i b C
            alen, enc, clen = struct.unpack_from('<III', d, pos); pos += 12
            raw = d[pos:pos + clen]; pos += clen
            if enc == 1:
                raw = zlib.decompress(raw)
            props.append((t, alen, raw))
            continue
        props.append((t, v))
    kids = []
    if e > pos:
        while pos < e:
            nd, pos = read_node(d, pos, wide)
            if nd is None:
                break
            kids.append(nd)
    return {'name': name, 'props': props, 'kids': kids}, pos


def load(path):
    d = open(path, 'rb').read()
    assert d[:20] == b'Kaydara FBX Binary  ', d[:24]
    ver = struct.unpack_from('<I', d, 23)[0]
    wide = ver >= 7500
    pos, top = 27, []
    while pos < len(d) - 24:
        nd, pos = read_node(d, pos, wide)
        if nd is None:
            break
        top.append(nd)
    return ver, top


def find(top, name):
    return next((k for k in top if k['name'] == name), None)


def dec(prop):
    t, alen, raw = prop
    fmt = {'f': 'f', 'd': 'd', 'l': 'q', 'i': 'i', 'b': '?'}[t]
    return list(struct.unpack(f'<{alen}{fmt}', raw[:alen * struct.calcsize(fmt)]))


def probe(path):
    ver, top = load(path)
    print(f'FBX version {ver}')
    gs = find(top, 'GlobalSettings')
    for k in gs['kids'] if gs else []:
        if k['name'] == 'Properties70':
            for p in k['kids']:
                if p['name'].startswith('P:'):
                    nm = p['props'][0][1] if isinstance(p['props'][0], tuple) else p['props'][0]
                    vals = [v[1] if isinstance(v, tuple) and len(v) == 2 else v
                            for v in p['props'][1:]]
                    if nm in ('UpAxis', 'UpAxisSign', 'FrontAxis', 'FrontAxisSign',
                              'CoordAxis', 'CoordAxisSign', 'UnitScaleFactor',
                              'OriginalUpAxis', 'TimeMode'):
                        print(f'  global {nm} = {vals}')
    objs = find(top, 'Objects')
    by_type = {}
    models = []
    for k in objs['kids']:
        if k['name'] == 'Model' and len(k['props']) >= 3:
            _id, nm, tp = k['props'][0][1], k['props'][1], k['props'][2]
            models.append((_id, nm, tp[1] if isinstance(tp, tuple) else tp))
            by_type[tp[1] if isinstance(tp, tuple) else tp] = \
                by_type.get(tp[1] if isinstance(tp, tuple) else tp, 0) + 1
        else:
            by_type[k['name']] = by_type.get(k['name'], 0) + 1
    print('object kinds:', by_type)
    conns = find(top, 'Connections')
    parent, links = {}, []
    for c in conns['kids']:
        p = c['props']
        typ = p[0][1] if isinstance(p[0], tuple) else p[0]
        src, dst = p[1][1], p[2][1]
        extra = p[3][1] if len(p) > 3 else None
        links.append((typ, src, dst, extra))
        if typ == 'OO':
            parent[src] = dst
    mid = {m[0]: m for m in models}
    roots = [m for m in models if m[0] not in parent or parent[m[0]] not in mid]
    print(f'models={len(models)} roots={[r[1] for r in roots]}')
    kids_of = {}
    for m in models:
        if m[0] in parent and parent[m[0]] in mid:
            kids_of.setdefault(parent[m[0]], []).append(m[0])

    def show(i, depth):
        m = mid[i]
        print(f"  {' '*depth}{m[1]} [{m[2]}]")
        for k in kids_of.get(i, []):
            show(k, depth + 1)

    for r in roots:
        show(r[0], 0)
    # animation overview
    stacks = [(k['props'][1], k['props'][0][1]) for k in objs['kids']
              if k['name'] == 'AnimationStack']
    print('stacks:', [s[0] for s in stacks])
    tmin, tmax, ncurves, nkeys = None, None, 0, 0
    for k in objs['kids']:
        if k['name'] == 'AnimationCurve':
            ncurves += 1
            for sub in k['kids']:
                if sub['name'] == 'KeyTime' and sub['props']:
                    ts = dec(sub['props'][0])
                    nkeys += len(ts)
                    tmin = min([tmin or ts[0]] + ts)
                    tmax = max([tmax or ts[0]] + ts)
    print(f'curves={ncurves} keys={nkeys} range='
          f'{tmin/FBX_TIME if tmin else 0:.2f}s..{tmax/FBX_TIME if tmax else 0:.2f}s')
    ops = [(s, dd, e) for t, s, dd, e in links if t == 'OP'][:8]
    print('sample OP links:', ops)




def _mmul(A, B):
    return [[sum(A[r][k]*B[k][c] for k in range(4)) for c in range(4)] for r in range(4)]

def _euler_xyz(rx, ry, rz):
    import math as _m
    ax, ay, az = map(_m.radians, (rx, ry, rz))
    cx, sx, cy, sy, cz, sz = _m.cos(ax), _m.sin(ax), _m.cos(ay), _m.sin(ay), _m.cos(az), _m.sin(az)
    Rx = [[1,0,0],[0,cx,-sx],[0,sx,cx]]
    Ry = [[cy,0,sy],[0,1,0],[-sy,0,cy]]
    Rz = [[cz,-sz,0],[sz,cz,0],[0,0,1]]
    def m3(A, B):
        return [[sum(A[r][k]*B[k][c] for k in range(3)) for c in range(3)] for r in range(3)]
    R = m3(m3(Rz, Ry), Rx)  # Max XYZ: apply X first; verified vs Rz*Ry*Rx on Manuel
    return R

def bake_pose(path, out):
    import math as _m
    ver, top = load(path)
    objs = find(top, 'Objects')
    models, parent = {}, {}
    for k in objs['kids']:
        if k['name'] != 'Model' or len(k['props']) < 3:
            continue
        i = k['props'][0][1]
        nm = k['props'][1][1] if isinstance(k['props'][1], tuple) else k['props'][1]
        tp = k['props'][2][1] if isinstance(k['props'][2], tuple) else k['props'][2]
        tr, ro = [0, 0, 0], [0, 0, 0]
        for s in k['kids']:
            if s['name'] == 'Properties70':
                for p in s['kids']:
                    pn = p['props'][0][1]
                    if pn == 'Lcl Translation':
                        tr = [v[1] for v in p['props'][4:7]]
                    elif pn == 'Lcl Rotation':
                        ro = [v[1] for v in p['props'][4:7]]
        models[i] = {'name': nm, 'type': tp, 't': tr, 'r': ro}
    mids = set(models)
    for n in find(top, 'Connections')['kids']:
        p = n['props']
        if p[0][1] == 'OO' and p[1][1] in mids and p[2][1] in mids:
            parent[p[1][1]] = p[2][1]
    kids = {}
    for s, d in parent.items():
        kids.setdefault(d, []).append(s)
    roots = [i for i in models if i not in parent]
    G = {}

    def fk(i, M):
        m = models[i]
        R = _euler_xyz(*m['r'])
        L = [[R[0][0], R[0][1], R[0][2], m['t'][0]],
             [R[1][0], R[1][1], R[1][2], m['t'][1]],
             [R[2][0], R[2][1], R[2][2], m['t'][2]],
             [0, 0, 0, 1]]
        G[i] = _mmul(M, L)
        for c in kids.get(i, []):
            fk(c, G[i])

    I = [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
    for r in roots:
        fk(r, I)
    bones = {i: (G[i][0][3], G[i][1][3], G[i][2][3]) for i in G
             if models[i]['type'] == 'LimbNode'}
    print(f'bones={len(bones)}')
    # face along toes, then yaw facing to -Z (toward camera)
    def by(nm):
        return next(v for i, v in bones.items() if models[i]['name'].endswith(nm))
    try:
        fx = (by('foot_l')[0]-by('ball_l')[0]) + (by('foot_r')[0]-by('ball_r')[0])
        fz = (by('foot_l')[2]-by('ball_l')[2]) + (by('foot_r')[2]-by('ball_r')[2])
    except StopIteration:
        fx, fz = 0, 1
    a = _m.atan2(fx, fz) - _m.pi
    ca, sa = _m.cos(a), _m.sin(a)
    pts = {}
    for i, (x, y, z) in bones.items():
        pts[i] = (x*ca+z*sa, y, -x*sa+z*ca)
    ys = [p[1] for p in pts.values()]
    s = 1.65/(max(ys)-min(ys))
    y0 = min(ys)
    pts = {i: ((x)*s, (y-y0)*s+0.02, (z)*s) for i, (x, y, z) in pts.items()}
    from fetch_rig import color_of, radius_of
    names = {i: models[i]['name'].split('dancing_')[-1] for i in pts}
    objs_out = [{'id': names[i], 'shape': 'sphere',
                 'pos': [round(v, 4) for v in pts[i]],
                 'r': radius_of(names[i]), 'color': color_of(names[i])} for i in pts]
    beats = []
    for j, deg in enumerate((-60, -30, 0, 30, 60)):
        r = deg*_m.pi/180
        b = {'camera': [round(3.4*_m.sin(r), 3), 1.3, round(-3.4*_m.cos(r), 3)],
             'objects': objs_out}
        if j == 0:
            b['caption'] = 'Manuel. 98 real bones, one static pose.'
        if j == 4:
            b['caption'] = 'The dance lives in the full FBX, not this copy.'
        beats.append(b)
    import json as _j
    _j.dump({'settings': {'FPS': 10, 'BEAT_FRAMES': 12}, 'beats': beats}, open(out, 'w'))
    print(f'wrote {out}')


PRUNE = ('eye', 'eyelid', 'eyebrow', 'mouth', 'jaw', 'thumb', 'index',
         'middle', 'ring', 'pinky', 'finger', 'twist', 'toe')

def _dec_pair(k):
    kt = kv = None
    for sub in k['kids']:
        if sub['name'] == 'KeyTime' and sub['props']:
            kt = dec(sub['props'][0])
        elif sub['name'] == 'KeyValueFloat' and sub['props']:
            kv = dec(sub['props'][0])
    return kt, kv

def _eval(kt, kv, t):
    import bisect as _b
    if t <= kt[0]:
        return kv[0]
    if t >= kt[-1]:
        return kv[-1]
    j = _b.bisect_right(kt, t) - 1
    f = (t - kt[j]) / (kt[j+1] - kt[j])
    return kv[j] + (kv[j+1] - kv[j]) * f

def _load_rig(path):
    """models, hierarchy, animated channels. Shared by dance + mesh bakers."""
    ver, top = load(path)
    objs = find(top, 'Objects')
    models, parent = {}, {}
    for k in objs['kids']:
        if k['name'] != 'Model' or len(k['props']) < 3:
            continue
        i = k['props'][0][1]
        nm = k['props'][1][1] if isinstance(k['props'][1], tuple) else k['props'][1]
        tp = k['props'][2][1] if isinstance(k['props'][2], tuple) else k['props'][2]
        tr, ro, sc = [0, 0, 0], [0, 0, 0], [1, 1, 1]
        for s in k['kids']:
            if s['name'] == 'Properties70':
                for p in s['kids']:
                    pn = p['props'][0][1]
                    if pn == 'Lcl Translation':
                        tr = [v[1] for v in p['props'][4:7]]
                    elif pn == 'Lcl Rotation':
                        ro = [v[1] for v in p['props'][4:7]]
                    elif pn == 'Lcl Scaling':
                        sc = [v[1] for v in p['props'][4:7]]
        models[i] = {'name': nm, 'type': tp, 't': tr, 'r': ro, 's': sc}
    mids = set(models)
    info = {}
    for k in objs['kids']:
        p = k['props']
        if p:
            nm = p[1][1] if len(p) > 1 and isinstance(p[1], tuple) else ''
            info[p[0][1]] = (k['name'], nm if isinstance(nm, str) else nm, k)
    links = []
    for n in find(top, 'Connections')['kids']:
        p = n['props']
        links.append((p[0][1], p[1][1], p[2][1], p[3][1] if len(p) > 3 else ''))
    for t, s, d, e in links:
        if t == 'OO' and s in mids and d in mids:
            parent[s] = d
    kids = {}
    for s, d in parent.items():
        kids.setdefault(d, []).append(s)
    c2n = {s: (d, e) for t, s, d, e in links
           if t == 'OP' and info.get(s, (None,))[0] == 'AnimationCurve'}
    n2m = {s: (d, e) for t, s, d, e in links
           if t == 'OP' and info.get(s, (None,))[0] == 'AnimationCurveNode'}
    chans = {}
    tmax = 0
    for cid, (cn, ch) in c2n.items():
        if cn not in n2m:
            continue
        m, prop = n2m[cn]
        if m not in mids or not ch.startswith('d|'):
            continue
        kt, kv = _dec_pair(info[cid][2])
        if not kt or not kv:
            continue
        chans[(m, prop, 'XYZ'.index(ch[2]))] = (kt, kv)
        tmax = max(tmax, kt[-1])
    bchan = {}
    for (mm, prop, ax), (kt, kv) in chans.items():
        bchan.setdefault(mm, []).append((prop, ax, kt, kv))
    return {'models': models, 'parent': parent, 'kids': kids,
            'order': [i for i in models if i not in parent],
            'bchan': bchan, 'tmax': tmax / FBX_TIME, 'nchans': len(chans)}


def _euler_from_R(R):
    """inverse of _euler_xyz (R = Rz Ry Rx). Returns degrees."""
    import math as _m
    sy = max(-1.0, min(1.0, -R[2][0]))
    y = _m.degrees(_m.asin(sy))
    if abs(R[2][0]) < 0.9999:
        x = _m.degrees(_m.atan2(R[2][1], R[2][2]))
        z = _m.degrees(_m.atan2(R[1][0], R[0][0]))
    else:
        x = _m.degrees(_m.atan2(-R[1][2], R[1][1]))
        z = 0.0
    return (x, y, z)

def _axis_angle(ax, ay, az, deg):
    import math as _m
    a = _m.radians(deg)
    l = _m.sqrt(ax*ax+ay*ay+az*az) or 1.0
    ax, ay, az = ax/l, ay/l, az/l
    c, s = _m.cos(a), _m.sin(a)
    return [[c+ax*ax*(1-c), ax*ay*(1-c)-az*s, ax*az*(1-c)+ay*s],
            [ay*ax*(1-c)+az*s, c+ay*ay*(1-c), ay*az*(1-c)-ax*s],
            [az*ax*(1-c)-ay*s, az*ay*(1-c)+ax*s, c+az*az*(1-c)]]

def _m3mul(A, B):
    return [[sum(A[r][k]*B[k][c] for k in range(3)) for c in range(3)]
            for r in range(3)]

def _fk(rig, loc):
    models, kids, order = rig['models'], rig['kids'], rig['order']
    G = {}

    def fk(i, M):
        T, R, S = loc[i]
        Re = _euler_xyz(*R)
        L = [[Re[0][0]*S[0], Re[0][1]*S[1], Re[0][2]*S[2], T[0]],
             [Re[1][0]*S[0], Re[1][1]*S[1], Re[1][2]*S[2], T[1]],
             [Re[2][0]*S[0], Re[2][1]*S[1], Re[2][2]*S[2], T[2]],
             [0, 0, 0, 1]]
        G[i] = _mmul(M, L)
        for c in kids.get(i, []):
            fk(c, G[i])

    I = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    for r in order:
        fk(r, I)
    return G

def _pose_custom(rig, drot=None, dpos=None):
    """procedural pose: drot {bone: [(axis3_local, deg), ...]} applied as
    R_new = R_base @ delta; dpos {bone: [dx,dy,dz]} added to Lcl T."""
    models = rig['models']
    loc = {}
    for i, m in models.items():
        R = _euler_xyz(*m['r'])
        if drot and i in drot:
            for ax, deg in drot[i]:
                R = _m3mul(R, _axis_angle(*ax, deg))
            R = _euler_from_R(R)
        else:
            R = list(m['r'])
        T = list(m['t'])
        if dpos and i in dpos:
            T = [a+b for a, b in zip(T, dpos[i])]
        loc[i] = (T, R, list(m['s']))
    return _fk(rig, loc)

def _pose_globals(rig, t):
    """bone id -> world 4x4 at time t (FBX units)."""
    t *= FBX_TIME
    models, kids, order = rig['models'], rig['kids'], rig['order']
    loc = {}
    for i, m in models.items():
        T, R, S = list(m['t']), list(m['r']), list(m['s'])
        for prop, ax, kt, kv in rig['bchan'].get(i, ()):
            v = _eval(kt, kv, t)
            if prop == 'Lcl Translation':
                T[ax] = v
            elif prop == 'Lcl Rotation':
                R[ax] = v
            elif prop == 'Lcl Scaling':
                S[ax] = v
        loc[i] = (T, R, S)
    return _fk(rig, loc)

def bake_dance(path, prefix, chunk=90, fps=10):
    import math as _m, json as _j, bisect as _b
    rig = _load_rig(path)
    models, parent, kids = rig['models'], rig['parent'], rig['kids']
    n = int(rig['tmax'] * fps)
    print(f"dance: {rig['nchans']} channels, {rig['tmax']:.1f}s -> {n} beats")
    order = rig['order']
    keep = [i for i in models
            if models[i]['type'] == 'LimbNode'
            and not any(q in models[i]['name'].lower() for q in PRUNE)]
    print(f'markers: {len(keep)}/{sum(1 for i in models if models[i]["type"]=="LimbNode")}')
    seq = []
    for b in range(n):
        t = (b / fps) * FBX_TIME
        G = _pose_globals(rig, b / fps)
        # walk-in-place: zero topmost ancestor XZ
        top = next(i for i in keep)
        while top in parent:
            top = parent[top]
        rx, rz = G[top][0][3], G[top][2][3]
        seq.append({i: (G[i][0][3]-rx, G[i][1][3], G[i][2][3]-rz) for i in keep})
    # face first-frame toe dir to -Z, normalize scale globally
    f0 = seq[0]
    def nm_end(e):
        return next(v for i, v in f0.items() if models[i]['name'].endswith(e))
    try:
        dx = (nm_end('foot_l')[0]-nm_end('ball_l')[0]) + (nm_end('foot_r')[0]-nm_end('ball_r')[0])
        dz = (nm_end('foot_l')[2]-nm_end('ball_l')[2]) + (nm_end('foot_r')[2]-nm_end('ball_r')[2])
        a = _m.atan2(dx, dz) - _m.pi
    except StopIteration:
        a = 0
    ca, sa = _m.cos(a), _m.sin(a)
    glo_min = min(p[1] for j in seq for p in j.values())
    glo_max = max(p[1] for j in seq for p in j.values())
    s = 1.65/(glo_max-glo_min)
    from fetch_rig import color_of, radius_of
    beats = []
    for j in seq:
        objs_out = []
        for i, (x, y, z) in j.items():
            X, Z = x*ca+z*sa, -x*sa+z*ca
            nm = models[i]['name'].split('dancing_')[-1]
            objs_out.append({'id': nm, 'shape': 'sphere',
                             'pos': [round(X*s, 4), round((y-glo_min)*s+0.02, 4), round(Z*s, 4)],
                             'r': radius_of(nm), 'color': color_of(nm)})
        beats.append({'objects': objs_out})
    beats[0]['caption'] = 'Manuel dances. 44 seconds, straight from the FBX.'
    beats[len(beats)//2]['caption'] = 'Every joint baked from Take 001.'
    beats[-1]['caption'] = 'Rendered as markers on the checkered stage.'
    for c in range(0, len(beats), chunk):
        fn = f'{prefix}_p{c//chunk+1}.json'
        _j.dump({'settings': {'FPS': fps, 'BEAT_FRAMES': 1,
                           'camera': [0, 1.2, -4.2], 'look': [0, 0.85, 0]},
                'beats': beats[c:c+chunk]},
                open(fn, 'w'))
        print(f'wrote {fn} ({min(chunk, len(beats)-c)} beats)')


_W = {}

def _mat_inv4(M):
    n = 4
    a = [r[:] + [1 if i == j else 0 for j in range(n)] for i, r in enumerate(M)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(a[r][c]))
        a[c], a[p] = a[p], a[c]
        d = a[c][c] or 1e-12
        a[c] = [v/d for v in a[c]]
        for r in range(n):
            if r != c and a[r][c]:
                f = a[r][c]
                a[r] = [x - f*y for x, y in zip(a[r], a[c])]
    return [r[n:] for r in a]

def _load_mesh(path):
    """verts, triangulated faces, per-vert bone influences. Binds are derived
    from our own FK at t=0 (the dance starts at bind), not the file's stale
    Z-up bind matrices."""
    ver, top = load(path)
    objs = find(top, 'Objects')
    info = {}
    for k in objs['kids']:
        p = k['props']
        if p:
            nm = p[1][1] if len(p) > 1 and isinstance(p[1], tuple) else ''
            info[p[0][1]] = (k['name'], nm if isinstance(nm, str) else nm, k)
    links = []
    for n in find(top, 'Connections')['kids']:
        p = n['props']
        links.append((p[0][1], p[1][1], p[2][1], p[3][1] if len(p) > 3 else ''))
    skin = next(i for i, v in info.items() if v[0] == 'Deformer'
                and any(s['name'] == 'SkinningType' for s in v[2]['kids']))
    geo = next(d for t, s, d, e in links
               if t == 'OO' and s == skin and info.get(d, (None,))[0] == 'Geometry')
    verts = poly = None
    for s in info[geo][2]['kids']:
        if s['name'] == 'Vertices' and s['props']:
            verts = dec(s['props'][0])
        elif s['name'] == 'PolygonVertexIndex' and s['props']:
            poly = dec(s['props'][0])
    tris, cur = [], []
    for v in poly:
        if v < 0:
            cur.append(~v)
            for j in range(1, len(cur)-1):
                tris.append((cur[0], cur[j], cur[j+1]))
            cur = []
        else:
            cur.append(v)
    clids = [s for t, s, d, e in links
             if t == 'OO' and d == skin and info.get(s, (None,))[0] == 'Deformer']
    bones = []
    infl = {}
    for c in clids:
        sub = {s['name']: s for s in info[c][2]['kids']}
        idx, w = dec(sub['Indexes']['props'][0]), dec(sub['Weights']['props'][0])
        b = next((d if info.get(d, (None,))[0] == 'Model' else s)
                 for t, s, d, e in links
                 if t == 'OO' and (s == c or d == c)
                 and info.get(s if d == c else d, (None,))[0] == 'Model')
        if b not in bones:
            bones.append(b)
        for vi, wi in zip(idx, w):
            if wi:
                infl.setdefault(vi, []).append((bones.index(b), wi))
    V = []
    for j in range(0, len(verts), 3):
        V.append((verts[j], verts[j+1], verts[j+2]))
    return {'verts': V, 'tris': tris, 'infl': infl, 'bones': bones}


_WM = {}

def _winit(static):
    _WM.update(static)
    import math as _m
    _WM['sqrt'] = _m.sqrt

def _wframe(arg):
    idx, dancers = arg
    import struct as _st, zlib as _z
    sqrt = _WM['sqrt']
    W_, H_, CAM, LOOK = _WM['W'], _WM['H'], _WM['cam'], _WM['look']
    lx, ly, lz = _WM['L']
    sx, sy, sz = LOOK[0]-CAM[0], LOOK[1]-CAM[1], LOOK[2]-CAM[2]
    ll = sqrt(sx*sx+sy*sy+sz*sz)
    fwd = (sx/ll, sy/ll, sz/ll)
    rx, rz = fwd[2], -fwd[0]
    rl = sqrt(rx*rx+rz*rz) or 1.0
    right = (rx/rl, 0, rz/rl)
    up = (fwd[1]*right[2]-fwd[2]*right[1], fwd[2]*right[0]-fwd[0]*right[2],
          fwd[0]*right[1]-fwd[1]*right[0])
    nb = _WM['nbones']
    sc, y0 = _WM['norm']
    verts, infl, tris = _WM['verts'], _WM['infl'], _WM['tris']
    SPs = []
    for flat, dx, dz, ang in dancers:
        import math as _mm2
        ca, sa = _mm2.cos(ang), _mm2.sin(ang)
        S = [flat[i*16:(i+1)*16] for i in range(nb)]
        SP = []
        for vi, v in enumerate(verts):
            iv = infl.get(vi)
            if iv:
                x = y = z = 0.0
                for bb, w in iv:
                    M = S[bb]
                    x += w*(M[0]*v[0]+M[1]*v[1]+M[2]*v[2]+M[3])
                    y += w*(M[4]*v[0]+M[5]*v[1]+M[6]*v[2]+M[7])
                    z += w*(M[8]*v[0]+M[9]*v[1]+M[10]*v[2]+M[11])
            else:
                x, y, z = v
            X = x*ca+z*sa
            Z = -x*sa+z*ca
            p = (X*sc+dx, (y-y0)*sc+0.02, Z*sc+dz)
            vx, vy, vz = p[0]-CAM[0], p[1]-CAM[1], p[2]-CAM[2]
            zd = vx*fwd[0]+vy*fwd[1]+vz*fwd[2]
            if zd < 0.2:
                SP.append(None)
                continue
            SP.append(((vx*right[0]+vy*right[1]+vz*right[2])/zd,
                       (vx*up[0]+vy*up[1]+vz*up[2])/zd, zd, p))
        SPs.append(SP)
    zb = [-1.0]*(W_*H_)
    img = bytearray(W_*H_*3)
    for SP in SPs:
        for a, bb, c, col in tris:
            A, B, C = SP[a], SP[bb], SP[c]
            if A is None or B is None or C is None:
                continue
            ax = (A[0]/0.8+1)*W_/2
            ay = (1-A[1]/0.5)*H_/2
            bx = (B[0]/0.8+1)*W_/2
            by = (1-B[1]/0.5)*H_/2
            cx = (C[0]/0.8+1)*W_/2
            cy = (1-C[1]/0.5)*H_/2
            area = (bx-ax)*(cy-ay)-(cx-ax)*(by-ay)
            if area == 0:
                continue
            sgn = 1.0 if area > 0 else -1.0
            pa, pb, pc = A[3], B[3], C[3]
            ux, uy, uz = pb[0]-pa[0], pb[1]-pa[1], pb[2]-pa[2]
            vx, vy, vz = pc[0]-pa[0], pc[1]-pa[1], pc[2]-pa[2]
            nx, ny, nz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
            nl = sqrt(nx*nx+ny*ny+nz*nz) or 1.0
            df = 0.18+0.82*max(0, (nx*lx+ny*ly+nz*lz)/nl)
            r = min(255, int(col[0]*df))
            g = min(255, int(col[1]*df))
            bl = min(255, int(col[2]*df))
            x0 = max(0, int(min(ax, bx, cx)))
            x1 = min(W_-1, int(max(ax, bx, cx)))
            y0 = max(0, int(min(ay, by, cy)))
            y1 = min(H_-1, int(max(ay, by, cy)))
            e0x, e0y = bx-ax, by-ay
            e1x, e1y = cx-bx, cy-by
            e2x, e2y = ax-cx, ay-cy
            zaz, zbz, zcz = 1.0/A[2], 1.0/B[2], 1.0/C[2]
            inv = -1.0/area
            for y in range(y0, y1+1):
                w0 = (x0-ax)*e0y-(y-ay)*e0x
                w1 = (x0-bx)*e1y-(y-by)*e1x
                w2 = (x0-cx)*e2y-(y-cy)*e2x
                for x in range(x0, x1+1):
                    if (w0*sgn <= 0 and w1*sgn <= 0 and w2*sgn <= 0):
                        l0 = w1*inv
                        l1 = w2*inv
                        iz = (1-l0-l1)*zaz+l0*zbz+l1*zcz
                        o = y*W_+x
                        if iz > zb[o]:
                            zb[o] = iz
                            q = o*3
                            img[q], img[q+1], img[q+2] = r, g, bl
                    w0 += e0y
                    w1 += e1y
                    w2 += e2y
    for py in range(H_):
        v = (1-py/H_*2)*0.5
        for px in range(W_):
            o = py*W_+px
            if zb[o] >= 0:
                continue
            u = (px/W_*2-1)*0.8
            dx = fwd[0]+u*right[0]+v*up[0]
            dy = fwd[1]+u*right[1]+v*up[1]
            dz = fwd[2]+u*right[2]+v*up[2]
            dl = sqrt(dx*dx+dy*dy+dz*dz)
            dx, dy, dz = dx/dl, dy/dl, dz/dl
            if dy < -1e-6:
                t = -CAM[1]/dy
                hx, hz = CAM[0]+t*dx, CAM[2]+t*dz
                col = (30, 30, 34) if (int(hx)+int(hz)) % 2 == 0 else (215, 215, 220)
                dd = max(0, ly)
                r = min(255, int(col[0]*(0.18+0.82*dd)))
                g = min(255, int(col[1]*(0.18+0.82*dd)))
                bl = min(255, int(col[2]*(0.18+0.82*dd)))
            else:
                s = max(0, dy)
                r, g, bl = int(135+90*s), int(170+60*s), 220
            q = o*3
            img[q], img[q+1], img[q+2] = r, g, bl
    rows = []
    for y in range(H_):
        rows.append(b'\x00'+bytes(img[y*W_*3:(y+1)*W_*3]))
    raw = b''.join(rows)

    def chunk(tag, data):
        c = _st.pack('>I', len(data))+tag+data
        return c+_st.pack('>I', _z.crc32(tag+data) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', _st.pack('>IIBBBBB', W_, H_, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', _z.compress(raw, 6)) + chunk(b'IEND', b''))
    open(_WM['out'] % idx, 'wb').write(png)
    return idx

def bake_mesh(path, out_mp4, fps=10, jobs=16, test=None, cast=None,
              cam=None, look=None, captexts=None, poses=None, tracks=None,
              center=True):
    import math as _m, tempfile as _tf, subprocess as _sp, os as _os
    from multiprocessing import Pool
    from fetch_rig import color_of as _cc
    W_, H_, FPS = 320, 200, fps
    CAM, LOOK = cam or (0, 1.2, -4.2), look or (0, 0.85, 0)
    cast = cast or [(0.0, 0.0, 0)]
    rig = _load_rig(path)
    models = rig['models']
    mesh = _load_mesh(path)
    print(f"mesh: {len(mesh['verts'])} verts, {len(mesh['tris'])} tris, "
          f"{len(mesh['bones'])} bones")
    blist = mesh['bones']
    bnames = [models[b]['name'].split('dancing_')[-1] for b in blist]
    # dominant bone per tri -> part color (matches marker movies)
    dom = {}
    for vi, lst in mesh['infl'].items():
        dom[vi] = max(lst, key=lambda t: t[1])[0]
    tris = []
    for a, b, c in mesh['tris']:
        votes = [dom.get(a, 0), dom.get(b, 0), dom.get(c, 0)]
        col = _cc(bnames[max(set(votes), key=votes.count)])
        tris.append((a, b, c, tuple(col)))
    n = len(poses) if poses is not None else int(rig['tmax'] * fps)
    beats = list(range(n)) if test is None else list(test)
    if poses is None:
        need = sorted({(bi+dt) % n for bi in beats for _, _, dt in cast})
        Gmap = {t: _pose_globals(rig, t / fps) for t in need}
    else:
        Gmap = {bi: poses[j] for j, bi in enumerate(beats)}
    stop = blist[0]
    while stop in rig['parent']:
        stop = rig['parent'][stop]
    # normalize from bone positions (same framing as dance markers)
    _G0beat = Gmap[beats[0]]
    if poses is not None:
        _G0beat = _G0beat[0]
    f0 = {i: (_G0beat[i][0][3], _G0beat[i][1][3],
               _G0beat[i][2][3]) for i in blist}
    def end(e):
        return next(v for i, v in f0.items()
                    if models[i]['name'].endswith(e))
    try:
        dx = (end('foot_l')[0]-end('ball_l')[0]) + (end('foot_r')[0]-end('ball_r')[0])
        dz = (end('foot_l')[2]-end('ball_l')[2]) + (end('foot_r')[2]-end('ball_r')[2])
        ang = _m.atan2(dx, dz) - _m.pi
    except StopIteration:
        ang = 0
    ca, sa = _m.cos(ang), _m.sin(ang)
    ys = []
    for _Gv in Gmap.values():
        _Gs = [_Gv] if poses is None else _Gv
        for _G in _Gs:
            for i in blist:
                ys.append(_G[i][1][3])
    y0, sc = min(ys), 1.65/(max(ys)-min(ys))
    G0 = _pose_globals(rig, 0.0)
    inv = [_mat_inv4(G0[b]) for b in blist]
    flats = []
    for j, bi in enumerate(beats):
        fd = []
        for d, (dx0, dz0, dt) in enumerate(cast):
            if tracks is not None:
                dx, dz, yaw = tracks[d][j]
            else:
                dx, dz, yaw = dx0, dz0, 0.0
            if poses is not None:
                G = Gmap[bi][d]
            else:
                G = Gmap.get((bi+dt) % n, Gmap[bi])
            if center:
                rx, rz = G[stop][0][3], G[stop][2][3]
                SH = [[1, 0, 0, -rx], [0, 1, 0, 0], [0, 0, 1, -rz], [0, 0, 0, 1]]
            else:
                SH = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
            f = []
            for i, b in enumerate(blist):
                Gb, Ib = _mmul(SH, G[b]), inv[i]
                M = [[sum(Gb[r][k]*Ib[k][c] for k in range(4)) for c in range(4)]
                     for r in range(4)]
                f += [M[r][c] for r in range(4) for c in range(4)]
            fd.append((f, dx, dz, ang+yaw))
        flats.append(fd)
    import math as _mm
    ll = _mm.sqrt(0.5*0.5+1+0.25)
    static = {'W': W_, 'H': H_, 'cam': CAM, 'look': LOOK,
              'L': (0.5/ll, 1.0/ll, -0.5/ll), 'norm': (sc, y0),
              'verts': mesh['verts'], 'infl': mesh['infl'], 'tris': tris,
              'nbones': len(blist), 'out': _os.path.join(_tf.mkdtemp(), 'f%04d.png')}
    _OUT[0] = static['out']
    with Pool(jobs, initializer=_winit, initargs=(static,)) as pool:
        got = pool.map(_wframe, [(beats[i], flats[i]) for i in range(len(beats))])
    print(f'rendered {len(got)} frames')
    tmp = _os.path.dirname(static['out'])
    if test is not None:
        print('test frames in', tmp)
        return
    import storyvid as _sv
    _sv.BEAT_FRAMES = 1
    captext = captexts or {beats[0]: 'Manuel, in the mesh. Full dance, real skin.',
               beats[len(beats)//2]: 'Take 001, skinned live per frame.',
               beats[-1]: 'The checkered stage holds.'}
    caps = []
    for j, bi in enumerate(beats):
        if bi in captext:
            caps += _sv.caption_filters(captext[bi], j)
    cmd = ['ffmpeg', '-y', '-framerate', str(FPS), '-i',
           _os.path.join(tmp, 'f%04d.png')]
    if caps:
        flt = _os.path.join(tmp, 'caps.txt')
        open(flt, 'w').write(','.join(caps))
        cmd += ['-filter_script:v', flt]
    _sp.run(cmd + ['-pix_fmt', 'yuv420p', out_mp4], check=True)
    print('wrote', out_mp4)

_OUT = [None]

if __name__ == '__main__':
    if sys.argv[1] == '--probe':
        probe(sys.argv[2])
    elif sys.argv[1] == '--mesh':
        import json as _jj
        _args = sys.argv[2:]
        _t = [int(x) for x in _args[2].split(',')] if len(_args) > 2 else None
        bake_mesh(_args[0], _args[1] if len(_args) > 1 else 'manuel_mesh.mp4', test=_t)
    elif sys.argv[1] == '--chorus':
        _args = sys.argv[2:]
        _t = [int(x) for x in _args[2].split(',')] if len(_args) > 2 else None
        bake_mesh(_args[0], _args[1] if len(_args) > 1 else 'manuel_chorus.mp4',
                  test=_t, cast=[(-1.7, 0.0, 0), (0.0, 0.0, -30), (1.7, 0.0, -60)],
                  cam=(0, 1.3, -5.8), look=(0, 0.85, 0),
                  captexts={0: 'Manuel, Manuel, and Manuel.',
                            223: 'A canon in three parts, three seconds apart.',
                            445: 'The stage holds all three.'})
    elif sys.argv[1] == '--dance':
        bake_dance(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'manuel_dance')
    else:
        bake_pose(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'manuel_statue.json')
