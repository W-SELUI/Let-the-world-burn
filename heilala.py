"""
heilala.py - Tonga's national flower, in ASCII.

Bits in a dark void grow a branch, glossy leaves unfold, clusters of round
red buds appear and open one by one into 4-petal heilala flowers. Their
fragrance drifts up in golden specks... then the flowers lift off the
branch and string themselves into a kahoa heilala that turns slowly, glowing.

Setup (once):   pip install pygame-ce numpy
Run:            python heilala.py

Keys:
    Space     grow it again
    F11 / F   fullscreen on/off
    Esc / Q   quit
"""

import math
import random

import numpy as np
import pygame

# ------------------------------------------------------------------ settings --
HANDLE = "@w_selui"
FONT_SIZE = 9
WINDOW = (1280, 760)
FPS = 30
N_FLOWERS = 22
N_KAHOA = 54              # flowers in the finished kahoa
GLOW = 1.0
SPIN = 0.22               # how fast the kahoa turns

TAU = 2 * math.pi
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
RAMP_CODES = np.array([ord(c) for c in RAMP], dtype=np.int32)

# timeline (seconds)
T_BRANCH0, T_BRANCH1 = 2.0, 5.0
T_LEAF0, T_LEAF1 = 3.4, 7.0
T_BUD0, T_BUD1 = 5.4, 7.2
T_OPEN0, T_OPEN1 = 7.4, 12.5
T_KAHOA0 = 17.0           # flowers lift off the branch
T_KAHOA1 = 22.5           # kahoa complete

PETAL, EDGE, CENTER, STAMEN, LEAF, BARK, BITS, GOLD, THREAD, STAR = range(10)
PALETTES = [(232, 70, 58), (255, 135, 105), (125, 15, 28), (255, 205, 90),
            (60, 160, 75), (130, 88, 60), (255, 170, 150), (255, 215, 120),
            (240, 225, 200), (255, 245, 235)]


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def colour(level, pal):
    b = level / 15
    r, g, bl = PALETTES[pal]
    k = b ** 0.85
    w = max(0.0, b - 0.86) * (1.3 if pal in (PETAL, EDGE, CENTER) else 3.0)
    return (int(min(255, r * k + (255 - r) * w)),
            int(min(255, g * k + (255 - g) * w)),
            int(min(255, bl * k + (255 - bl) * w)))


def basis(a):
    """Two vectors perpendicular to axis a (for orienting a flower or leaf)."""
    a = a / np.linalg.norm(a)
    h = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 0, 1.0])
    u = np.cross(a, h); u /= np.linalg.norm(u)
    v = np.cross(a, u)
    return u, a, v


def normals(P):
    du = np.gradient(P, axis=-3)
    dv = np.gradient(P, axis=-2)
    n = np.cross(du, dv)
    return n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9)


# -------------------------------------------------------------------- plant --
def tube_line(p0, p1, bow, n=120):
    t = np.linspace(0, 1, n)[:, None]
    mid = (p0 + p1) / 2 + bow
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * mid + t ** 2 * p1


