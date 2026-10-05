#!/usr/bin/env python3
"""fetch_rig: download a real mocap rig (CMU 07_01 walk, BVH) and bake it to JusAnim JSON.

Rig source: CMU Graphics Lab Motion Capture Database (http://mocap.cs.cmu.edu),
BVH conversion by Bruce Hahne, mirror https://github.com/konyshevgmbh/cmu-mocap
(CMU + converter both permit reuse; see mirror READMEFIRST.txt).
Subject 007 = walk, 317 frames @120fps. Baked slow-mo (every 4th frame @10fps).

Usage: python3 fetch_rig.py [out.json]
Each mocap frame becomes one beat (BEAT_FRAMES 1): joints as marker spheres.
Walk is zeroed in place (root XZ travel removed) so the rig stays on stage.
"""
import json, math, os, sys, urllib.request

URL = ('https://raw.githubusercontent.com/konyshevgmbh/cmu-mocap/'
       'master/data/007/07_01.bvh')
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'rig.bvh')
STRIDE, FPS = 4, 10


def parse_bvh(text):
    L = [l.strip() for l in text.replace('\r', '').split('\n') if l.strip()]
    order, i = [], [0]

    def node(name):
        assert L[i[0]] == '{', L[i[0]]
        i[0] += 1
        off = [float(x) for x in L[i[0]].split()[1:]]
        i[0] += 1
        ch = []
        if L[i[0]].startswith('CHANNELS'):
            ch = L[i[0]].split()[2:]
            i[0] += 1
            order.extend((name, c) for c in ch)
        kids = []
        while L[i[0]] != '}':
            p = L[i[0]].split()
            if p[0] in ('JOINT', 'ROOT'):
                i[0] += 1
                kids.append(node(p[1]))
            elif p[:2] == ['End', 'Site']:
                i[0] += 1
                kids.append(node(name + '-tip'))
            else:
                i[0] += 1
        i[0] += 1
        return {'name': name, 'offset': off, 'channels': ch, 'kids': kids}

    assert L[0] == 'HIERARCHY'
    p = L[1].split()
    assert p[0] == 'ROOT'
    i[0] = 2
    root = node(p[1])
    assert L[i[0]] == 'MOTION'
    n = int(L[i[0] + 1].split()[1])
    frames = [[float(x) for x in L[i[0] + 3 + k].split()] for k in range(n)]
    return root, order, frames


def mat_mul(A, B):
    return [[sum(A[r][k] * B[k][c] for k in range(3)) for c in range(3)]
            for r in range(3)]


def mat_vec(A, v):
    return [sum(A[r][k] * v[k] for k in range(3)) for r in range(3)]


def euler(vals, axes):
    # R = R_first @ R_rest (leftmost channel outermost); good enough for playback
    R = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    for v, ax in zip(vals, axes):
        a, c, s = math.radians(v), 0, 0
        c, s = math.cos(a), math.sin(a)
        M = {'X': [[1, 0, 0], [0, c, -s], [0, s, c]],
             'Y': [[c, 0, s], [0, 1, 0], [-s, 0, c]],
             'Z': [[c, -s, 0], [s, c, 0], [0, 0, 1]]}[ax]
        R = mat_mul(R, M)
    return R


def fk(n, vals, P, R, out):
    pv = vals.get(n['name'], {'pos': [0, 0, 0], 'rot': []})
    lp = [o + p for o, p in zip(n['offset'], pv['pos'])]
    Rg = mat_mul(R, euler([v for _, v in pv['rot']], [a for a, _ in pv['rot']]))
    Pg = [p + q for p, q in zip(P, mat_vec(R, lp))]
    out[n['name']] = Pg
    for k in n['kids']:
        fk(k, vals, Pg, Rg, out)


def color_of(name):
    n = name.lower()
    if 'head' in n or 'neck' in n or 'skull' in n:
        return [235, 200, 160]
    if n in ('hips', 'hip') or 'spine' in n or 'chest' in n or 'collar' in n \
            or n == 'ab' or 'pelvis' in n or 'waist' in n or 'clavicle' in n:
        return [220, 70, 70]
    if 'shoulder' in n or 'elbow' in n or 'wrist' in n or 'hand' in n \
            or 'arm' in n or 'finger' in n:
        return [245, 245, 245]
    return [70, 120, 230]


def radius_of(name):
    n = name.lower()
    if 'head' in n:
        return 0.13
    if 'tip' in n and ('toe' in n or 'finger' in n):
        return 0.05
    return 0.08


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'rig_walk.json')
    if not os.path.exists(CACHE):
        print('downloading rig...', URL)
        urllib.request.urlretrieve(URL, CACHE)
    root, order, frames = parse_bvh(open(CACHE).read())
    cols = {}
    for idx, (nm, c) in enumerate(order):
        cols.setdefault(nm, []).append((c, idx))
    print(f'rig: joints={len(cols)} frames={len(frames)}')

    seq = []
    for f in frames[::STRIDE]:
        vals = {}
        for nm, cl in cols.items():
            pos, rot = [0, 0, 0], []
            for c, idx in cl:
                if c.endswith('position'):
                    pos['XYZ'.index(c[0])] = f[idx]
                elif c.endswith('rotation'):
                    rot.append((c[0], f[idx]))
            vals[nm] = {'pos': pos, 'rot': rot}
        joints = {}
        fk(root, vals, [0, 0, 0], [[1, 0, 0], [0, 1, 0], [0, 0, 1]], joints)
        seq.append(joints)

    # face walk direction -> +X (profile to default camera), then walk in place
    rx = [j[root['name']][0] for j in seq]
    rz = [j[root['name']][2] for j in seq]
    a = math.atan2(rz[-1] - rz[0], rx[-1] - rx[0])
    ca, sa = math.cos(a), math.sin(a)
    for j in seq:
        rx0, rz0 = j[root['name']][0], j[root['name']][2]
        for nm, p in j.items():
            x, z = p[0] - rx0, p[2] - rz0
            p[0], p[2] = x * ca + z * sa, -x * sa + z * ca
        j[root['name']][0] = j[root['name']][2] = 0.0
    mn = min(p[1] for j in seq for p in j.values())
    mx = max(p[1] for j in seq for p in j.values())
    s = 1.65 / (mx - mn)
    for j in seq:
        for p in j.values():
            p[0] *= s
            p[1] = (p[1] - mn) * s + 0.02
            p[2] *= s

    names = list(seq[0].keys())
    beats = []
    caps = {0: 'A real motion-capture rig. CMU walk, slowed down.',
            len(seq) // 2: 'Every dot is a joint from the BVH file.',
            len(seq) - 1: 'Walk in place. Thanks, CMU.'}
    for i, j in enumerate(seq):
        objs = [{'id': nm, 'shape': 'sphere', 'pos': [round(v, 4) for v in j[nm]],
                 'r': radius_of(nm), 'color': color_of(nm)} for nm in names]
        b = {'objects': objs}
        if i in caps:
            b['caption'] = caps[i]
        beats.append(b)
    json.dump({'settings': {'FPS': FPS, 'BEAT_FRAMES': 1,
                           'camera': [0, 1.3, -3.4], 'look': [0, 0.9, 0]},
               'beats': beats}, open(out, 'w'))
    print(f'wrote {out} ({len(beats)} beats)')


if __name__ == '__main__':
    main()
