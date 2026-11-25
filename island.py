"""
palm.py - a detailed 3D coconut palm grown from bits, drawn in ASCII.

The trunk builds itself from the ground up (rings and bark and all), 16
fronds unfurl from the crown with hundreds of leaflets fanning open,
coconuts appear, and the palm sways in the wind and slowly turns.

Setup (once):   pip install pygame-ce numpy
Run:            python palm.py

Fairy lights spiral up the trunk and drape along the fronds, switch on one
by one, and a star lights up on top. The lights cycle through patterns.

Then the night comes alive: a full moon over the ocean, shooting stars,
fireflies, shiny baubles hanging from the fronds, presents on the sand, and
fireworks bursting over the sea, reflected in the water, with a grand finale.

Keys:
    F         fireworks volley now!
    L         next light pattern (twinkle / chase / rainbow / sparkle)
    Space     grow it again
    F11       fullscreen on/off
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
N_FRONDS = 16
GLOW = 1.0
SPIN = 0.1                # slow turn so you see it in 3D
WIND = 1.0                # 0 = still, 2 = stormy
LIGHT_MODES = ["twinkle", "chase", "rainbow", "sparkle"]
MODE_SECONDS = 10         # light pattern changes this often
FIREWORKS = True
FINALE_EVERY = 40         # seconds between grand finales
N_FIREFLIES = 26

TAU = 2 * math.pi
GOLDEN = 2.39996323
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
RAMP_CODES = np.array([ord(c) for c in RAMP], dtype=np.int32)

# timeline (seconds)
T_TRUNK0, T_TRUNK1 = 1.8, 5.2
T_FROND0, T_FROND1 = 4.8, 9.0
T_NUTS = 8.6
T_LIGHT0, T_LIGHT1 = 9.6, 13.4    # lights switch on one by one
T_STAR = 13.8
T_FW = 16.0              # first firework

(FROND, FROND_OLD, RACHIS, TRUNK, NUT_G, NUT_B, SAND, BITS, STAR, RED, GREEN, GOLD, BLUE, PINK, WIRE,
 FOAM, FIREFLY, SEA, MOON, WHITE) = range(20)
BULB_COLOURS = [RED, GOLD, GREEN, BLUE, PINK]
PALETTES = [(80, 190, 95), (205, 175, 85), (160, 200, 95), (190, 155, 120),
            (150, 200, 80), (190, 125, 65), (215, 190, 140), (170, 200, 255), (200, 215, 255), (255, 60, 70), (80, 255, 120), (255, 205, 80), (90, 170, 255), (255, 110, 210), (60, 90, 60),
            (190, 225, 255), (215, 255, 120), (60, 115, 200), (255, 246, 214), (255, 255, 255)]


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def colour(level, pal):
    b = level / 15
    r, g, bl = PALETTES[pal]
    k = b ** 0.85
    w = max(0.0, b - 0.88) * 2.0
    return (int(min(255, r * k + (255 - r) * w)),
            int(min(255, g * k + (255 - g) * w)),
            int(min(255, bl * k + (255 - bl) * w)))


def line_char(dx, dy):
    a = math.degrees(math.atan2(dy, dx)) % 180
    if a < 22 or a >= 158:
        return "-"
    if a < 68:
        return "\\"
    if a < 112:
        return "|"
    return "/"


def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


# --------------------------------------------------------------------- palm --
TRUNK_H = 7.0


def trunk_centre(s):
    s = np.asarray(s, float)
    return np.stack([1.1 * s ** 1.8 - 0.08 * np.sin(s * math.pi),
                     TRUNK_H * s,
                     0.18 * np.sin(s * math.pi * 1.2)], -1)


TOP = trunk_centre(1.0) + np.array([0, 0.05, 0])


class Palm:
    def __init__(self):
        # fronds in a spiral: top ones reach up, low ones droop (old ones go yellow)
        self.fr = []
        for i in range(N_FRONDS):
            f = i / (N_FRONDS - 1)                         # 0 = newest (top) .. 1 = oldest
            elev = math.radians(62 - 100 * f + random.uniform(-6, 6))
            self.fr.append(dict(phi=i * GOLDEN + random.uniform(-0.15, 0.15), elev=elev,
                                L=random.uniform(2.8, 3.3) * (0.8 if f < 0.1 else 1.0),
                                droop=0.08 + 0.14 * f + random.uniform(-0.02, 0.02),
                                old=f > 0.82, ph=random.uniform(0, TAU),
                                delay=(1 - f) * 0.45 + random.uniform(0, 0.08)))
        self.rachis = {}
        # fairy lights: a spiral up the trunk, then draped along every frond
        self.lights = []
        n_trunk = 72
        for k in range(n_trunk):
            s_ = 0.05 + 0.92 * k / n_trunk
            self.lights.append(dict(kind="trunk", s=s_, ang=s_ * TAU * 9.5))
        for i in range(N_FRONDS):
            for u in np.linspace(0.18, 0.95, 7):
                self.lights.append(dict(kind="frond", f=i, ui=int(u * (len(U) - 1))))
        for k, L in enumerate(self.lights):
            L["pal"] = BULB_COLOURS[k % len(BULB_COLOURS)]
            L["on"] = T_LIGHT0 + k / len(self.lights) * (T_LIGHT1 - T_LIGHT0)
            L["ph"] = random.uniform(0, TAU)
            L["k"] = k
        self.baubles = []
        cols_ = [RED, GOLD, BLUE, PINK, GREEN, WHITE]
        for n_, i in enumerate(range(2, N_FRONDS - 1, 1)):
            if i % 2:
                continue
            self.baubles.append(dict(f=i, ui=int(random.uniform(0.45, 0.8) * (len(U) - 1)),
                                     drop=random.uniform(0.3, 0.5), r=random.uniform(0.09, 0.12),
                                     pal=cols_[n_ % len(cols_)], ph=random.uniform(0, TAU)))
        self.flies = [dict(c=np.array([random.uniform(-2.2, 2.6), random.uniform(1.0, 8.5),
                                       random.uniform(-1.8, 1.8)]),
                           ph=np.random.uniform(0, TAU, 3), w=np.random.uniform(0.3, 0.8, 3))
                      for _ in range(N_FIREFLIES)]
        # coconuts clustered under the crown
        self.nuts = []
        for k in range(10):
            a = k * 2.2 + random.uniform(-0.2, 0.2)
            r = 0.26 + 0.08 * (k % 3)
            self.nuts.append((TOP + np.array([r * math.cos(a), -0.32 - 0.1 * (k % 3), r * math.sin(a)]),
                              random.uniform(0.17, 0.2), NUT_G if k % 3 else NUT_B))


# sample grids
U = np.linspace(0.06, 1.0, 24)                      # leaflet stations along a frond
V = np.linspace(0.0, 1.0, 16)                       # along a leaflet
WS = np.array([0.0])                          # across a leaflet
SIDES = np.array([-1.0, 1.0])
FIB = np.array([[math.cos(i * 2.39996) * math.sqrt(1 - ((i + 0.5) / 90 * 2 - 1) ** 2),
                 (i + 0.5) / 90 * 2 - 1,
                 math.sin(i * 2.39996) * math.sqrt(1 - ((i + 0.5) / 90 * 2 - 1) ** 2)] for i in range(90)])


def fronds_geometry(palm, t, grow):
    """All leaflets and rachises as points + normals + palette, numpy."""
    P_all, N_all, K_all, B_all = [], [], [], []
    palm.rachis = {}
    wind = WIND
    for i, f in enumerate(palm.fr):
        g = float(smooth((grow - f["delay"]) / 0.55))
        if g <= 0.01:
            continue
        sway = 0.06 * wind * math.sin(t * 0.9 + f["ph"]) + 0.03 * wind * math.sin(t * 2.3 + f["ph"] * 2)
        phi = f["phi"] + sway * 0.6
        elev = f["elev"] + sway
        d0 = np.array([math.cos(phi) * math.cos(elev), math.sin(elev), math.sin(phi) * math.cos(elev)])
        L = f["L"] * (0.25 + 0.75 * g)
        k = f["droop"] * (1.3 - 0.3 * g)
        gvec = np.array([0, -1.0, 0])
        u = U[:, None]
        R = TOP + d0 * L * u + gvec * k * (L * u) ** 2               # rachis (U,3)
        Tg = unit(d0 * L + 2 * gvec * k * L * L * u)
        lat = unit(np.cross(Tg, [0, 1.0, 0]))
        up = unit(np.cross(lat, Tg))

        palm.rachis[i] = (R, up, g)
        # rachis: thin bright stem
        P_all.append(R); N_all.append(up); K_all.append(np.full(len(R), RACHIS))
        B_all.append(np.full(len(R), 0.85))

        # leaflets fan open as the frond unfurls
        open_ = float(smooth((grow - f["delay"] - 0.25) / 0.6))
        alpha = 0.5 + (1 - open_) * 0.95                              # folded along the rachis
        shape = np.sin(np.pi * (0.12 + 0.88 * U)) ** 0.7               # short at base & tip
        ll = 0.52 * shape * (0.3 + 0.7 * open_) * (L / 2.6)            # (U,)
        flutter = 0.08 * wind * np.sin(t * 4.2 + U * 9 + f["ph"])     # (U,)
        s = SIDES[:, None, None]
        dirn = unit(s * lat[None] * math.cos(alpha) + Tg[None] * math.sin(alpha)
                    - up[None] * (0.55 + flutter[None, :, None]))      # (2,U,3) drooping V
        wv = unit(np.cross(dirn, Tg[None]))                           # leaflet width direction
        v = V[None, None, :, None, None]
        Lv = ll[None, :, None, None, None] * v
        Pts = (R[None, :, None, None, :] + dirn[:, :, None, None, :] * Lv
               + np.array([0, -1.0, 0]) * 0.28 * Lv ** 2 / (ll.max() + 1e-6)
               + wv[:, :, None, None, :] * WS[None, None, None, :, None] * 0.03 * (1 - 0.8 * v))
        Nrm = np.broadcast_to(wv[:, :, None, None, :] * 0 + unit(np.cross(dirn, wv))[:, :, None, None, :], Pts.shape)
        alt = (0.8 + 0.2 * (np.arange(len(U)) % 2))[None, :, None, None]
        tipfade = np.broadcast_to((0.7 + 0.3 * (1 - V))[None, None, :, None] * alt, Pts.shape[:-1])
        P_all.append(Pts.reshape(-1, 3)); N_all.append(Nrm.reshape(-1, 3))
        K_all.append(np.full(Pts.shape[:-1], FROND_OLD if f["old"] else FROND).ravel())
        B_all.append(tipfade.ravel())
    if not P_all:
        return None
    return np.concatenate(P_all), np.concatenate(N_all), np.concatenate(K_all), np.concatenate(B_all)


def trunk_frame(s):
    """Centre, two sideways directions and radius of the trunk at heights s."""
    s = np.atleast_1d(np.asarray(s, float))
    c = trunk_centre(s)
    tg = unit(trunk_centre(np.minimum(s + 1e-3, 1)) - trunk_centre(np.maximum(s - 1e-3, 0)))
    side = unit(np.cross(tg, [0, 0, 1.0]))
    up = unit(np.cross(side, tg))
    r = 0.2 * (1 - 0.35 * s) + 0.14 * np.exp(-s * 16)
    return c, side, up, r


def trunk_geometry(grow):
    s = np.linspace(0, 1, 420)
    s = s[s <= grow]
    if len(s) < 2:
        return None
    th = np.linspace(0, TAU, 30, endpoint=False)
    c = trunk_centre(s)
    tg = unit(np.gradient(c, axis=0))
    side = unit(np.cross(tg, [0, 0, 1.0]))
    up = unit(np.cross(side, tg))
    rings = np.abs(np.sin(s * 70 * math.pi))                    # leaf-scar rings
    r = 0.2 * (1 - 0.35 * s) + 0.14 * np.exp(-s * 16) + 0.014 * rings
    n = np.cos(th)[None, :, None] * side[:, None, :] + np.sin(th)[None, :, None] * up[:, None, :]
    P = c[:, None, :] + n * r[:, None, None]
    bark = (0.72 + 0.28 * rings[:, None]) * (0.9 + 0.1 * np.sin(th[None, :] * 7 + s[:, None] * 60))
    return P.reshape(-1, 3), n.reshape(-1, 3), np.full(P.shape[0] * P.shape[1], TRUNK), 1.35 * bark.ravel()


def nuts_geometry(palm, k):
    if k <= 0:
        return None
    P, N, K = [], [], []
    for (c, r, pal) in palm.nuts:
        P.append(c + FIB * r * k); N.append(FIB); K.append(np.full(len(FIB), pal))
    P = np.concatenate(P)
    return P, np.concatenate(N), np.concatenate(K), np.ones(len(P))


def sand_geometry():
    r = np.sqrt(np.random.random(2600)) * 1.7
    a = np.random.uniform(0, TAU, 2600)
    y = 0.18 * (1 - (r / 1.7) ** 2) - 0.03
    P = np.stack([r * np.cos(a), y, r * np.sin(a)], 1)
    N = unit(np.stack([np.cos(a) * 0.25 * r, np.ones_like(r), np.sin(a) * 0.25 * r], 1))
    return P, N, np.full(len(P), SAND), np.full(len(P), 0.55)


SAND_GEO = None


def presents_geometry():
    """Wrapped gift boxes with ribbons and bows on the sand."""
    boxes = [((0.62, 0.3), 0.42, RED, GOLD, 0.4), ((-0.55, 0.45), 0.34, GREEN, RED, -0.3),
             ((0.15, -0.7), 0.3, BLUE, GOLD, 0.9), ((-0.62, -0.38), 0.27, GOLD, RED, 0.2),
             ((0.95, -0.25), 0.22, PINK, WHITE, -0.6)]
    g = np.linspace(-1, 1, 11)
    A, B = [x.ravel() for x in np.meshgrid(g, g)]
    P, N, K, L = [], [], [], []
    for (cx, cz), size, col, rib, rot in boxes:
        h = size * 0.85
        base = np.array([cx, 0.12, cz])
        cr, sr = math.cos(rot), math.sin(rot)
        R = np.array([[cr, 0, sr], [0, 1, 0], [-sr, 0, cr]])
        faces = [  # (points in box space, normal, ribbon mask)
            (np.stack([A, np.ones_like(A), B], 1), [0, 1, 0], (np.abs(A) < 0.18) | (np.abs(B) < 0.18)),
            (np.stack([A, (B + 1) / 2 * 2 - 1, np.ones_like(A)], 1), [0, 0, 1], np.abs(A) < 0.18),
            (np.stack([A, (B + 1) / 2 * 2 - 1, -np.ones_like(A)], 1), [0, 0, -1], np.abs(A) < 0.18),
            (np.stack([np.ones_like(A), (B + 1) / 2 * 2 - 1, A], 1), [1, 0, 0], np.abs(A) < 0.18),
            (np.stack([-np.ones_like(A), (B + 1) / 2 * 2 - 1, A], 1), [-1, 0, 0], np.abs(A) < 0.18)]
        for pts, nrm, mask in faces:
            q = pts * np.array([size / 2, h / 2, size / 2])
            q[:, 1] += h / 2
            P.append(q @ R.T + base)
            N.append(np.tile(np.array(nrm, float) @ R.T, (len(q), 1)))
            K.append(np.where(mask, rib, col))
            L.append(np.where(mask, 1.1, 0.95))
        # bow: two loops on top
        a = np.linspace(0, TAU, 24)
        for side in (-1, 1):
            loop = np.stack([side * (0.06 + 0.06 * np.cos(a)) * size * 2, h + 0.07 * size * 2 * (1 + np.sin(a)),
                             np.zeros_like(a)], 1) * np.array([1, 1, 1])
            loop[:, 1] = h + 0.03 + 0.12 * size * (1 + np.sin(a)) * 0.5
            P.append(loop @ R.T + base); N.append(np.tile([0, 0, 1.0], (len(a), 1)) @ R.T)
            K.append(np.full(len(a), rib)); L.append(np.full(len(a), 1.2))
    return np.concatenate(P), unit(np.concatenate(N)), np.concatenate(K), np.concatenate(L)


PRESENTS_GEO = presents_geometry()


def foam_geometry(t):
    a = np.linspace(0, TAU, 360, endpoint=False)
    wave = np.sin(a * 9 - t * 2.2)
    r = 1.72 + 0.08 * wave
    P = np.stack([r * np.cos(a), np.full_like(a, 0.0), r * np.sin(a)], 1)
    keep = wave > -0.2
    return P[keep], np.tile([0, 1.0, 0], (keep.sum(), 1)), np.full(keep.sum(), FOAM), (0.55 + 0.35 * wave[keep])


def baubles_geometry(palm, t, k):
    """Shiny christmas baubles hanging on threads from the fronds."""
    if k <= 0:
        return None
    P, N, K, L = [], [], [], []
    for b in palm.baubles:
        if b["f"] not in palm.rachis:
            continue
        R, upv, g = palm.rachis[b["f"]]
        if g < 0.95:
            continue
        A = R[b["ui"]]
        swing = 0.05 * math.sin(t * 1.7 + b["ph"])
        C = A + np.array([swing, -b["drop"] * k, swing * 0.5])
        th = np.linspace(0, 1, 14)[:, None]                     # thread
        P.append(A + (C - A) * th); N.append(np.tile([0, 0, 1.0], (14, 1)))
        K.append(np.full(14, WIRE)); L.append(np.full(14, 0.7))
        P.append(C + FIB * b["r"] * k); N.append(FIB)
        K.append(np.full(len(FIB), b["pal"])); L.append(np.full(len(FIB), 1.15))
    if not P:
        return None
    return np.concatenate(P), np.concatenate(N), np.concatenate(K), np.concatenate(L)


# ------------------------------------------------------------ camera, light --
LIGHT = unit(np.array([0.5, 0.7, -0.55]))


def transform(P, t):
    yaw = 0.6 + SPIN * t
    cy, sy = math.cos(yaw), math.sin(yaw)
    x = P[..., 0] * cy + P[..., 2] * sy
    z = -P[..., 0] * sy + P[..., 2] * cy
    tilt = -0.14
    ct, st = math.cos(tilt), math.sin(tilt)
    y = P[..., 1] - 4.75
    y2, z2 = y * ct - z * st, y * st + z * ct
    return np.stack([x - 0.6, y2, z2 + 15.5], -1)


def rotate_normals(N, t):
    yaw = 0.6 + SPIN * t
    cy, sy = math.cos(yaw), math.sin(yaw)
    x = N[..., 0] * cy + N[..., 2] * sy
    z = -N[..., 0] * sy + N[..., 2] * cy
    tilt = -0.14
    ct, st = math.cos(tilt), math.sin(tilt)
    y = N[..., 1]
    return np.stack([x, y * ct - z * st, y * st + z * ct], -1)


def shade(Pw, Nw, base):
    V = unit(-Pw)
    nv = np.sum(Nw * V, -1)
    Nw = Nw * np.sign(nv + 1e-9)[..., None]                # two-sided leaflets
    nv = np.abs(nv)
    diff = np.clip(Nw @ LIGHT, 0, 1)
    R = 2 * nv[..., None] * Nw - V
    spec = np.clip(R @ LIGHT, 0, 1) ** 20
    return np.clip(base * (0.3 + 0.6 * diff) + 0.22 * (1 - nv) ** 2 + 0.2 * spec, 0, 1)


# -------------------------------------------------------------------- scene --
class Scene:
    def __init__(self, cols, rows, aspect):
        global SAND_GEO
        self.cols, self.rows, self.aspect = cols, rows, aspect
        self.F = 0.95 * rows * 12.0 / (9.0 * aspect)
        self.palm = Palm()
        self.mode_pick = None
        self.glows = []
        self.H = int(rows * 0.74)                                 # horizon row
        # moon (pre-shaded cells)
        mx, my, mr = cols * 0.83, rows * 0.15, rows * 0.075
        self.moon = (mx, my, mr)
        mc = []
        for yy in range(int(my - mr) - 1, int(my + mr) + 2):
            for xx in range(int(mx - mr / aspect) - 1, int(mx + mr / aspect) + 2):
                dx, dy = (xx - mx) * aspect / mr, (yy - my) / mr
                d2 = dx * dx + dy * dy
                if d2 < 1:
                    z = math.sqrt(1 - d2)
                    light = 0.35 + 0.65 * max(0.0, -0.4 * dx - 0.3 * dy + 0.85 * z)
                    crater = 0.8 + 0.2 * math.sin(dx * 9.1 + dy * 4.3) * math.sin(dy * 7.7 - dx * 3.1)
                    mc.append((xx, yy, light * crater))
        self.moon_cells = np.array(mc)
        # fireworks: x, y, vx, vy, age, life, pal, kind, drag, trail
        self.fw = np.zeros((0, 10))
        self.rockets = []
        self.next_fw = T_FW
        self.next_finale = T_FW + 22
        self.fired = 0
        self.flash = 0.0
        self.flash_pal = GOLD
        self.shoot = None
        self.next_shoot = 4.0
        if SAND_GEO is None:
            SAND_GEO = sand_geometry()
        self.stars = [(random.randrange(cols), random.randrange(rows), random.uniform(0, TAU))
                      for _ in range(cols * rows // 160)]
        # bits that build the trunk and the crown
        n1, n2 = 900, 1100
        s = np.random.random(n1)
        trunk_t = trunk_centre(s) + np.random.normal(scale=0.08, size=(n1, 3))
        crown_t = []
        for _ in range(n2):
            f = random.choice(self.palm.fr)
            u = random.random()
            d0 = np.array([math.cos(f["phi"]) * math.cos(f["elev"]), math.sin(f["elev"]),
                           math.sin(f["phi"]) * math.cos(f["elev"])])
            crown_t.append(TOP + d0 * f["L"] * u + np.array([0, -1.0, 0]) * f["droop"] * (f["L"] * u) ** 2)
        self.b_tgt = np.concatenate([trunk_t, np.array(crown_t)])
        self.b_t1 = np.concatenate([T_TRUNK0 + s * (T_TRUNK1 - T_TRUNK0),
                                    np.random.uniform(T_FROND0, T_FROND1 - 1.5, n2)])
        self.b_t0 = self.b_t1 - np.random.uniform(1.0, 2.0, len(self.b_t1))
        self.b_start = np.random.uniform([-5, -0.5, -3], [5, 9.5, 3], (len(self.b_t1), 3))
        self.b_char = np.where(np.random.random(len(self.b_t1)) < 0.5, ord("0"), ord("1"))

    def project(self, P):
        Z = P[..., 2]
        return (self.cols / 2 + P[..., 0] * self.F / Z,
                self.rows / 2 - P[..., 1] * self.F * self.aspect / Z)


def build_frame(sc, t):
    cols, rows = sc.cols, sc.rows
    n = cols * rows
    ch = np.zeros(n, np.int32); br = np.zeros(n, np.float32); pa = np.zeros(n, np.int8)

    sc.glows = []
    draw_background(sc, t, ch.reshape(rows, cols), br.reshape(rows, cols), pa.reshape(rows, cols))

    parts = []
    ground = float(smooth(t / 1.5))
    if ground > 0:
        P, N, K, B = SAND_GEO
        parts.append((P, N, K, B * ground))
        P, N, K, B = foam_geometry(t)
        parts.append((P, N, K, B * ground))
    tgrow = float(np.clip((t - T_TRUNK0) / (T_TRUNK1 - T_TRUNK0), 0, 1))
    if tgrow > 0:
        g = trunk_geometry(tgrow)
        if g:
            parts.append(g)
    fgrow = (t - T_FROND0) / (T_FROND1 - T_FROND0)
    if fgrow > 0:
        g = fronds_geometry(sc.palm, t, fgrow)
        if g:
            parts.append(g)
    g = nuts_geometry(sc.palm, float(smooth((t - T_NUTS) / 0.8)))
    if g:
        parts.append(g)
    g = baubles_geometry(sc.palm, t, float(smooth((t - T_STAR - 0.5) / 1.0)))
    if g:
        parts.append(g)
    pk = float(smooth((t - T_NUTS) / 1.2))
    if pk > 0:
        P, N, K, B = PRESENTS_GEO
        P = P.copy(); P[:, 1] = P[:, 1] * pk - (1 - pk) * 0.4      # presents pop up out of the sand
        parts.append((P, N, K, B * pk))
    if t > T_LIGHT0 - 0.6:                                   # the wire spirals up first
        wk = float(np.clip((t - (T_LIGHT0 - 0.6)) / (T_LIGHT1 - T_LIGHT0), 0, 1))
        ss = np.linspace(0.05, 0.05 + 0.92 * wk, 900)
        c, side, up, r = trunk_frame(ss)
        a = ss * TAU * 9.5
        nrm = np.cos(a)[:, None] * side + np.sin(a)[:, None] * up
        parts.append((c + nrm * (r[:, None] + 0.035), nrm, np.full(len(ss), WIRE), np.full(len(ss), 0.5)))

    zmin = np.full(n, np.inf)
    if parts:
        P = np.concatenate([p[0] for p in parts]); N = np.concatenate([p[1] for p in parts])
        K = np.concatenate([p[2] for p in parts]); B = np.concatenate([p[3] for p in parts])
        Pw = transform(P, t); Nw = unit(rotate_normals(N, t))
        L = shade(Pw, Nw, B)
        sx, sy = sc.project(Pw)
        ix, iy = sx.astype(int), sy.astype(int)
        ok = (ix >= 0) & (ix < cols) & (iy >= 0) & (iy < rows) & (Pw[:, 2] > 0.5)
        idx = (iy * cols + ix)[ok]; z = Pw[ok, 2]; L = L[ok]; K = K[ok]
        np.minimum.at(zmin, idx, z)
        front = z <= zmin[idx] + 0.05
        lsum = np.zeros(n); cnt = np.zeros(n)
        np.add.at(lsum, idx[front], L[front]); np.add.at(cnt, idx[front], 1)
        order = np.argsort(-z[front])
        pa[idx[front][order]] = K[front][order]
        has = cnt > 0
        lv = np.maximum(lsum[has] / cnt[has], 0.08)
        br[has] = lv
        ch[has] = RAMP_CODES[np.clip((lv * (len(RAMP) - 1)).astype(int), 1, len(RAMP) - 1)]

    plant = np.isfinite(zmin)
    night = 0.3 * float(smooth((t - T_LIGHT0) / 2.0))
    br[plant] *= (1 - night)
    lights_on, mode = draw_lights(sc, t, ch, br, pa, zmin)
    CH, BR, PA = ch.reshape(rows, cols), br.reshape(rows, cols), pa.reshape(rows, cols)
    draw_fireflies(sc, t, CH, BR, PA, zmin.reshape(rows, cols))
    draw_fireworks(sc, t, CH, BR, PA, ~plant.reshape(rows, cols))

    # bits flying in
    s_ = np.clip((t - sc.b_t0) / (sc.b_t1 - sc.b_t0), 0, 1)
    live = (t < sc.b_t1)
    if live.any():
        e = smooth(s_[live])[:, None]
        ang = s_[live][:, None] * 6
        swirl = np.concatenate([np.cos(ang), np.zeros_like(ang), np.sin(ang)], 1) * 0.5 * (1 - e) * e
        Pb = sc.b_start[live] + (sc.b_tgt[live] - sc.b_start[live]) * e + swirl
        b = np.where(s_[live] == 0, 0.12, 0.35 + 0.6 * e[:, 0])
        Pw = transform(Pb, t)
        x, y = sc.project(Pw)
        x, y = x.astype(int), y.astype(int)
        ok = (x >= 0) & (x < cols) & (y >= 0) & (y < rows)
        j = y[ok] * cols + x[ok]
        front = Pw[ok, 2] < zmin[j]
        j = j[front]
        ch[j] = sc.b_char[live][ok][front]; br[j] = b[ok][front]; pa[j] = BITS

    phase = ("void" if t < T_TRUNK0 else "trunk" if t < T_FROND0 else
             "fronds unfurling" if t < T_FROND1 else "lights on" if t < T_STAR else
             f"fireworks · {mode}" if t > T_FW else mode)
    return ch.reshape(rows, cols), br.reshape(rows, cols), pa.reshape(rows, cols), phase, lights_on


def draw_background(sc, t, CH, BR, PA):
    """Stars, shooting stars, the moon and the ocean (screen space, behind the palm)."""
    cols, rows, H = sc.cols, sc.rows, sc.H
    k = float(smooth(t / 2.5))
    for (x, y, ph) in sc.stars:
        if y >= H - 1:
            continue
        v = 0.5 + 0.5 * math.sin(t * 1.4 + ph)
        if v > 0.55:
            CH[y, x], BR[y, x], PA[y, x] = ord("*" if v > 0.97 else "."), (0.08 + 0.3 * v ** 3) * k, STAR
    # shooting star
    if t > sc.next_shoot and sc.shoot is None:
        sc.shoot = dict(x=random.uniform(cols * 0.2, cols * 0.9), y=random.uniform(2, H * 0.35),
                        vx=random.choice((-1, 1)) * random.uniform(2.0, 3.0), vy=random.uniform(0.5, 0.9), a=0.0)
        sc.next_shoot = t + random.uniform(5, 11)
    if sc.shoot:
        sh = sc.shoot
        sh["a"] += 1 / FPS; sh["x"] += sh["vx"]; sh["y"] += sh["vy"]
        if sh["a"] > 0.9:
            sc.shoot = None
        else:
            f = math.sin(math.pi * sh["a"] / 0.9)
            for i in range(14):
                x, y = int(sh["x"] - sh["vx"] * i * 0.5), int(sh["y"] - sh["vy"] * i * 0.5)
                if 0 <= x < cols and 0 <= y < H:
                    CH[y, x] = ord("*" if i == 0 else line_char(sh["vx"], sh["vy"]))
                    BR[y, x], PA[y, x] = f * (1 - i / 14), WHITE
    # moon
    mx, my, mr = sc.moon
    mc = sc.moon_cells
    xs, ys = mc[:, 0].astype(int), mc[:, 1].astype(int)
    ok = (xs >= 0) & (xs < cols) & (ys >= 0) & (ys < rows)
    lum = mc[ok, 2] * k
    CH[ys[ok], xs[ok]] = RAMP_CODES[np.clip((lum * (len(RAMP) - 1)).astype(int), 1, len(RAMP) - 1)]
    BR[ys[ok], xs[ok]] = lum; PA[ys[ok], xs[ok]] = MOON
    sc.glows.append((int(mx), int(my), MOON, 4.5 * k))
    # ocean
    ys = np.arange(H + 1, rows)
    d = ((ys - H) / max(1, rows - H))[:, None]
    X = np.arange(cols)[None, :]
    wv = np.sin(X * 0.22 / (d + 0.1) + t * 1.5 + ys[:, None] * 0.9) + \
        0.6 * np.sin(X * 0.08 / (d + 0.1) - t * 1.1 + ys[:, None] * 1.7)
    show = wv > -0.15
    chars = np.where(wv > 1.05, ord("~"), np.where(wv > 0.45, ord("-"), ord("_")))
    b = (0.07 + 0.22 * d) * np.where(wv > 1.05, 1.5, 1.0) * k
    sub_c, sub_b, sub_p = CH[H + 1:], BR[H + 1:], PA[H + 1:]
    sub_c[show] = chars[show]; sub_b[show] = b[show]; sub_p[show] = SEA
    glit = (np.abs(X - mx) < 1.5 + 16 * d) & (wv > 0.2) & (np.sin(t * 7 + X * 3.1 + ys[:, None] * 7.3) > 0.1)
    sub_c[glit] = np.where(wv[glit] > 0.9, ord("="), ord("-"))
    sub_b[glit] = (0.45 + 0.4 * (1 - np.broadcast_to(d, glit.shape)[glit])) * k
    sub_p[glit] = MOON
    CH[H, :], BR[H, :], PA[H, :] = ord("_"), 0.2 * k, SEA


def launch(sc, x=None, kind=None):
    x = x if x is not None else random.uniform(sc.cols * 0.08, sc.cols * 0.95)
    sc.rockets.append(dict(x=x, y=float(sc.H), vy=-random.uniform(1.1, 1.45),
                           ty=random.uniform(sc.rows * 0.06, sc.rows * 0.36),
                           pal=random.choice([RED, GOLD, GREEN, BLUE, PINK, WHITE]),
                           kind=kind or random.choice(["peony", "peony", "ring", "willow", "crossette", "double"])))


def explode(sc, x, y, pal, kind):
    a_ = sc.aspect * 1.4
    if kind == "ring":
        n = 110; ang = np.linspace(0, TAU, n, endpoint=False); sp = np.full(n, 1.2)
    elif kind == "willow":
        n = 120; ang = np.random.uniform(0, TAU, n); sp = np.random.uniform(0.3, 1.0, n); pal = GOLD
    elif kind == "crossette":
        n = 22; ang = np.linspace(0, TAU, n, endpoint=False); sp = np.full(n, 1.0)
    else:
        n = 150; ang = np.random.uniform(0, TAU, n); sp = np.random.uniform(0.45, 1.35, n)
    pals = np.full(n, pal)
    if kind == "double":
        pals[n // 2:] = random.choice([RED, GOLD, GREEN, BLUE, PINK])
    kid = {"willow": 1, "crossette": 2}.get(kind, 0)
    life = np.random.uniform(2.4, 3.2, n) if kind == "willow" else np.random.uniform(1.2, 2.0, n)
    drag = 0.94 if kind == "willow" else 0.965
    trail = 4 if kind == "willow" else 2
    new = np.column_stack([np.full(n, x), np.full(n, y), np.cos(ang) * sp, np.sin(ang) * sp * a_,
                           np.zeros(n), life, pals, np.full(n, kid), np.full(n, drag), np.full(n, trail)])
    sc.fw = np.concatenate([sc.fw, new])
    sc.fired += 1
    sc.flash = max(sc.flash, 0.7)
    sc.flash_pal = pal
    sc.glows.append((int(x), int(y), pal if pal in (RED, GOLD, GREEN, BLUE, PINK) else GOLD, 3.0))


def draw_fireworks(sc, t, CH, BR, PA, bg):
    """Rockets, bursts and their reflections - only where the sky/sea shows."""
    cols, rows, H = sc.cols, sc.rows, sc.H
    if FIREWORKS and t > sc.next_fw:
        launch(sc)
        if random.random() < 0.35:
            launch(sc)
        sc.next_fw = t + random.uniform(0.35, 1.1)
    if FIREWORKS and t > sc.next_finale:                     # grand finale
        for _ in range(14):
            launch(sc)
        sc.next_finale = t + FINALE_EVERY
    keep = []
    for r in sc.rockets:
        r["y"] += r["vy"]; r["vy"] *= 0.985
        x, y = int(r["x"]), int(r["y"])
        for dy, c, b in ((0, "|", 0.9), (1, "'", 0.5), (2, ".", 0.3)):
            if 0 <= x < cols and 0 <= y + dy < rows and bg[y + dy, x]:
                CH[y + dy, x], BR[y + dy, x], PA[y + dy, x] = ord(c), b, GOLD
        if r["y"] <= r["ty"] or r["vy"] > -0.3:
            explode(sc, r["x"], r["y"], r["pal"], r["kind"])
        else:
            keep.append(r)
    sc.rockets = keep
    sc.flash *= 0.86
    if not len(sc.fw):
        return
    P = sc.fw
    P[:, 0] += P[:, 2]; P[:, 1] += P[:, 3]
    P[:, 2] *= P[:, 8]; P[:, 3] = P[:, 3] * P[:, 8] + np.where(P[:, 7] == 1, 0.02, 0.03)
    P[:, 4] += 1 / FPS
    # crossettes split into four at 0.55 s
    split = (P[:, 7] == 2) & (P[:, 4] > 0.55)
    if split.any():
        kids = []
        for x, y, vx, vy, a, life, pal, *_ in P[split]:
            for k in range(4):
                ang = math.atan2(vy, vx) + (k - 1.5) * 0.9
                kids.append([x, y, math.cos(ang) * 0.7, math.sin(ang) * 0.7 * sc.aspect * 1.4,
                             0.0, random.uniform(0.7, 1.0), pal, 0, 0.96, 1])
        P = np.concatenate([P[~split], np.array(kids)])
    P = P[(P[:, 4] < P[:, 5]) & (P[:, 1] < H) & (P[:, 1] > -5)]
    sc.fw = P
    if not len(P):
        return
    f = P[:, 4] / P[:, 5]
    b = (1 - f) ** 0.7
    glit = (P[:, 7] == 1) & (np.random.random(len(P)) < 0.25)
    b = np.where(glit, np.minimum(1, b + 0.4), b)
    chars = np.where(f < 0.3, ord("*"), np.where(f < 0.65, ord("+"), ord(".")))
    xs, ys, bs, cs, ps = [P[:, 0]], [P[:, 1]], [b], [chars], [P[:, 6]]
    for k in (1, 2, 3, 4):                                   # trails behind each spark
        m = P[:, 9] >= k
        xs.append(P[m, 0] - P[m, 2] * k * 1.2); ys.append(P[m, 1] - P[m, 3] * k * 1.2)
        bs.append(b[m] * (1 - k / 5) * 0.7); cs.append(np.full(m.sum(), ord("'" if k > 2 else "."))); ps.append(P[m, 6])
    X = np.concatenate(xs).astype(int); Y = np.concatenate(ys).astype(int)
    B = np.concatenate(bs); C = np.concatenate(cs); Pl = np.concatenate(ps).astype(int)
    ok = (X >= 0) & (X < cols) & (Y >= 0) & (Y < H)
    X, Y, B, C, Pl = X[ok], Y[ok], B[ok], C[ok], Pl[ok]
    ok = bg[Y, X]
    X, Y, B, C, Pl = X[ok], Y[ok], B[ok], C[ok], Pl[ok]
    o = np.argsort(B)
    CH[Y[o], X[o]] = C[o]; BR[Y[o], X[o]] = np.maximum(BR[Y[o], X[o]], B[o]); PA[Y[o], X[o]] = Pl[o]
    # reflections in the sea, broken up by the waves
    yr = (H + (H - Y) * 0.5).astype(int)
    xr = (X + np.sin(t * 3 + yr * 1.3) * (1 + (yr - H) * 0.1)).astype(int)
    ok = (yr > H) & (yr < rows) & (xr >= 0) & (xr < cols) & (B > 0.3) & \
        (np.sin(t * 9 + xr * 2.3 + yr * 5.1) > -0.2)
    xr, yr, Br, Plr = xr[ok], yr[ok], B[ok], Pl[ok]
    ok = bg[yr, xr]
    CH[yr[ok], xr[ok]] = ord("-"); BR[yr[ok], xr[ok]] = Br[ok] * 0.4; PA[yr[ok], xr[ok]] = Plr[ok]


def draw_fireflies(sc, t, CH, BR, PA, ZM):
    if t < T_STAR:
        return
    k = float(smooth((t - T_STAR) / 2))
    pos = []
    for fl in sc.palm.flies:
        w, ph = fl["w"], fl["ph"]
        pos.append(fl["c"] + np.array([math.sin(t * w[0] + ph[0]) * 0.9, math.sin(t * w[1] + ph[1]) * 0.6,
                                       math.sin(t * w[2] + ph[2]) * 0.9]))
    Pw = transform(np.array(pos), t)
    sx, sy = sc.project(Pw)
    for i, (x, y, z) in enumerate(zip(sx.astype(int), sy.astype(int), Pw[:, 2])):
        if 0 <= x < sc.cols and 0 <= y < sc.rows and z < ZM[y, x] + 0.1:
            blink = 0.5 + 0.5 * math.sin(t * 2.2 + i * 1.9)
            if blink > 0.3:
                CH[y, x], BR[y, x], PA[y, x] = ord("*" if blink > 0.85 else "."), blink * k, FIREFLY
                sc.glows.append((x, y, FIREFLY, 0.7 * blink * k))


def draw_lights(sc, t, ch, br, pa, zmin):
    """Fairy lights (hidden when behind the trunk or leaves) and the star on top."""
    cols, rows = sc.cols, sc.rows
    palm = sc.palm
    if t < T_LIGHT0 - 0.6:
        return 0, ""
    if sc.mode_pick is not None:
        mode = LIGHT_MODES[sc.mode_pick % len(LIGHT_MODES)]
    else:
        mode = LIGHT_MODES[int(max(0.0, t - T_STAR) // MODE_SECONDS) % len(LIGHT_MODES)]

    pos, items = [], []
    for L in palm.lights:
        if L["kind"] == "trunk":
            if "pos" not in L:                                # the trunk doesn't move: work it out once
                c, side, up, r = trunk_frame(L["s"])
                a = L["ang"]
                L["pos"] = c[0] + (math.cos(a) * side[0] + math.sin(a) * up[0]) * (r[0] + 0.07)
            pos.append(L["pos"])
        else:
            if L["f"] not in palm.rachis:
                continue
            R, upv, g = palm.rachis[L["f"]]
            if g < 0.9:
                continue
            pos.append(R[L["ui"]] - upv[L["ui"]] * 0.09)
        items.append(L)
    if not pos:
        return 0, mode
    Pw = transform(np.array(pos), t)
    sx, sy = sc.project(Pw)
    n_on = 0
    total = len(palm.lights)
    for L, x, y, z in zip(items, sx, sy, Pw[:, 2]):
        x, y = int(x), int(y)
        if not (0 <= x < cols and 0 <= y < rows):
            continue
        j = y * cols + x
        if z > zmin[j] + 0.18:                          # behind the trunk / leaves
            continue
        on = t - L["on"]
        if on < 0:
            ch[j], br[j], pa[j] = ord("."), 0.18, WIRE
            continue
        n_on += 1
        pal = L["pal"]
        k = L["k"] / total
        if t < T_STAR or mode == "twinkle":
            b = 0.72 + 0.28 * math.sin(t * 3.0 + L["ph"])
        elif mode == "chase":
            d = (k - t * 0.45) % 1.0
            b = 0.35 + 0.65 * math.exp(-min(d, 1 - d) ** 2 / 0.0025) + 0.15 * (L["k"] % 5 == int(t * 4) % 5)
        elif mode == "rainbow":
            pal = BULB_COLOURS[int(L["k"] + t * 4) % len(BULB_COLOURS)]
            b = 0.85
        else:                                           # sparkle
            b = 0.35 + (0.65 if math.sin(t * 9 + L["ph"] * 7) > 0.85 else 0.0)
        b = min(1.0, b + max(0.0, 1 - on / 0.2) * 0.6)  # pop when it switches on
        ch[j] = ord("@" if b > 0.9 else "o")
        br[j], pa[j] = b, pal
        sc.glows.append((x, y, pal, b))

    # the star on top of the palm
    if t > T_STAR:
        k = float(smooth((t - T_STAR) / 0.5))
        sp = transform((TOP + np.array([0, 1.35, 0]))[None], t)
        x, y = sc.project(sp)
        x, y = int(x[0]), int(y[0])
        pulse = 0.85 + 0.15 * math.sin(t * 2.4)
        arm = 3 + int(3 * pulse * k)
        sc.glows.append((x, y, GOLD, 2.5 * k))
        pts = [(0, 0, "@", 1.0), (-1, 0, "*", 1.0), (1, 0, "*", 1.0)]
        for d in range(2, arm * 2 + 2):                     # long horizontal rays
            f = 1 - d / (arm * 2 + 3)
            pts += [(-d, 0, "=" if d < 4 else "-", f), (d, 0, "=" if d < 4 else "-", f)]
        for d in range(1, arm + 1):                          # vertical rays
            f = 1 - d / (arm + 1.5)
            pts += [(0, -d, "|", f), (0, d, "|", f * 0.8)]
        for d in range(1, 3):                                # diagonals
            f = 0.85 - d * 0.2
            pts += [(-2 * d, -d, "\\", f), (2 * d, -d, "/", f), (-2 * d, d, "/", f), (2 * d, d, "\\", f)]
        for dx, dy, c, f in pts:
            xx, yy = x + dx, y + dy
            if 0 <= xx < cols and 0 <= yy < rows:
                jj = yy * cols + xx
                ch[jj], br[jj], pa[jj] = ord(c), min(1.0, f * k * pulse + 0.1), GOLD
        # a ring of glitter when it first lights up
        if t - T_STAR < 1.2:
            a = t - T_STAR
            for i in range(24):
                ang = i / 24 * TAU
                xx, yy = int(x + math.cos(ang) * a * 18), int(y + math.sin(ang) * a * 9)
                if 0 <= xx < cols and 0 <= yy < rows:
                    jj = yy * cols + xx
                    ch[jj], br[jj], pa[jj] = ord("+" if i % 2 else "."), 1 - a / 1.2, GOLD
    return n_on, mode


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
        n = 32
        yy, xx = np.mgrid[0:n, 0:n]
        r = np.hypot(xx - n / 2 + 0.5, yy - n / 2 + 0.5) / (n / 2)
        v = np.clip(1 - r, 0, 1) ** 2
        self.halos = {}
        for pal in (RED, GREEN, GOLD, BLUE, PINK, FIREFLY, MOON, WHITE):
            c = PALETTES[pal]
            arr = np.dstack([v * c[0] * 0.6, v * c[1] * 0.6, v * c[2] * 0.6]).astype(np.uint8)
            self.halos[pal] = pygame.surfarray.make_surface(arr.transpose(1, 0, 2))
        self.big = {}

    def glyph(self, code, level, pal):
        key = (code, level, pal)
        g = self.cache.get(key)
        if g is None:
            g = self.font.render(chr(code), True, colour(level, pal))
            self.cache[key] = g
        return g

    def draw(self, screen, ch, br, pa, fade, glows=(), flash=0.0, flash_pal=GOLD):
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
                if l >= 10:
                    hot.append(item)
        blit = (lambda s, q: s.fblits(q)) if hasattr(self.layer, "fblits") else \
               (lambda s, q: s.blits(q, doreturn=False))
        blit(self.layer, seq)
        blit(self.bright, hot)
        screen.fill((0, 0, 0))
        screen.blit(self.layer, (0, 0))
        cw, chh = self.cw, self.ch
        for (x, y, pal, b) in glows:          # each bulb glows its own colour
            if b > 1.2:
                key = (pal, int(b * 4))
                if key not in self.big:
                    sz = int(28 * b)
                    self.big[key] = pygame.transform.smoothscale(self.halos[pal], (sz, sz))
                h_ = self.big[key]
            else:
                h_ = self.halos[pal]
            screen.blit(h_, (x * cw + cw // 2 - h_.get_width() // 2, y * chh + chh // 2 - h_.get_height() // 2),
                        special_flags=pygame.BLEND_ADD)
        if flash > 0.02:                       # the sky lights up with each burst
            c = PALETTES[flash_pal]
            screen.fill((int(c[0] * flash * 0.12), int(c[1] * flash * 0.12), int(c[2] * flash * 0.12)),
                        special_flags=pygame.BLEND_ADD)
        if GLOW > 0:
            s1 = pygame.transform.smoothscale(self.bright, (max(1, w // 5), max(1, h // 5)))
            s2 = pygame.transform.smoothscale(s1, (max(1, w // 14), max(1, h // 14)))
            s1.blit(pygame.transform.smoothscale(s2, s1.get_size()), (0, 0),
                    special_flags=pygame.BLEND_ADD)
            blur = pygame.transform.smoothscale(s1, (w, h))
            for _ in range(max(1, int(GLOW))):
                screen.blit(blur, (0, 0), special_flags=pygame.BLEND_ADD)


def draw_hud(screen, ren, t, letters, phase, fps, lights=0, fired=0):
    w, h = screen.get_size()
    dim, pink = (110, 118, 128), (225, 110, 150)
    f = ren.hud
    lh = f.get_linesize()
    screen.blit(f.render(f"t {t:05.2f}s", True, pink), (w - 100, 8))
    for i, line in enumerate((f"{HANDLE} · 2026", f"lights on {lights} · fireworks {fired}",
                              f"letters {letters:,}", phase)):
        screen.blit(f.render(line, True, dim), (10, h - 26 - (4 - i) * lh))
    pygame.draw.line(screen, (30, 34, 40), (0, h - 22), (w, h - 22))
    screen.blit(f.render("py palm.py", True, dim), (6, h - 19))
    txt = f.render(f"running · {fps:.0f} fps", True, dim)
    screen.blit(txt, (w - txt.get_width() - 8, h - 19))


def main():
    pygame.init()
    pygame.display.set_caption("palm.py")
    screen = pygame.display.set_mode(WINDOW, pygame.RESIZABLE)
    clock = pygame.time.Clock()
    ren = Renderer()

    def new_scene():
        w, h = screen.get_size()
        return Scene(w // ren.cw, (h - 90) // ren.ch, ren.cw / ren.ch), pygame.time.get_ticks()

    sc, start = new_scene()
    full = False
    t = 0.0
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_q)):
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_f:
                for _ in range(5):
                    launch(sc)
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                full = not full
                screen = pygame.display.set_mode((0, 0) if full else WINDOW,
                                                 pygame.FULLSCREEN if full else pygame.RESIZABLE)
                sc, start = new_scene()
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_l:
                cur = sc.mode_pick if sc.mode_pick is not None else \
                    int(max(0.0, t - T_STAR) // MODE_SECONDS)
                sc.mode_pick = cur + 1
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                sc, start = new_scene()
            elif e.type == pygame.VIDEORESIZE and not full:
                screen = pygame.display.set_mode(e.size, pygame.RESIZABLE)
                sc, start = new_scene()
        t = (pygame.time.get_ticks() - start) / 1000
        ch, br, pa, phase, lights = build_frame(sc, t)
        ren.draw(screen, ch, br, pa, min(1.0, t / 0.8 + 0.2), sc.glows, sc.flash, sc.flash_pal)
        draw_hud(screen, ren, t, int((ch != 0).sum()), phase, clock.get_fps(), lights, sc.fired)
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()