class Plant:
    def __init__(self):
        main = tube_line(np.array([-3.4, -0.7, 0.2]), np.array([2.9, 0.35, -0.1]),
                         np.array([0.0, 0.55, 0.0]))
        i1, i2 = 50, 82
        tw1 = tube_line(main[i1], main[i1] + [0.9, 0.95, -0.2], np.array([-0.1, 0.1, 0]), 60)
        tw2 = tube_line(main[i2], main[i2] + [0.8, -0.8, -0.1], np.array([0.1, 0.0, 0]), 60)
        # (centre line, base radius, start delay as fraction of growth time)
        self.tubes = [(main, 0.075, 0.0), (tw1, 0.04, 0.42), (tw2, 0.04, 0.68)]

        # leaves along the branch, alternating sides
        self.leaves = []
        for (line, rad, delay) in self.tubes:
            for j, f in enumerate(np.linspace(0.12, 0.92, 5 if rad > 0.05 else 3)):
                k = int(f * (len(line) - 1))
                side = 1 if j % 2 == 0 else -1
                tang = line[min(k + 1, len(line) - 1)] - line[max(k - 1, 0)]
                tang /= np.linalg.norm(tang)
                out = np.cross(tang, [0, 0, 1.0]) * side
                d = out * 0.75 + tang * 0.45 + np.array([0, -0.15, -0.25 * side])
                self.leaves.append(dict(base=line[k], dir=d / np.linalg.norm(d),
                                        len=random.uniform(0.5, 0.7), at=delay + f * (1 - delay)))

        # flower clusters at nodes; each flower faces mostly towards us
        nodes = [(0, 0.3), (0, 0.48), (0, 0.62), (0, 0.8), (0, 0.95),
                 (1, 0.55), (1, 0.95), (2, 0.6), (2, 0.95)]
        self.flowers = []
        while len(self.flowers) < N_FLOWERS:
            for (ti, f) in nodes:
                if len(self.flowers) >= N_FLOWERS:
                    break
                line = self.tubes[ti][0]
                base = line[int(f * (len(line) - 1))] + np.random.normal(scale=0.12, size=3) * [1, 0.8, 0.5]
                ax = np.array([random.uniform(-0.5, 0.5), random.uniform(0.0, 0.6), -1.0])
                self.flowers.append(dict(pos=base, axis=ax / np.linalg.norm(ax),
                                         rot=random.uniform(0, TAU), size=random.uniform(0.9, 1.15),
                                         bud_t=random.uniform(T_BUD0, T_BUD1 - 0.4),
                                         open_t=0.0))
        order = np.argsort([fl["pos"][0] for fl in self.flowers])
        for rank, i in enumerate(order):            # open from left to right, a little random
            self.flowers[i]["open_t"] = T_OPEN0 + rank / N_FLOWERS * (T_OPEN1 - T_OPEN0 - 1.2) \
                + random.uniform(0, 0.6)
        # where each flower sits on the kahoa; the rest of the slots fill from bits
        self.slots = kahoa_slots()
        taken = set()
        for i, fl in enumerate(self.flowers):
            j = int(round(i * N_KAHOA / N_FLOWERS)) % N_KAHOA
            taken.add(j)
            sl = self.slots[j]
            fl.update(kpos=sl["pos"], kaxis=sl["axis"], kdelay=sl["t"] - 1.2, ka=sl["a"])
        self.extra = []
        for j, sl in enumerate(self.slots):
            if j in taken:
                continue
            self.extra.append(dict(pos=sl["pos"], axis=sl["axis"], a=sl["a"], t=sl["t"],
                                   rot=random.uniform(0, TAU), size=random.uniform(0.72, 0.88),
                                   bud=random.random() < 0.15))
        self.kleaves = [sl for j, sl in enumerate(self.slots) if j % 3 == 1]


# -------------------------------------------------------------------- kahoa --
K_R = 1.55


def cord(a):
    """Centre line of the kahoa: high at the back, hanging low at the front."""
    a = np.asarray(a, float)
    hang = ((1 - np.sin(a)) / 2) ** 1.6                   # 1 at the front, 0 at the back
    return np.stack([K_R * np.cos(a), 0.65 - 1.35 * hang, 0.8 * K_R * np.sin(a)], -1)


def kahoa_slots():
    slots = []
    for j in range(N_KAHOA):
        a = math.pi / 2 + TAU * j / N_KAHOA               # start at the back, go round
        c = cord(a)
        T = cord(a + 1e-3) - cord(a - 1e-3); T /= np.linalg.norm(T)
        out = np.array([math.cos(a), 0, math.sin(a)])
        n1 = out - T * np.dot(out, T); n1 /= np.linalg.norm(n1)
        n2 = np.cross(T, n1)
        psi = j * 2.4                                     # spiral round the cord
        d = math.cos(psi) * n1 + math.sin(psi) * n2
        ax = d + np.array([0, 0.2, -0.25]); ax /= np.linalg.norm(ax)
        slots.append(dict(a=a, c=c, T=T, d=d, pos=c + d * 0.09, axis=ax,
                          t=T_KAHOA0 + 0.4 + j / N_KAHOA * 3.4))
    return slots


# ---------------------------------------------------------------- geometry --
NS, NW = 10, 9
S = np.linspace(0, 1, NS)
Wv = np.linspace(-1, 1, NW)
SS, WW = np.meshgrid(S, Wv, indexing="ij")
FIB = np.array([[math.cos(i * 2.39996) * math.sqrt(1 - ((i + 0.5) / 60 * 2 - 1) ** 2),
                 (i + 0.5) / 60 * 2 - 1,
                 math.sin(i * 2.39996) * math.sqrt(1 - ((i + 0.5) / 60 * 2 - 1) ** 2)] for i in range(60)])


