#!/usr/bin/env python3
"""fight: procedural triple-threat duel driving the Manuel mesh.

No mocap here: every pose is choreographed in code (advance, punch, kick,
block, hit, fall, victory) via local-axis Aim on the real skeleton, skinned
by the same pipeline as the dance. Usage: python3 fight.py [out.mp4]
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fbx_rig import (_load_rig, _pose_globals, _pose_custom, _euler_xyz,
                     _m3mul, _axis_angle, bake_mesh)

FBX = '/tmp/opencode/rp_manuel_animated_001_dancing.fbx'
N = 340
FPS = 10


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u*u*(3-2*u)


def pulse(u):
    u = max(0.0, min(1.0, u))
    return math.sin(math.pi*u)


class Rig:
    def __init__(self, path):
        self.rig = _load_rig(path)
        models = self.rig['models']
        self.models = models
        short = {}
        for i, m in models.items():
            n = m['name']
            short[n.split('dancing_')[-1]] = i
        self.id = short
        hip = short['hip']
        root = hip
        while root in self.rig['parent']:
            root = self.rig['parent'][root]
        self.root = root
        G0 = _pose_globals(self.rig, 0.0)
        self.R0 = {i: [[G0[i][r][c] for c in range(3)] for r in range(3)]
                   for i in models}

    def off(self, bone, child):
        o = self.models[child]['t']
        l = math.sqrt(sum(v*v for v in o)) or 1.0
        return [v/l for v in o]

    def to_local(self, bone, w):
        R = self.R0[bone]
        return [R[0][0]*w[0]+R[1][0]*w[1]+R[2][0]*w[2],
                R[0][1]*w[0]+R[1][1]*w[1]+R[2][1]*w[2],
                R[0][2]*w[0]+R[1][2]*w[1]+R[2][2]*w[2]]

    def swing(self, bone, child, target, amt, cap=165.0):
        """rotate limb from rest toward world target by amt (1 = point at it)."""
        rest = self.off(bone, child)
        tl = self.to_local(bone, target)
        l = math.sqrt(sum(v*v for v in tl)) or 1.0
        tl = [v/l for v in tl]
        cx = rest[1]*tl[2]-rest[2]*tl[1]
        cy = rest[2]*tl[0]-rest[0]*tl[2]
        cz = rest[0]*tl[1]-rest[1]*tl[0]
        dot = max(-1.0, min(1.0, sum(a*b for a, b in zip(rest, tl))))
        full = math.degrees(math.acos(dot))
        if full < 1.0:
            return None
        return ((cx, cy, cz), amt*min(full, cap))

    def about_world(self, bone, waxis, deg):
        return (self.to_local(bone, waxis), deg)


def facing_yaw(frm, to):
    dx, dz = to[0]-frm[0], to[1]-frm[1]
    return math.atan2(-dx, -dz)


def lerp_waypoints(wps, j):
    """wps: [(beat, x, z, yaw), ...] -> (x, z, yaw) with smooth interp."""
    if j <= wps[0][0]:
        return wps[0][1:]
    for k in range(len(wps)-1):
        if j <= wps[k+1][0]:
            b0, x0, z0, y0 = wps[k]
            b1, x1, z1, y1 = wps[k+1]
            u = smooth((j-b0)/max(1, b1-b0))
            dy = (y1-y0+math.pi) % (2*math.pi)-math.pi
            return (x0+(x1-x0)*u, z0+(z1-z0)*u, y0+dy*u)
    return wps[-1][1:]


def build(beats=None):
    R = Rig(FBX)
    I = R.id
    UP = (0.0, 1.0, 0.0)

    A, B, C = 0, 1, 2
    spots = {A: (-110, 40), B: (110, 40), C: (0, -100)}
    starts = {A: (-190, 70), B: (190, 70), C: (0, -190)}

    # ---- root waypoints (beat, x, z, face-target) ----
    Tales = {
        A: [(0, *starts[A], (0, 0)), (50, *spots[A], (0, 0)),
            (58, -10, 32, (100, 40)), (106, -10, 32, (100, 40)),
            (118, -70, 10, (-40, -50)), (150, -70, 10, (-40, -50)),
            (182, -10, -30, (-75, -68)), (202, -60, -10, (20, -25)),
            (222, -60, -10, (20, -25)), (240, -70, -25, (0, -70)),
            (280, -50, -10, (50, -10)), (292, -50, -10, (50, -10)),
            (300, -50, -10, (45, -10)), (310, -45, -5, (45, -10)),
            (322, -45, -5, (-45, -1000)), (339, -45, -5, (-45, -1000))],
        B: [(0, *starts[B], (0, 0)), (50, *spots[B], (0, 0)),
            (70, 100, 38, (-10, 32)), (92, 140, 45, (-10, 32)),
            (106, 140, 45, (-40, -50)), (120, 90, -30, (-40, -50)),
            (150, 40, -45, (-40, -50)), (166, 45, -50, (-40, -50)),
            (178, 45, -50, (-10, -30)), (200, 20, -25, (-60, -10)),
            (212, 40, -30, (-60, -10)), (222, 40, -30, (-30, -60)),
            (242, 80, -35, (0, -70)), (256, 80, -35, (0, -70)),
            (280, 50, -10, (-50, -10)), (292, 50, -10, (-50, -10)),
            (300, 45, -10, (-45, -5)), (322, 90, -20, (-45, -5)),
            (339, 90, -25, (-45, -5))],
        C: [(0, *starts[C], (0, 0)), (50, *spots[C], (0, 0)),
            (70, 20, -80, (-10, 32)), (90, 20, -80, (-10, 32)),
            (118, -40, -50, (-70, 10)), (150, -40, -50, (40, -45)),
            (164, -80, -70, (40, -45)), (178, -80, -70, (-10, -30)),
            (192, -60, -60, (-10, -30)), (202, -40, -55, (20, -25)),
            (220, -30, -60, (40, -30)), (230, -30, -60, (40, -30)),
            (240, 0, -70, (-60, -30)), (266, 0, -70, (-60, -30)),
            (339, 10, -75, (-60, -30))],
    }
    # convert face-targets to yaw
    W = {}
    for d, wps in Tales.items():
        conv = []
        for b, x, z, tgt in wps:
            conv.append((b, x, z, facing_yaw((x, z), tgt)))
        W[d] = conv

    # ---- strike / reaction moves ----
    # (dancer, kind, t0, t1, side, env)
    moves = [
        (A, 'punch', 62, 74, 'L', 'pulse'), (B, 'hit', 68, 82, None, 'pulse'),
        (A, 'punch', 84, 96, 'R', 'pulse'), (B, 'hit', 92, 106, None, 'pulse'),
        (C, 'kick', 126, 140, 'R', 'pulse'), (A, 'hit', 136, 150, None, 'pulse'),
        (B, 'kick', 152, 166, 'L', 'pulse'), (C, 'hit', 162, 178, None, 'pulse'),
        (A, 'punch', 182, 192, 'L', 'pulse'), (C, 'hit', 190, 202, None, 'pulse'),
        (B, 'punch', 202, 212, 'R', 'pulse'), (A, 'hit', 210, 222, None, 'pulse'),
        (C, 'kick', 220, 232, 'L', 'pulse'), (B, 'hit', 230, 242, None, 'pulse'),
        (A, 'punch', 240, 250, 'R', 'pulse'), (C, 'block', 240, 254, None, 'latch'),
        (B, 'kick', 256, 268, 'R', 'pulse'), (C, 'hit', 264, 280, None, 'pulse'),
        (C, 'fall', 266, 339, None, 'latch'),
        (B, 'punch', 300, 310, 'L', 'pulse'), (A, 'block', 300, 310, None, 'latch'),
        (A, 'kick', 314, 326, 'R', 'pulse'), (B, 'hit', 322, 334, None, 'pulse'),
        (B, 'fall', 320, 339, None, 'latch'),
        (A, 'victory', 322, 339, None, 'latch'),
    ]

    # bounce ranges (standing only)
    bounce = {A: [(0, 292), (292, 339)], B: [(0, 320)], C: [(0, 266)]}

    poses, tracks = [], [[], [], []]
    DOWN = {A: None, B: None, C: None}
    beats = range(N) if beats is None else beats

    for j in beats:
        Gper = []
        for d in (A, B, C):
            x, z, yaw = lerp_waypoints(W[d], j)
            drot, dpos = {}, {}
            F = (-math.sin(yaw), 0.0, -math.cos(yaw))
            SIDE = (F[2], 0.0, -F[0])

            def add(bone, mod):
                drot.setdefault(bone, []).append(mod)

            # idle bounce
            if any(a <= j <= b for a, b in bounce[d]):
                dpos.setdefault(R.root, [0, 0, 0])[1] += \
                    3.0*(0.5-0.5*math.cos(2*math.pi*j/6))

            for md, kind, t0, t1, side, env in moves:
                if md != d or not (t0 <= j <= t1):
                    continue
                u = (j-t0)/max(1, t1-t0)
                e = pulse(u) if env == 'pulse' else smooth(u)
                if kind == 'punch':
                    sh = I[f'shoulder_{side.lower()}']
                    ua = I[f'upperarm_{side.lower()}']
                    m = R.swing(sh, ua, F, e)
                    if m:
                        add(sh, m)
                    sp = I['spine_02']
                    add(sp, (R.to_local(sp, SIDE), 12*e))
                elif kind == 'kick':
                    ul = I[f'upperleg_{side.lower()}']
                    ll = I[f'lowerleg_{side.lower()}']
                    tgt = (F[0]*0.7, 0.7, F[2]*0.7)
                    m = R.swing(ul, ll, tgt, e)
                    if m:
                        add(ul, m)
                    sp = I['spine_01']
                    add(sp, (R.to_local(sp, (-F[0], 0, -F[2])), 10*e))
                elif kind == 'block':
                    for s in ('l', 'r'):
                        sh = I[f'shoulder_{s}']
                        sgn = 1 if s == 'l' else -1
                        tgt = (F[0]*0.4+UP[0]*0.8+SIDE[0]*0.3*sgn,
                               0.8, F[2]*0.4+SIDE[2]*0.3*sgn)
                        m = R.swing(sh, I[f'upperarm_{s}'], tgt, e)
                        if m:
                            add(sh, m)
                    dpos.setdefault(R.root, [0, 0, 0])[1] -= 12*e
                elif kind == 'hit':
                    for s in ('spine_01', 'spine_02', 'spine_03'):
                        add(I[s], (R.to_local(I[s], (-F[0], 0, -F[2])), 8*e))
                    add(I['head'], (R.to_local(I['head'], (-F[0], 0, -F[2])), 14*e))
                    for s in ('l', 'r'):
                        sh = I[f'shoulder_{s}']
                        m = R.swing(sh, I[f'upperarm_{s}'],
                                    (-F[0]*0.5, 0.5, -F[2]*0.5), 0.5*e)
                        if m:
                            add(sh, m)
                    dpos.setdefault(R.root, [0, 0, 0])[0] += -F[0]*45*e
                    dpos.setdefault(R.root, [0, 0, 0])[2] += -F[2]*45*e
                elif kind == 'fall':
                    e = smooth((j-t0)/34.0)  # fixed 34-beat crumple, then hold
                    dpos.setdefault(R.root, [0, 0, 0])[1] -= 62*e
                    for s in ('spine_01', 'spine_02', 'spine_03'):
                        add(I[s], (R.to_local(I[s], (F[0], 0, F[2])), 18*e))
                    add(I['head'], (R.to_local(I['head'], (F[0], 0, F[2])), 25*e))
                    for s in ('l', 'r'):
                        ul = I[f'upperleg_{s}']
                        m = R.swing(ul, I[f'lowerleg_{s}'], (F[0], 0.25, F[2]),
                                    0.75*e)
                        if m:
                            add(ul, m)
                    DOWN[d] = DOWN[d] or j
                elif kind == 'victory':
                    for s in ('l', 'r'):
                        sh = I[f'shoulder_{s}']
                        m = R.swing(sh, I[f'upperarm_{s}'], UP, e)
                        if m:
                            add(sh, m)
                    hop = pulse(((j-322) % 9)/9) if j >= 322 else 0
                    dpos.setdefault(R.root, [0, 0, 0])[1] += 16*hop*e
                    add(I['head'], (R.to_local(I['head'], (0, -1, 0)), 8*e))

            # root placement from waypoints (cm; ROOT Lcl ~ origin)
            base = R.models[R.root]['t']
            dpos.setdefault(R.root, [0, 0, 0])[0] += x-base[0]
            dpos.setdefault(R.root, [0, 0, 0])[2] += z-base[2]
            Gper.append(_pose_custom(R.rig, drot, dpos))
            tracks[d].append((0.0, 0.0, yaw))
        poses.append(Gper)
    return R, poses, tracks


def main():
    from fbx_rig import bake_mesh
    import sys as _s
    out = _s.argv[1] if len(_s.argv) > 1 else 'manuel_fight.mp4'
    test = None
    if len(_s.argv) > 2:
        test = [int(v) for v in _s.argv[2].split(',')]
    R, poses, tracks = build(test)
    if test is not None:
        for j, bi in enumerate(test):
            hs = []
            for d in range(3):
                h = poses[j][d][R.id['hip']]
                hs.append([round(h[r][3], 1) for r in range(3)])
            print(f'beat {bi} hips A/B/C:', hs)
    bake_mesh(FBX, out, test=test,
              cast=[(0.0, 0.0, 0), (0.0, 0.0, 0), (0.0, 0.0, 0)],
              cam=(0, 1.25, -5.0), look=(0, 0.85, 0),
              captexts={0: 'Three Manuels walk in. One walks out.',
                        165: 'No mocap was used in this beating.',
                        N-1: 'Winner takes the checkered stage.'} if test is None else {},
              poses=poses, tracks=tracks, center=False)
    print('built', len(poses), 'beats')


if __name__ == '__main__':
    main()
