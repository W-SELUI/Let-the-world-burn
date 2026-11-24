"""
rose.py - in a dark void, bits gather into a stem, leaves unfurl, a bud
forms and a deep red rose blooms petal by petal, all drawn in ASCII.
It sways with dew drops sparkling, drops a petal now and then, and
finally sheds every petal into bits... and grows again.

Setup (once):   pip install pygame-ce numpy
Run:            python rose.py

Keys:
    Space     grow a new rose
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
N_PETALS = 34
GLOW = 1.0
SPIN = 0.12               # slow turn so you see it in 3D

TAU = 2 * math.pi
GOLDEN = 2.39996323
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
RAMP_CODES = np.array([ord(c) for c in RAMP], dtype=np.int32)

# timeline (seconds)
T_STEM0, T_STEM1 = 2.0, 4.6
T_LEAF0, T_LEAF1 = 3.6, 5.6
T_BUD0, T_BUD1 = 4.8, 6.4
T_BLOOM0, T_BLOOM1 = 6.4, 11.5
SOLO_FALLS = (17.0, 22.5, 27.0)         # single petals drifting down
T_SHED = 32.0                          # every petal falls
T_DISSOLVE = 36.0                      # stem + leaves turn to bits
T_RESTART = 40.0

# palettes
ROSE, EDGE, STEM, LEAF, BITS, DEW, SEPAL, STAR = range(8)
PALETTES = [(175, 8, 32), (255, 55, 80), (70, 170, 70), (80, 190, 80),
            (255, 165, 175), (215, 235, 255), (35, 105, 42), (255, 240, 245)]


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def colour(level, pal):
    b = level / 15
    r, g, bl = PALETTES[pal]
    k = b ** 0.85
    w = max(0.0, b - 0.86) * (1.2 if pal in (ROSE, EDGE) else 3.0)
    return (int(min(255, r * k + (255 - r) * w)),
            int(min(255, g * k + (255 - g) * w)),
            int(min(255, bl * k + (255 - bl) * w)))


# ----------------------------------------------------------------- geometry --
NS, NW = 30, 24
S = np.linspace(0, 1, NS)[None, :, None]
W = np.linspace(-1, 1, NW)[None, None, :]


def normals(P):
    du = np.gradient(P, axis=1)
    dv = np.gradient(P, axis=2)
    n = np.cross(du, dv)
    return n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9)


class Plant:
    def __init__(self):
        k = np.arange(N_PETALS)
        self.phi = k * GOLDEN + random.uniform(0, TAU)
        self.ell = (k / (N_PETALS - 1)) ** 0.9            # 0 = centre, 1 = outer
        self.jit = np.random.uniform(0.9, 1.1, N_PETALS)
        self.attached = np.ones(N_PETALS, bool)
        # stem: a gentle S-curve from the ground to the bloom
        v = np.linspace(0, 1, 140)
        self.stem_v = v
        self.stem_c = np.stack([0.09 * np.sin(v * math.pi * 1.3),
                                -2.9 + 2.9 * v,
                                0.05 * np.sin(v * math.pi)], 1)
        self.leaves = [(0.33, -1, 0.62), (0.58, 1, 0.5), (0.45, 1, 0.32)]   # (v, side, length)
        # dew drops sit on outer petals
        self.dew = [(random.randint(N_PETALS // 2, N_PETALS - 1), random.randint(10, 24),
                     random.randint(6, NW - 7), random.uniform(0, TAU)) for _ in range(14)]

    # ---- petals (all at once, numpy)
    def petals(self, bloom, grow):
        ell = self.ell[:, None, None]
        b = smooth((bloom - (1 - self.ell) * 0.55) / 0.45)[:, None, None]
        L = (0.3 + 0.62 * ell ** 0.7) * 1.4 * self.jit[:, None, None] * grow
        r0 = 0.03 + 0.11 * ell
        th0 = 0.05 + (0.12 + 0.8 * ell) * b
        curl = (0.15 + 0.85 * ell) * b - (1 - b) * 0.65        # closed bud: tips lean in
        th = th0 + curl * S ** 2.5
        ds = 1 / (NS - 1)
        rho = r0 + np.cumsum(np.sin(th) * L * ds, axis=1) - np.sin(th[:, :1]) * L * ds
        h = -0.14 * ell + np.cumsum(np.cos(th) * L * ds, axis=1) - np.cos(th[:, :1]) * L * ds
        wp = np.sqrt(S) * np.sqrt(np.clip(1 - S ** 6, 0, 1))
        alpha = 0.55 + 0.45 * ell
        phi = self.phi[:, None, None] + W * alpha * wp
        rho = np.maximum(0.004, rho + 0.06 * ell * b * W ** 4 * S)   # edges roll back
        h = h - 0.025 * W ** 2 * S * ell
        P = np.stack([rho * np.cos(phi) + 0 * W, h + 0 * W, rho * np.sin(phi) + 0 * W], -1)
        return P

    def sepals(self, grow):
        k = np.arange(5)
        phi = k * TAU / 5 + 0.3
        L = 0.38 * grow
        th = 2.0 + 0.5 * S ** 1.5 + 0 * phi[:, None, None]
        ds = 1 / (NS - 1)
        rho = 0.05 + np.cumsum(np.sin(th) * L * ds, axis=1)
        h = -0.06 + np.cumsum(np.cos(th) * L * ds, axis=1)
        wp = (1 - S) ** 0.8
        ph = phi[:, None, None] + W * 0.22 * wp
        return np.stack([rho * np.cos(ph), h + 0 * W, rho * np.sin(ph)], -1)

    def stem(self, grow):
        vis = self.stem_v <= grow
        c = self.stem_c[vis]
        if not len(c):
            return np.zeros((0, 3)), np.zeros((0, 3))
        a = np.linspace(0, TAU, 12, endpoint=False)
        r = 0.05 * (1 - 0.3 * self.stem_v[vis])
        n = np.stack([np.cos(a)[None, :].repeat(len(c), 0), np.zeros((len(c), 12)),
                      np.sin(a)[None, :].repeat(len(c), 0)], -1)
        P = c[:, None, :] + n * r[:, None, None]
        return P.reshape(-1, 3), n.reshape(-1, 3)

    def leaf(self, v, side, length, unfurl):
        i = int(v * (len(self.stem_v) - 1))
        base = self.stem_c[i]
        L = length * unfurl
        s, w = S[0], W[0]
        width = 0.17 * length * unfurl ** 1.5 * np.sin(np.pi * np.clip(s, 0, 1)) ** 0.8 \
            * (1 + 0.08 * np.sin(s * 45))                    # serrated edge
        x = side * (s * L)
        y = (0.35 * s - 0.55 * s ** 2) * L + 0.06 * np.abs(w) * unfurl   # droop + fold
        z = w * width
        P = np.stack([base[0] + x + 0 * w, base[1] + y + 0 * w, base[2] + z + 0 * s], -1)
        return P[None]


# ------------------------------------------------------------------ helpers --
def transform(P, t, sway):
    """Sway (bending more higher up), then turn and tilt for the camera."""
    P = P.copy()
    bend = (P[..., 1] + 2.9) ** 2 * 0.03
    P[..., 0] += sway * bend
    th = 0.4 + SPIN * t
    cy, sy = math.cos(th), math.sin(th)
    x, z = P[..., 0] * cy + P[..., 2] * sy, -P[..., 0] * sy + P[..., 2] * cy
    tilt = -0.5
    ct, st = math.cos(tilt), math.sin(tilt)
    y = P[..., 1] + 0.5
    y2, z2 = y * ct - z * st, y * st + z * ct
    return np.stack([x, y2, z2 + 5.3], -1)


LIGHT = np.array([-0.4, 0.75, -0.5]); LIGHT /= np.linalg.norm(LIGHT)


def shade(P, N, base, rim_k=0.35):
    V = -P / np.linalg.norm(P, axis=-1, keepdims=True)
    nv = np.sum(N * V, -1)
    N = N * np.sign(nv + 1e-9)[..., None]                # two-sided petals
    nv = np.abs(nv)
    diff = np.clip(np.sum(N * LIGHT, -1), 0, 1)
    R = 2 * nv[..., None] * N - V
    spec = np.clip(np.sum(R * LIGHT, -1), 0, 1) ** 30
    return np.clip(base * (0.12 + 0.6 * diff) + rim_k * (1 - nv) ** 2 + 0.25 * spec, 0, 1)


# -------------------------------------------------------------------- scene --
class Scene:
    def __init__(self, cols, rows, aspect):
        self.cols, self.rows, self.aspect = cols, rows, aspect
        self.F = 0.95 * rows * 5.3 / (4.2 * aspect)
        self.plant = Plant()
        self.stars = []
        self.falling = []          # detached petals: [P_local(NS,NW,3), t_detach, vel, spin]
        self.solo_done = 0
        self.shed_next = None
        box = lambda n: np.random.uniform([-3, -3, -2], [3, 2, 2], (n, 3))
        # builders: fly from the void to the stem / bud
        v = np.random.random(700)
        stem_t = self.plant.stem_c[(v * 139).astype(int)]
        d = np.random.normal(size=(900, 3)); d /= np.linalg.norm(d, axis=1, keepdims=True)
        bud_t = d * [0.16, 0.22, 0.16] * np.random.random((900, 1)) ** 0.5 + [0, 0.18, 0]
        t1 = np.concatenate([T_STEM0 + v * (T_STEM1 - T_STEM0), np.random.uniform(T_BUD0, T_BUD1, 900)])
        self.b_start = box(1600)
        self.b_target = np.concatenate([stem_t, bud_t])
        self.b_t1 = t1
        self.b_t0 = t1 - np.random.uniform(1.0, 2.0, 1600)
        self.b_char = np.where(np.random.random(1600) < 0.5, ord("0"), ord("1"))
        # void dust
        self.d_pos = box(500)
        self.d_vel = np.random.normal(scale=0.004, size=(500, 3))
        self.d_char = np.array([ord(c) for c in np.random.choice(list("01.'"), 500)])
        # crumbs (petals and stem turning into bits)
        self.c_pos = np.zeros((0, 3)); self.c_vel = np.zeros((0, 3))
        self.c_age = np.zeros(0); self.c_life = np.zeros(0); self.c_pal = np.zeros(0, int)

    def add_crumbs(self, P, pal, spread, life):
        n = len(P)
        self.c_pos = np.concatenate([self.c_pos, P])
        self.c_vel = np.concatenate([self.c_vel, np.random.normal(scale=spread, size=(n, 3)) + [0, -0.004, 0]])
        self.c_age = np.concatenate([self.c_age, np.zeros(n)])
        self.c_life = np.concatenate([self.c_life, np.random.uniform(life * 0.6, life * 1.2, n)])
        self.c_pal = np.concatenate([self.c_pal, np.full(n, pal)])

    def project(self, P):
        Z = P[..., 2]
        return (self.cols / 2 + P[..., 0] * self.F / Z,
                self.rows / 2 - P[..., 1] * self.F * self.aspect / Z)

    def detach(self, k, t, bloom, grow):
        P = self.plant.petals(bloom, grow)[k]
        self.plant.attached[k] = False
        vel = np.array([random.uniform(-0.25, 0.25), -0.22, random.uniform(-0.2, 0.2)])
        self.falling.append([P, t, vel, random.uniform(-1.5, 1.5)])


def build_frame(sc, t):
    cols, rows = sc.cols, sc.rows
    pl = sc.plant
    sway = 0.22 * math.sin(t * 0.9) + 0.08 * math.sin(t * 2.1)
    bloom = float(smooth((t - T_BLOOM0) / (T_BLOOM1 - T_BLOOM0)))
    grow_bud = float(smooth((t - T_BUD0) / (T_BUD1 - T_BUD0)))
    grow_stem = float(np.clip((t - T_STEM0) / (T_STEM1 - T_STEM0), 0, 1))
    dissolve = float(np.clip((t - T_DISSOLVE) / 2.5, 0, 1))

    # ---- petals falling: a few solo ones, then all of them
    if sc.solo_done < len(SOLO_FALLS) and t >= SOLO_FALLS[sc.solo_done]:
        outer = [k for k in range(N_PETALS - 1, N_PETALS // 2, -1) if pl.attached[k]]
        if outer:
            sc.detach(random.choice(outer[:6]), t, bloom, grow_bud)
        sc.solo_done += 1
    if t >= T_SHED:
        if sc.shed_next is None:
            sc.shed_next = T_SHED
        while t >= sc.shed_next and pl.attached.any():
            k = int(np.nonzero(pl.attached)[0][-1])       # outer to inner
            sc.detach(k, t, bloom, grow_bud)
            sc.shed_next += 0.11

    parts_P, parts_N, parts_L, parts_K = [], [], [], []

    def add(Ploc, Nloc, pal, base=1.0, rim=0.35, edge_mask=None, darken=None):
        Pw = transform(Ploc, t, sway)
        if Nloc is None:
            Nw = normals(Pw)
        else:
            Nw = transform(Ploc + Nloc * 0.01, t, sway) - Pw
            Nw /= np.linalg.norm(Nw, axis=-1, keepdims=True) + 1e-9
        L = shade(Pw, Nw, base, rim)
        if darken is not None:
            L = L * darken
        K = np.full(L.shape, pal)
        if edge_mask is not None:
            K = np.where(edge_mask, EDGE, K)
            L = np.where(edge_mask, np.minimum(1, L * 1.25 + 0.08), L)
        parts_P.append(Pw.reshape(-1, 3)); parts_L.append(L.ravel()); parts_K.append(K.ravel())

    if grow_bud > 0:
        P = pl.petals(bloom, grow_bud)
        keep = pl.attached
        edge = (np.abs(W) > 0.82) | (S > 0.88)
        edge = np.broadcast_to(edge, P.shape[:3])
        dark = (0.3 + 0.7 * pl.ell ** 0.7)[:, None, None] * (0.55 + 0.45 * S) * np.ones(P.shape[:3])
        if keep.any():
            add(P[keep], None, ROSE, 1.0, 0.4, edge[keep], dark[keep])
        if dissolve < 1:
            add(pl.sepals(grow_bud), None, SEPAL, 0.9, 0.2)

    # falling petals (flutter down, then crumble into bits)
    alive = []
    for fp in sc.falling:
        P0, td, vel, sp = fp
        a = t - td
        c = P0.reshape(-1, 3).mean(0)
        ang = sp * a
        ca, sa = math.cos(ang), math.sin(ang)
        Q = P0 - c
        Q = np.stack([Q[..., 0] * ca - Q[..., 1] * sa, Q[..., 0] * sa + Q[..., 1] * ca, Q[..., 2]], -1)
        drift = vel * a + np.array([0.25 * math.sin(a * 2.2 + sp), -0.05 * a * a, 0])
        Pn = Q + c + drift
        if a > 2.6 or Pn[..., 1].mean() < -2.0:
            sc.add_crumbs(Pn.reshape(-1, 3)[::9], ROSE, 0.012, 1.4)
            continue
        edge = np.broadcast_to((np.abs(W[0]) > 0.86) | (S[0] > 0.9), Pn.shape[:2])
        add(Pn[None], None, ROSE, 1.0, 0.4, edge[None])
        alive.append(fp)
    sc.falling = alive

    # stem + leaves (they turn into bits at the end)
    if grow_stem > 0 and dissolve < 1:
        top = grow_stem * (1 - dissolve)
        sp_, sn = pl.stem(top)
        if len(sp_):
            add(sp_, sn, STEM, 1.4, 0.35)
        for (v, side, length) in pl.leaves:
            unf = float(smooth((t - T_LEAF0 - v * 1.2) / 1.4)) * (1 - dissolve)
            if unf > 0.02:
                lp = pl.leaf(v, side, length, unf)
                mid = np.broadcast_to(np.abs(W[0]) < 0.1, lp.shape[1:3])[None]
                add(lp, None, LEAF, 1.3, 0.35, darken=np.where(mid, 0.6, 1.0))
    if 0 < dissolve < 1 and random.random() < 0.9:
        v = np.random.random(12) * (1 - dissolve)
        sc.add_crumbs(pl.stem_c[(v * 139).astype(int)], STEM, 0.015, 1.2)

    # ---- splat surfaces into the letter grid (front-most wins, anti-aliased)
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
        front = z <= zmin[idx] + 0.04
        lsum = np.zeros(n); cnt = np.zeros(n)
        np.add.at(lsum, idx[front], L[front]); np.add.at(cnt, idx[front], 1)
        order = np.argsort(-z[front])
        pa[idx[front][order]] = K[front][order]
        has = cnt > 0
        lv = np.maximum(lsum[has] / cnt[has], 0.08)
        br[has] = lv
        ch[has] = RAMP_CODES[np.clip((lv * (len(RAMP) - 1)).astype(int), 1, len(RAMP) - 1)]

    # ---- dew drops (only on petals still attached and facing us)
    if bloom > 0.6 and t < T_SHED:
        P = pl.petals(bloom, grow_bud)
        for (k, si, wi, ph) in pl.dew:
            if not pl.attached[k]:
                continue
            Pw = transform(P[k, si, wi], t, sway)
            x, y = sc.project(Pw)
            x, y = int(x), int(y)
            if 0 <= x < cols and 0 <= y < rows and Pw[2] <= zmin[y * cols + x] + 0.03:
                j = y * cols + x
                tw = 0.5 + 0.5 * math.sin(t * 2.5 + ph)
                ch[j], br[j], pa[j] = ord("o" if tw < 0.8 else "@"), 0.75 + 0.25 * tw, DEW
                if tw > 0.985 and random.random() < 0.3:
                    sc.stars.append([x, y, 0.0, 0.5, 1])

    # ---- bits: void dust, builders, crumbs (all numpy)
    def put_points(Ploc, b, chars, pals):
        if not len(Ploc):
            return
        Pw = transform(Ploc, t, 0.0)
        x, y = sc.project(Pw)
        x, y = x.astype(int), y.astype(int)
        ok = (x >= 0) & (x < cols) & (y >= 0) & (y < rows) & (b > 0.03)
        j = y[ok] * cols + x[ok]
        front = Pw[ok, 2] < zmin[j]
        j = j[front]
        ch[j] = chars[ok][front]; br[j] = b[ok][front]; pa[j] = pals[ok][front]

    dust_fade = 1.0 if t < T_BUD1 + 2 else max(0.0, 1 - (t - T_BUD1 - 2) / 3)
    if dust_fade > 0:
        sc.d_pos += sc.d_vel
        put_points(sc.d_pos, np.full(len(sc.d_pos), 0.12 * dust_fade), sc.d_char,
                   np.full(len(sc.d_pos), BITS))
    s_ = np.clip((t - sc.b_t0) / (sc.b_t1 - sc.b_t0), 0, 1)
    live = t < sc.b_t1
    flying = int(((s_ > 0) & live).sum())
    if live.any():
        e = smooth(s_[live])[:, None]
        sw = (0.4 * (1 - e) * e)
        ang = s_[live][:, None] * 6
        swirl = np.concatenate([np.cos(ang), np.zeros_like(ang), np.sin(ang)], 1) * sw
        P = sc.b_start[live] + (sc.b_target[live] - sc.b_start[live]) * e + swirl
        b = np.where(s_[live] == 0, 0.14, 0.35 + 0.6 * e[:, 0])
        put_points(P, b, sc.b_char[live], np.full(len(P), BITS))
    if len(sc.c_pos):
        sc.c_pos += sc.c_vel
        sc.c_age += 1 / FPS
        keep = sc.c_age < sc.c_life
        sc.c_pos, sc.c_vel, sc.c_age = sc.c_pos[keep], sc.c_vel[keep], sc.c_age[keep]
        sc.c_life, sc.c_pal = sc.c_life[keep], sc.c_pal[keep]
        chars = np.where(np.arange(len(sc.c_pos)) % 2 == 0, ord("0"), ord("1"))
        put_points(sc.c_pos, 0.65 * (1 - sc.c_age / sc.c_life), chars, sc.c_pal)

    # ---- star glints
    kept = []
    for st in sc.stars:
        st[2] += 1 / FPS
        if st[2] < st[3]:
            k = math.sin(math.pi * st[2] / st[3])
            x, y, arm = st[0], st[1], st[4]
            pts = [(0, 0, "*", 1.0)] + [(d, 0, "-", 0.6) for d in (-2, -1, 1, 2)] + \
                  [(0, d, "|", 0.6) for d in (-1, 1)]
            for dx, dy, c, f in pts:
                xx, yy = x + dx, y + dy
                if 0 <= xx < cols and 0 <= yy < rows:
                    j = yy * cols + xx
                    if k * f > br[j] * 0.8:
                        ch[j], br[j], pa[j] = ord(c), min(1.0, k * f + 0.1), STAR
            kept.append(st)
    sc.stars = kept

    phase = ("void" if t < T_STEM0 else "growing" if t < T_BUD0 else "bud" if t < T_BLOOM0 else
             "blooming" if t < T_BLOOM1 else "in bloom" if t < T_SHED else
             "petals falling" if t < T_DISSOLVE else "returning to the void")
    return ch.reshape(rows, cols), br.reshape(rows, cols), pa.reshape(rows, cols), \
        int(pl.attached.sum()) if grow_bud > 0 else 0, flying, phase


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


def draw_hud(screen, ren, t, petals, bits, letters, phase, fps):
    w, h = screen.get_size()
    dim, pink = (110, 118, 128), (225, 110, 150)
    f = ren.hud
    lh = f.get_linesize()
    screen.blit(f.render(f"t {t:05.2f}s", True, pink), (w - 100, 8))
    for i, line in enumerate((f"{HANDLE} · 2026", f"petals {petals}",
                              f"letters {letters:,}", phase)):
        screen.blit(f.render(line, True, dim), (10, h - 26 - (4 - i) * lh))
    pygame.draw.line(screen, (30, 34, 40), (0, h - 22), (w, h - 22))
    screen.blit(f.render("py rose.py", True, dim), (6, h - 19))
    txt = f.render(f"running · {fps:.0f} fps", True, dim)
    screen.blit(txt, (w - txt.get_width() - 8, h - 19))


def main():
    pygame.init()
    pygame.display.set_caption("rose.py")
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
        if t > T_RESTART:
            sc, start = new_scene()
            t = 0.0
        ch, br, pa, petals, bits, phase = build_frame(sc, t)
        fade = min(1.0, t / 0.8 + 0.2) * (1.0 if t < T_RESTART - 1 else max(0.0, T_RESTART - t))
        ren.draw(screen, ch, br, pa, fade)
        draw_hud(screen, ren, t, petals, bits, int((ch != 0).sum()), phase, clock.get_fps())
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()