def flower_points(pos, axis, rot, size, openness, grow):
    """4 cupped petals (closed = round bud) + dark centre + golden stamens."""
    o = openness
    L = 0.27 * size * grow
    th0 = 0.12 + 0.5 * o
    curl = -0.95 * (1 - o) + 0.55 * o
    th = th0 + curl * SS ** 2
    ds = 1 / (NS - 1)
    rho = 0.02 * grow + np.cumsum(np.sin(th) * L * ds, axis=0) - np.sin(th[:1]) * L * ds
    h = np.cumsum(np.cos(th) * L * ds, axis=0) - np.cos(th[:1]) * L * ds
    wp = np.sqrt(np.sin(np.pi * np.clip(0.12 + 0.88 * SS, 0, 1)))
    u, a, v = basis(axis)
    Ps = []
    for k in range(4):
        phi = rot + k * TAU / 4 + WW * 0.95 * wp
        rr = np.maximum(0.003, rho + 0.012 * WW ** 2 * SS * o)
        local = np.stack([rr * np.cos(phi), h, rr * np.sin(phi)], -1)
        Ps.append(local)
    local = np.stack(Ps)                                    # (4, NS, NW, 3)
    world = pos + local[..., :1] * u + local[..., 1:2] * a + local[..., 2:] * v
    edge = (np.abs(WW) > 0.8) | (SS > 0.85)
    extras_P, extras_K = [], []
    if o > 0.35 and grow > 0.5:
        c = pos + a * (0.03 * size) + FIB * 0.05 * size        # pistil
        extras_P.append(c); extras_K.append(np.full(len(c), CENTER))
        for j in range(10):                                   # stamens
            ang = rot + j * TAU / 10
            p = pos + a * 0.07 * size * o + (u * math.cos(ang) + v * math.sin(ang)) * 0.085 * size
            extras_P.append(p[None]); extras_K.append(np.array([STAMEN]))
    return world, edge, extras_P, extras_K


def leaf_points(base, d, length, unf):
    u, a, v = basis(d)
    side = np.cross(d, [0, 1.0, 0])
    side = side / (np.linalg.norm(side) + 1e-9)
    up = np.cross(side, d)
    L = length * unf
    width = 0.2 * length * unf ** 1.4 * np.sin(np.pi * SS) ** 0.85
    along = SS * L
    droop = -0.25 * SS ** 2 * L
    fold = 0.05 * np.abs(WW) * unf
    P = base + along[..., None] * d + (WW * width)[..., None] * side + (droop + fold)[..., None] * up
    return P[None]


# ----------------------------------------------------------------- camera --
LIGHT = np.array([-0.35, 0.75, -0.55]); LIGHT /= np.linalg.norm(LIGHT)


def camera(t):
    k = float(smooth((t - T_KAHOA0) / (T_KAHOA1 - T_KAHOA0)))
    yaw = 0.22 * math.sin(t * 0.25) * (1 - k) + 0.55 * math.sin(max(0.0, t - T_KAHOA0) * SPIN * 1.4) * k
    tilt = -0.12 - 0.12 * k
    return yaw, tilt


def transform(P, t):
    yaw, tilt = camera(t)
    cy, sy = math.cos(yaw), math.sin(yaw)
    x = P[..., 0] * cy + P[..., 2] * sy
    z = -P[..., 0] * sy + P[..., 2] * cy
    ct, st = math.cos(tilt), math.sin(tilt)
    y = P[..., 1]
    y2, z2 = y * ct - z * st, y * st + z * ct
    k = float(smooth((t - T_KAHOA0) / (T_KAHOA1 - T_KAHOA0)))
    return np.stack([x, y2 - 0.45 * (1 - k) + 0.05 * k, z2 + 6.2 - 0.7 * k], -1)


def shade(P, N, base, gloss):
    V = -P / np.linalg.norm(P, axis=-1, keepdims=True)
    nv = np.sum(N * V, -1)
    N = N * np.sign(nv + 1e-9)[..., None]
    nv = np.abs(nv)
    diff = np.clip(np.sum(N * LIGHT, -1), 0, 1)
    R = 2 * nv[..., None] * N - V
    spec = np.clip(np.sum(R * LIGHT, -1), 0, 1) ** 24
    return np.clip(base * (0.15 + 0.62 * diff) + 0.28 * (1 - nv) ** 2 + gloss * spec, 0, 1)


# -------------------------------------------------------------------- scene --
class Scene:
    def __init__(self, cols, rows, aspect):
        self.cols, self.rows, self.aspect = cols, rows, aspect
        self.F = 0.92 * cols * 6.2 / 7.0
        self.plant = Plant()
        self.stars = []
        box = lambda n: np.random.uniform([-4, -2.2, -1.5], [4, 2.2, 1.5], (n, 3))
        # builders: bits that fly in to build the branch and the buds
        pts, t1 = [], []
        for (line, rad, delay) in self.plant.tubes:
            for _ in range(260):
                f = random.random()
                pts.append(line[int(f * (len(line) - 1))])
                t1.append(T_BRANCH0 + (delay + f * (1 - delay)) * (T_BRANCH1 - T_BRANCH0))
        for ex in self.plant.extra:
            for _ in range(14):
                pts.append(ex["pos"] + np.random.normal(scale=0.04, size=3))
                t1.append(ex["t"] + random.uniform(0, 0.3))
        for fl in self.plant.flowers:
            for _ in range(22):
                pts.append(fl["pos"] + np.random.normal(scale=0.04, size=3))
                t1.append(fl["bud_t"] + random.uniform(0, 0.3))
        n = len(pts)
        self.b_start = box(n)
        self.b_target = np.array(pts)
        self.b_t1 = np.array(t1)
        self.b_t0 = self.b_t1 - np.random.uniform(1.0, 2.0, n)
        self.b_char = np.where(np.random.random(n) < 0.5, ord("0"), ord("1"))
        self.d_pos = box(450)
        self.d_vel = np.random.normal(scale=0.004, size=(450, 3))
        self.d_char = np.array([ord(c) for c in np.random.choice(list("01.'"), 450)])
        self.c_pos = np.zeros((0, 3)); self.c_vel = np.zeros((0, 3))
        self.c_age = np.zeros(0); self.c_life = np.zeros(0); self.c_pal = np.zeros(0, int)
        self.c_char = np.zeros(0, int)

    def add_crumbs(self, P, pal, vel, spread, life, chars="01"):
        n = len(P)
        if not n:
            return
        self.c_pos = np.concatenate([self.c_pos, P])
        self.c_vel = np.concatenate([self.c_vel, np.random.normal(scale=spread, size=(n, 3)) + vel])
        self.c_age = np.concatenate([self.c_age, np.zeros(n)])
        self.c_life = np.concatenate([self.c_life, np.random.uniform(life * 0.6, life * 1.2, n)])
        self.c_pal = np.concatenate([self.c_pal, np.full(n, pal)])
        self.c_char = np.concatenate([self.c_char,
                                      np.array([ord(c) for c in np.random.choice(list(chars), n)])])

    def project(self, P):
        Z = P[..., 2]
        return (self.cols / 2 + P[..., 0] * self.F / Z,
                self.rows / 2 - P[..., 1] * self.F * self.aspect / Z)


def build_frame(sc, t):
    cols, rows = sc.cols, sc.rows
    pl = sc.plant
    gone = float(np.clip((t - (T_KAHOA0 + 0.8)) / 3.0, 0, 1))   # branch dissolving
    breeze = 0.03 * math.sin(t * 0.8)

    parts_P, parts_L, parts_K = [], [], []

    def add(Ploc, pal, base, gloss, edge=None, extra=None):
        Pw = transform(Ploc, t)
        Nw = normals(Pw)
        L = shade(Pw, Nw, base, gloss)
        K = np.full(L.shape, pal)
        if extra is not None:
            L = L * extra
        if edge is not None:
            e = np.broadcast_to(edge, L.shape)
            K = np.where(e, EDGE, K)
            L = np.where(e, np.minimum(1, L * 1.2 + 0.08), L)
        parts_P.append(Pw.reshape(-1, 3)); parts_L.append(L.ravel()); parts_K.append(K.ravel())

    # ---- branch (tubes grow from the trunk end)
    grow = float(np.clip((t - T_BRANCH0) / (T_BRANCH1 - T_BRANCH0), 0, 1))
    if grow > 0 and gone < 1:
        ring = np.linspace(0, TAU, 14, endpoint=False)
        for (line, rad, delay) in pl.tubes:
            g = np.clip((grow - delay) / (1 - delay), 0, 1)
            n = int(g * len(line) * (1 - gone))
            if n < 2:
                continue
            c = line[:n].copy()
            c[:, 1] += breeze * np.linspace(0, 1, n) ** 2
            tang = np.gradient(c, axis=0); tang /= np.linalg.norm(tang, axis=1, keepdims=True)
            side = np.cross(tang, [0, 0, 1.0]); side /= np.linalg.norm(side, axis=1, keepdims=True) + 1e-9
            up = np.cross(side, tang)
            r = rad * (1 - 0.45 * np.linspace(0, 1, n))[:, None, None]
            P = c[:, None, :] + r * (np.cos(ring)[None, :, None] * side[:, None, :] +
                                     np.sin(ring)[None, :, None] * up[:, None, :])
            bark = 0.85 + 0.15 * np.sin(np.arange(n)[:, None] * 0.9 + ring[None, :] * 3)   # rough bark
            add(P[None], BARK, 1.2, 0.1, extra=bark[None])

    # ---- leaves unfold along the branch
    if gone < 1:
        bl = []
        for lf in pl.leaves:
            st = T_LEAF0 + lf["at"] * (T_LEAF1 - T_LEAF0 - 1.2)
            unf = float(smooth((t - st) / 1.2)) * (1 - gone)
            if unf > 0.03:
                P = leaf_points(lf["base"], lf["dir"], lf["len"], unf)
                P[..., 1] += breeze
                bl.append(P)
        if bl:
            P = np.concatenate(bl)
            add(P, LEAF, 1.25, 0.45, extra=np.where(np.abs(WW) < 0.15, 0.6, 1.0)[None] * np.ones(P.shape[:3]))

    # ---- flowers: buds -> open -> lift into the kahoa
    open_count = 0
    petal_worlds, petal_mult = [], []
    raw_P, raw_K = [], []            # centres + stamens, transformed in one go
    wave = t * 1.1

    def shimmer(a):
        if t < T_KAHOA0:
            return 1.0
        d = (a - wave + math.pi) % TAU - math.pi
        return 1.0 + 0.45 * math.exp(-d * d / 0.12)

    for i, fl in enumerate(pl.flowers):
        g = float(smooth((t - fl["bud_t"]) / 0.5))
        if g <= 0:
            continue
        o = float(smooth((t - fl["open_t"]) / 1.1))
        open_count += o > 0.5
        e = float(smooth((t - fl["kdelay"]) / 1.6))
        pos = fl["pos"] * (1 - e) + fl["kpos"] * e + np.array([0, math.sin(math.pi * e) * 0.7 + breeze, 0])
        ax = fl["axis"] * (1 - e) + fl["kaxis"] * e
        world, edge, ex_P, ex_K = flower_points(pos, ax / np.linalg.norm(ax), fl["rot"] + e * 2,
                                                fl["size"] * (1 - 0.2 * e), o, g)
        petal_worlds.append(world); petal_mult += [shimmer(fl["ka"])] * 4
        for P, K in zip(ex_P, ex_K):
            raw_P.append(P); raw_K.append(K)
        # fragrance: golden specks drift up from open flowers
        if o > 0.8 and random.random() < 0.12:
            sc.add_crumbs(pos[None] + np.random.normal(scale=0.05, size=(1, 3)), GOLD,
                          np.array([0, 0.008, 0]), 0.003, 2.5, ".'*`")

    # extra kahoa flowers grow in place from bits
    for ex in pl.extra:
        g = float(smooth((t - ex["t"]) / 0.5))
        if g <= 0:
            continue
        o = float(smooth((t - ex["t"] - 0.3) / 0.9)) * (0.12 if ex["bud"] else 1.0)
        open_count += g > 0.5
        world, edge, ex_P, ex_K = flower_points(ex["pos"], ex["axis"], ex["rot"], ex["size"], o, g)
        petal_worlds.append(world); petal_mult += [shimmer(ex["a"])] * 4
        for P, K in zip(ex_P, ex_K):
            raw_P.append(P); raw_K.append(K)
        if o > 0.8 and random.random() < 0.05:
            sc.add_crumbs(ex["pos"][None], GOLD, np.array([0, 0.008, 0]), 0.003, 2.5, ".'*`")

    if raw_P:
        K = np.concatenate(raw_K)
        Pw = transform(np.concatenate(raw_P), t)
        parts_P.append(Pw); parts_K.append(K)
        parts_L.append(np.where(K == CENTER, 0.55, 0.95))

    if petal_worlds:
        allw = np.concatenate(petal_worlds)                 # (4 * flowers, NS, NW, 3)
        mult = np.array(petal_mult)[:, None, None] * np.ones(allw.shape[:3])
        add(allw, PETAL, 1.25, 0.35, edge=(np.abs(WW) > 0.8) | (SS > 0.85), extra=mult)

    # green leaves tucked between the flowers
    kl = []
    for j, sl in enumerate(pl.kleaves):
        unf = float(smooth((t - sl["t"] - 0.6) / 0.9))
        if unf > 0.03:
            side = 1 if j % 2 else -1
            dl = sl["T"] * side * 0.8 + sl["d"] * 0.6
            kl.append(leaf_points(sl["c"] + sl["d"] * 0.03, dl / np.linalg.norm(dl), 0.3, unf))
    if kl:
        P = np.concatenate(kl)
        add(P, LEAF, 1.2, 0.45, extra=np.where(np.abs(WW) < 0.15, 0.6, 1.0)[None] * np.ones(P.shape[:3]))

    # ---- the kahoa string appears as the flowers arrive
    if t > T_KAHOA0:
        done = float(np.clip((t - T_KAHOA0 - 0.3) / 3.6, 0, 1))
        a = math.pi / 2 + np.linspace(0, TAU * done, max(2, int(260 * done)))
        ring = np.linspace(0, TAU, 6, endpoint=False)
        c = cord(a)
        tn = np.gradient(c, axis=0); tn /= np.linalg.norm(tn, axis=1, keepdims=True) + 1e-9
        side = np.cross(tn, [0, 1.0, 0]); side /= np.linalg.norm(side, axis=1, keepdims=True) + 1e-9
        up = np.cross(side, tn)
        P = c[:, None, :] + 0.016 * (np.cos(ring)[None, :, None] * side[:, None, :] +
                                     np.sin(ring)[None, :, None] * up[:, None, :])
        add(P[None], THREAD, 1.0, 0.6)

    # branch & leaves crumble into bits
    if 0 < gone < 1:
        for (line, rad, delay) in pl.tubes:
            k = np.random.randint(0, len(line), 8)
            sc.add_crumbs(line[k], BARK, np.array([0, -0.006, 0]), 0.012, 1.3)
        for lf in random.sample(pl.leaves, 3):
            sc.add_crumbs(lf["base"][None] + lf["dir"] * random.random() * lf["len"], LEAF,
                          np.array([0, -0.006, 0]), 0.012, 1.3)

    # ---- splat into the letter grid (front-most surface wins, anti-aliased)
    n = cols * rows
    ch = np.zeros(n, np.int32); br = np.zeros(n, np.float32); pa = np.zeros(n, np.int8)
    zmin = np.full(n, np.inf)
    if parts_P:
        P = np.concatenate(parts_P); L = np.concatenate(parts_L); K = np.concatenate(parts_K)
        sx, sy = sc.project(P)
        ix, iy = sx.astype(int), sy.astype(int)
        ok = (ix >= 0) & (ix < cols) & (iy >= 0) & (iy < rows) & (P[:, 2] > 0.5)
        idx = (iy * cols + ix)[ok]; z = P[ok, 2]; L = L[ok]; K = K[ok]
        np.minimum.at(zmin, idx, z)
        front = z <= zmin[idx] + 0.03
        lsum = np.zeros(n); cnt = np.zeros(n)
        np.add.at(lsum, idx[front], L[front]); np.add.at(cnt, idx[front], 1)
        order = np.argsort(-z[front])
        pa[idx[front][order]] = K[front][order]
        has = cnt > 0
        lv = np.maximum(lsum[has] / cnt[has], 0.08)
        br[has] = lv
        ch[has] = RAMP_CODES[np.clip((lv * (len(RAMP) - 1)).astype(int), 1, len(RAMP) - 1)]

    # ---- bits
    def put_points(Ploc, b, chars, pals):
        if not len(Ploc):
            return
        Pw = transform(Ploc, t)
        x, y = sc.project(Pw)
        x, y = x.astype(int), y.astype(int)
        ok = (x >= 0) & (x < cols) & (y >= 0) & (y < rows) & (b > 0.03)
        j = y[ok] * cols + x[ok]
        front = Pw[ok, 2] < zmin[j]
        j = j[front]
        ch[j] = chars[ok][front]; br[j] = b[ok][front]; pa[j] = pals[ok][front]

    dust_fade = 1.0 if t < T_BUD1 + 1 else max(0.0, 1 - (t - T_BUD1 - 1) / 3)
    if dust_fade > 0:
        sc.d_pos += sc.d_vel
        put_points(sc.d_pos, np.full(len(sc.d_pos), 0.12 * dust_fade), sc.d_char,
                   np.full(len(sc.d_pos), BITS))
    s_ = np.clip((t - sc.b_t0) / (sc.b_t1 - sc.b_t0), 0, 1)
    live = t < sc.b_t1
    flying = int(((s_ > 0) & live).sum())
    if live.any():
        e = smooth(s_[live])[:, None]
        ang = s_[live][:, None] * 6
        swirl = np.concatenate([np.cos(ang), np.zeros_like(ang), np.sin(ang)], 1) * 0.4 * (1 - e) * e
        P = sc.b_start[live] + (sc.b_target[live] - sc.b_start[live]) * e + swirl
        b = np.where(s_[live] == 0, 0.14, 0.35 + 0.6 * e[:, 0])
        put_points(P, b, sc.b_char[live], np.full(len(P), BITS))
    if len(sc.c_pos):
        sc.c_pos += sc.c_vel
        sc.c_pos[:, 0] += 0.004 * np.sin(t * 2 + sc.c_pos[:, 1] * 3) * (sc.c_pal == GOLD)
        sc.c_age += 1 / FPS
        keep = sc.c_age < sc.c_life
        for name in ("c_pos", "c_vel", "c_age", "c_life", "c_pal", "c_char"):
            setattr(sc, name, getattr(sc, name)[keep])
        lifefrac = sc.c_age / sc.c_life
        b = np.where(sc.c_pal == GOLD, 0.75 * np.sin(np.pi * lifefrac), 0.6 * (1 - lifefrac))
        put_points(sc.c_pos, b, sc.c_char, sc.c_pal)

    # ---- sparkles on the finished kahoa
    if t > T_KAHOA1 and random.random() < 0.35:
        bright = np.nonzero(br > 0.9)[0]
        if len(bright):
            k = random.choice(bright.tolist())
            sc.stars.append([k % cols, k // cols, 0.0, random.uniform(0.4, 0.7)])
    kept = []
    for st in sc.stars:
        st[2] += 1 / FPS
        if st[2] < st[3]:
            k = math.sin(math.pi * st[2] / st[3])
            for dx, dy, c, f in [(0, 0, "*", 1.0), (-1, 0, "-", 0.6), (1, 0, "-", 0.6),
                                 (-2, 0, "-", 0.3), (2, 0, "-", 0.3), (0, -1, "|", 0.6), (0, 1, "|", 0.6)]:
                xx, yy = st[0] + dx, st[1] + dy
                if 0 <= xx < cols and 0 <= yy < rows:
                    j = yy * cols + xx
                    if k * f > br[j] * 0.8:
                        ch[j], br[j], pa[j] = ord(c), min(1.0, k * f + 0.1), STAR
            kept.append(st)
    sc.stars = kept

    phase = ("void" if t < T_BRANCH0 else "branch growing" if t < T_BUD0 else
             "buds" if t < T_OPEN0 else "blooming" if t < T_OPEN1 else
             "in bloom" if t < T_KAHOA0 else "stringing the kahoa" if t < T_KAHOA1 else
             "kahoa heilala")
    return ch.reshape(rows, cols), br.reshape(rows, cols), pa.reshape(rows, cols), open_count, phase


# ------------------------------------------------------------------- render --
class Renderer:
    def __init__(self):
        self.font = None
        for name in ("consolas", "cascadiamono", "dejavusansmono", "couriernew", "monospace"):
            path = pygame.font.match_font(name)
            if path:
                self.font = pygame.font.Font(path, FONT_SIZE)
                break
        if self.font is None:
            self.font = pygame.font.Font(None, FONT_SIZE + 4)
        self.cw, self.ch = self.font.size("M")
        hud_path = pygame.font.match_font("consolas") or pygame.font.match_font("dejavusansmono")
        self.hud = pygame.font.Font(hud_path, 14)
        self.cache = {}
        self.size = None

    def glyph(self, code, level, pal):
        key = (code, level, pal)
        g = self.cache.get(key)
        if g is None:
            g = self.font.render(chr(code), True, colour(level, pal))
            self.cache[key] = g
        return g

    def draw(self, screen, ch, br, pa, fade):
        if screen.get_size() != self.size:
            self.size = screen.get_size()
            self.layer = pygame.Surface(self.size)
            self.bright = pygame.Surface(self.size)
        w, h = self.size
        self.layer.fill((0, 0, 0))
        self.bright.fill((0, 0, 0))
        ys, xs = np.nonzero(ch)
        levels = np.clip((br[ys, xs] * fade * 15 + 0.5).astype(int), 0, 15)
        seq, hot = [], []
        cw, chh = self.cw, self.ch
        for c, l, x, y, p in zip(ch[ys, xs].tolist(), levels.tolist(), xs.tolist(),
                                 ys.tolist(), pa[ys, xs].tolist()):
            if l > 0:
                item = (self.glyph(c, l, p), (x * cw, y * chh))
                seq.append(item)
                if l >= 9:
                    hot.append(item)
        blit = (lambda s, q: s.fblits(q)) if hasattr(self.layer, "fblits") else \
               (lambda s, q: s.blits(q, doreturn=False))
        blit(self.layer, seq)
        blit(self.bright, hot)
        screen.fill((0, 0, 0))
        screen.blit(self.layer, (0, 0))
        if GLOW > 0:
            s1 = pygame.transform.smoothscale(self.bright, (max(1, w // 5), max(1, h // 5)))
            s2 = pygame.transform.smoothscale(s1, (max(1, w // 14), max(1, h // 14)))
            s1.blit(pygame.transform.smoothscale(s2, s1.get_size()), (0, 0),
                    special_flags=pygame.BLEND_ADD)
            blur = pygame.transform.smoothscale(s1, (w, h))
            for _ in range(max(1, int(GLOW))):
                screen.blit(blur, (0, 0), special_flags=pygame.BLEND_ADD)


def draw_hud(screen, ren, t, flowers, letters, phase, fps):
    w, h = screen.get_size()
    dim, pink = (110, 118, 128), (225, 110, 150)
    f = ren.hud
    lh = f.get_linesize()
    screen.blit(f.render(f"t {t:05.2f}s", True, pink), (w - 100, 8))
    for i, line in enumerate((f"{HANDLE} · 2026", f"heilala {flowers}",
                              f"letters {letters:,}", phase)):
        screen.blit(f.render(line, True, dim), (10, h - 26 - (4 - i) * lh))
    pygame.draw.line(screen, (30, 34, 40), (0, h - 22), (w, h - 22))
    screen.blit(f.render("py heilala.py", True, dim), (6, h - 19))
    txt = f.render(f"running · {fps:.0f} fps", True, dim)
    screen.blit(txt, (w - txt.get_width() - 8, h - 19))


def main():
    pygame.init()
    pygame.display.set_caption("heilala.py")
    screen = pygame.display.set_mode(WINDOW, pygame.RESIZABLE)
    clock = pygame.time.Clock()
    ren = Renderer()

    def new_scene():
        w, h = screen.get_size()
        return Scene(w // ren.cw, (h - 90) // ren.ch, ren.cw / ren.ch), pygame.time.get_ticks()

    sc, start = new_scene()
    full = False
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_q)):
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_F11, pygame.K_f):
                full = not full
                screen = pygame.display.set_mode((0, 0) if full else WINDOW,
                                                 pygame.FULLSCREEN if full else pygame.RESIZABLE)
                sc, start = new_scene()
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                sc, start = new_scene()
            elif e.type == pygame.VIDEORESIZE and not full:
                screen = pygame.display.set_mode(e.size, pygame.RESIZABLE)
                sc, start = new_scene()
        t = (pygame.time.get_ticks() - start) / 1000
        ch, br, pa, flowers, phase = build_frame(sc, t)
        ren.draw(screen, ch, br, pa, min(1.0, t / 0.8 + 0.2))
        draw_hud(screen, ren, t, flowers, int((ch != 0).sum()), phase, clock.get_fps())
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()