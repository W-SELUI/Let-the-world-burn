"""
EYE OF GOD
A dark, cinematic, realistic-style eye animation in Python (pygame + numpy).

  1. Darkness ........ pitch black, a faint red heartbeat in the void
  2. The eye opens ... glowing iris in the dark, lids flutter, light slowly rises
  3. It looks around . the eye scans the room, blinks — code rain falls in the dark behind it
  4. It finds YOU .... snaps to centre, pupil contracts, iris blazes
  5. Zoom ............ we fall into the pupil
  6. Event horizon ... inside the pupil: a black hole. We fall in... darkness... and it begins again.
     (set GALAXY_ENDING = True for the longer ending below)
  7. Singularity ..... darkness, one point of light beating like a heart... big bang
  8. Warp ............ streaking through stars toward a distant galaxy
  9. Reveal .......... a 3D galaxy of 100,000+ stars, gas and dust, camera orbits it
 10. Dive ............ into the blazing core, anamorphic lens flare
 11. Infinity ........ the universe becomes the eye... it closes... and it begins again

Install:  pip install pygame numpy
Run:      python eye_of_god.py
Record:   python eye_of_god.py --record    (saves HD frames to ./frames for a video)

Controls: F = fullscreen,  A = ASCII look on/off,  H = HUD on/off,  R = restart,  ESC = quit
"""

import math
import os
import sys
import time

import numpy as np
import pygame

# ----------------------------------------------------------------------------
# SETTINGS
# ----------------------------------------------------------------------------
WINDOW = (1280, 720)
RENDER = (480, 270)          # internal resolution (raise for detail if your PC is fast)
RECORD_RENDER = (960, 540)   # internal resolution used with --record
FPS = 30
LOOP = True

# timeline (seconds)
T_DARK  = 3.0    # end of darkness
T_OPEN  = 8.0    # eye fully open
T_LOOK  = 16.0   # end of looking around
T_STARE = 19.0   # end of the stare
T_ZOOM  = 23.0   # end of zoom (inside the pupil)
T_SING  = 29.0   # we cross the event horizon: the singularity
T_BANG  = 31.6   # the flash: big bang
T_WARP  = 36.0   # end of the big bang flight, galaxy revealed
T_ORBIT = 45.0   # end of the slow orbit
T_DIVE  = 49.0   # end of the dive into the core
T_CLOSE = 53.5   # the cosmic eye has closed

# False: the film ends as we cross the event horizon -> darkness -> the heartbeat -> the eye opens again
# True:  continue through the singularity, big bang and galaxy (the longer purple ending)
GALAXY_ENDING = False
T_TOTAL = 54.5 if GALAXY_ENDING else T_SING + 1.2

# ASCII look: the final picture is rebuilt from tiny coloured characters
ASCII = True          # press A to toggle
ASCII_CELL = (4, 7)   # character size in pixels (smaller = subtler)
ASCII_MIX = 0.7       # 1.0 = pure characters, 0.0 = smooth image
ASCII_CHARS = " .'`,:;-~=+*<>/\\|!?ilI1tfjrxnuvczXYUJCLQ0OZmwqpdbkhao#MW&8%B@$"
HUD = True            # chapter title + status bar (press H to toggle)

LETTERBOX = True   # cinematic black bars (2.39 : 1)

# code rain in the background (eye scenes only)
RAIN = False                    # matrix-style code rain behind the eye
RAIN_DENSITY = 0.65             # fraction of columns with a falling stream
RAIN_HEAD  = (235, 242, 255)   # bright white head of each stream
RAIN_TRAIL = (90, 130, 210)    # faint blue tail
RAIN_CHARS = "0123456789ABCDEF{}[]<>/\\|;:=+-*$#&%@!?"

# look-around path: (time, x, y) as fractions of how far the eye can turn
GAZE_PATH = [
    (8.0, 0.0, 0.0), (8.5, -1.0, 0.15), (9.8, -1.0, 0.15),
    (10.15, 0.95, -0.25), (11.4, 0.95, -0.25), (11.7, 0.25, 0.75),
    (12.7, 0.25, 0.75), (13.5, -0.55, -0.6), (14.4, -0.55, -0.6),
    (14.7, 0.7, 0.2), (15.6, 0.7, 0.2), (15.9, 0.0, 0.0),
]
BLINK = (13.0, 13.35)

# eye geometry (screen height = 2 units)
A, BU, BL = 0.98, 0.50, 0.36     # half width, upper lid height, lower lid depth
RE = 0.98                        # eyeball radius
RI = 0.36                        # iris radius

# colours
IRIS_INNER = np.array([1.00, 0.64, 0.20], np.float32)   # molten gold
IRIS_OUTER = np.array([0.55, 0.22, 0.06], np.float32)   # dark amber
GLOW_COL   = np.array([1.00, 0.50, 0.12], np.float32)
SCLERA     = np.array([0.64, 0.58, 0.56], np.float32)
SKIN       = np.array([0.36, 0.22, 0.16], np.float32)
VEIN       = np.array([0.55, 0.06, 0.07], np.float32)

f32 = np.float32


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
GAL_SPIN = 0.05   # galaxy rotation speed
GAL_BRIGHT = 0.16 # brightness of the galaxy's stars

def warp_speed(t):
    """How fast we fly through the stars after the big bang."""
    if t < T_BANG:
        return 0.0
    if t < T_BANG + 0.6:
        return 34.0 * ease(seg(t, T_BANG, T_BANG + 0.6))
    if t < T_BANG + 1.8:
        return 34.0
    return 34.0 * (1 - ease(seg(t, T_BANG + 1.8, T_WARP + 1.0)))

def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v

def seg(t, a, b):
    return clamp((t - a) / (b - a))

def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)

def lerp(a, b, k):
    return a + (b - a) * k

def sstep(e0, e1, x):
    k = np.clip((x - e0) / (e1 - e0), 0, 1)
    return k * k * (3 - 2 * k)

def tile_noise(size, grids, rng):
    """Tileable smooth fractal noise texture in 0..1."""
    out = np.zeros((size, size), f32)
    amp, total = 1.0, 0.0
    for g in grids:
        grid = rng.random((g, g)).astype(f32)
        c = np.arange(size) * g / size
        i0 = np.floor(c).astype(int)
        fr = (c - i0).astype(f32)
        fr = fr * fr * (3 - 2 * fr)
        i1 = (i0 + 1) % g
        g00, g01 = grid[np.ix_(i0, i0)], grid[np.ix_(i0, i1)]
        g10, g11 = grid[np.ix_(i1, i0)], grid[np.ix_(i1, i1)]
        fx, fy = fr[None, :], fr[:, None]
        layer = (g00 * (1 - fx) + g01 * fx) * (1 - fy) + (g10 * (1 - fx) + g11 * fx) * fy
        out += amp * layer
        total += amp
        amp *= 0.55
    out /= total
    out = (out - out.min()) / (out.max() - out.min())
    return out

def sample(tex, u, v):
    n = tex.shape[0]
    iu = (u * n).astype(np.int32) % n
    iv = (v * n).astype(np.int32) % n
    return tex[iv, iu]


# ----------------------------------------------------------------------------
# what is happening at time t
# ----------------------------------------------------------------------------
class State:
    pass

def state_at(t):
    S = State()
    S.t = t

    # eyelids
    if t < T_DARK:
        op = 0.0
    elif t < 4.2:
        op = 0.22 * ease(seg(t, T_DARK, 4.2))
    elif t < 4.8:
        op = lerp(0.22, 0.06, ease(seg(t, 4.2, 4.8)))
    else:
        op = lerp(0.06, 1.0, ease(seg(t, 4.8, T_OPEN)))
    if t > T_LOOK:                                   # eyes widen when it finds you
        op = lerp(op, 1.08, ease(seg(t, T_LOOK, T_LOOK + 0.4)))
    if BLINK[0] < t < BLINK[1]:
        op *= 1 - math.sin(math.pi * seg(t, *BLINK)) ** 0.7
    S.open = op

    # scene light (the room slowly reveals itself)
    S.light = ease(seg(t, 4.5, 8.5))

    # gaze
    gx = gy = 0.0
    if GAZE_PATH[0][0] <= t <= GAZE_PATH[-1][0]:
        for (t0, x0, y0), (t1, x1, y1) in zip(GAZE_PATH, GAZE_PATH[1:]):
            if t0 <= t <= t1:
                k = ease(seg(t, t0, t1))
                gx, gy = lerp(x0, x1, k), lerp(y0, y1, k)
                break
    if t < T_LOOK:                                   # tiny living tremor
        gx += 0.012 * math.sin(t * 17) + 0.008 * math.sin(t * 29)
        gy += 0.010 * math.sin(t * 23 + 1)
    S.gx, S.gy = gx * 0.40, gy * 0.15

    # pupil, glow, portal
    rp = 0.125 + 0.006 * math.sin(t * 1.3)
    emit = 0.45 if t < T_OPEN else 0.3 + 0.05 * math.sin(t * 2.0)
    portal = 0.0
    if t >= T_LOOK:
        k = ease(seg(t, T_LOOK, T_LOOK + 0.3))
        rp = lerp(rp, 0.085, k)
        emit = lerp(emit, 1.7, ease(seg(t, T_LOOK, T_LOOK + 0.8)))
        emit *= 1 + 0.15 * math.sin(t * 6)
        portal = 0.3 * ease(seg(t, 17.0, T_STARE))
    if t >= T_STARE:
        p = seg(t, T_STARE, T_ZOOM)
        rp = lerp(0.085, 0.17, ease(p))
        portal = lerp(0.3, 1.0, ease(p))
    S.rp, S.emit, S.portal = rp, emit, portal

    S.zoom = 1.0
    if t >= T_STARE:
        S.zoom = math.exp(math.log(32.0) * seg(t, T_STARE, T_ZOOM) ** 2.4)
    return S


# ----------------------------------------------------------------------------
# the renderer
# ----------------------------------------------------------------------------
class Scene:
    def __init__(self, w, h):
        self.w, self.h = w, h
        rng = np.random.default_rng(7)
        cols = (np.arange(w, dtype=f32) - w / 2 + 0.5) / (h / 2)
        rows = -(np.arange(h, dtype=f32) - h / 2 + 0.5) / (h / 2)
        self.X, self.Y = np.meshgrid(cols, rows)
        self.pix = f32(2.0 / h * 1.3)

        self.noise = tile_noise(512, [4, 8, 16, 32, 64], rng)
        self.noise_fine = tile_noise(512, [32, 64, 128, 256], rng)

        # iris fibres: many sine layers around the circle
        self.fibers = [(n, rng.uniform(0, 6.28), rng.uniform(-3, 3), 1.0 / (1 + i * 0.35))
                       for i, n in enumerate([13, 23, 37, 59, 89, 131, 197, 263, 347])]

        # star field
        self.stars = np.zeros((h, w, 3), f32)
        count = int(w * h * 0.004)
        sy, sx = rng.integers(0, h, count), rng.integers(0, w, count)
        mag = rng.random(count).astype(f32) ** 6 * 2.2 + 0.08
        tints = np.array([[1, 1, 1], [0.7, 0.8, 1.0], [1.0, 0.85, 0.65]], f32)
        self.stars[sy, sx] = mag[:, None] * tints[rng.integers(0, 3, count)]
        self.star_ph = rng.uniform(0, 6.28, (h, w)).astype(f32)
        self.star_sp = rng.uniform(1, 4, (h, w)).astype(f32)
        self.row_idx = np.arange(h)[:, None] * np.ones((1, w), int)
        self.col_idx = np.ones((h, 1), int) * np.arange(w)[None, :]

        r2 = self.X ** 2 / (self.X.max() ** 2) + self.Y ** 2
        self.vignette = (np.clip(1.1 - 0.62 * r2, 0, 1) ** 1.6).astype(f32)[..., None]
        bar = (1 - w / 2.39 / h) / 2 * h if LETTERBOX else 0
        self.bars = int(round(bar))
        self.grain = [rng.normal(0, 0.018, (h, w, 1)).astype(f32) for _ in range(6)]
        self._static = None
        self.rain_mask = None
        self.init_universe(rng)

    # ---------------------------------------------------------------- universe setup
    def init_universe(self, rng):
        # --- galaxy stars (3D particles) ---
        na, nd, nb = 70000, 22000, 16000
        r = 0.06 + rng.exponential(0.38, na)
        k = rng.integers(0, 2, na)
        th = (4.2 * np.log(r) + 2 * np.pi * k + rng.normal(0, 0.55, na)) / 2
        arm = np.stack([r, th, rng.normal(0, 0.018, na)], 1)
        rd = rng.exponential(0.42, nd) + 0.03
        disc = np.stack([rd, rng.uniform(0, 2 * np.pi, nd), rng.normal(0, 0.03, nd)], 1)
        bp = rng.normal(0, 1, (nb, 3)) * np.array([0.11, 0.11, 0.07])
        bulge = np.stack([np.hypot(bp[:, 0], bp[:, 1]), np.arctan2(bp[:, 1], bp[:, 0]), bp[:, 2]], 1)
        P = np.concatenate([arm, disc, bulge]).astype(f32)
        self.g_r, self.g_th, self.g_h = P[:, 0], P[:, 1], P[:, 2]
        n = len(P)
        mag = (rng.lognormal(0, 0.9, n) * 0.5).astype(f32)
        palette_arm = np.array([[0.45, 0.6, 1.0], [0.85, 0.88, 1.0], [0.6, 0.45, 1.0], [1.0, 0.35, 0.65]], f32)
        pick = rng.choice(4, na + nd, p=[0.4, 0.3, 0.24, 0.06])
        col = np.concatenate([palette_arm[pick],
                              np.tile(np.array([[1.0, 0.78, 0.5]], f32) * 0.45, (nb, 1))])
        self.g_col = col * mag[:, None]

        # --- distant background stars (directions) ---
        m = 7000
        d = rng.normal(0, 1, (m, 3))
        self.bg_dir = (d / np.linalg.norm(d, axis=1, keepdims=True)).astype(f32)
        tint = np.array([[1, 1, 1], [0.7, 0.8, 1.0], [1.0, 0.8, 0.6]], f32)[rng.integers(0, 3, m)]
        self.bg_col = tint * (rng.random(m) ** 8 * 2.5 + 0.05).astype(f32)[:, None]
        self.bg_ph = rng.uniform(0, 6.28, m).astype(f32)

        # --- warp stars (camera space) ---
        q = 2500
        self.w_x = rng.uniform(-2.5, 2.5, q).astype(f32)
        self.w_y = rng.uniform(-2.5, 2.5, q).astype(f32)
        self.w_z = rng.uniform(0, 30, q).astype(f32)
        self.w_c = (rng.random(q) * 0.8 + 0.4).astype(f32)

        # distance travelled during the warp (integral of speed)
        ts = np.arange(0, T_TOTAL + 1, 0.01)
        sp = np.array([warp_speed(x) for x in ts])
        self.warp_t, self.warp_s = ts, np.cumsum(sp) * 0.01

        # half resolution grid for the smooth gas
        self.X2, self.Y2 = self.X[::2, ::2], self.Y[::2, ::2]

    def splat(self, col, row, rgb, bilinear=True):
        """Draw points (bilinear = smooth sub-pixel motion, else nearest pixel)."""
        h, w = self.h, self.w
        if not bilinear:
            c, r = (col + 0.5).astype(np.int32), (row + 0.5).astype(np.int32)
            ok = (c >= 0) & (c < w) & (r >= 0) & (r < h)
            idx = (r * w + c)[ok]
            out = np.empty((h * w, 3), f32)
            for ch in range(3):
                out[:, ch] = np.bincount(idx, weights=rgb[ok, ch], minlength=h * w)
            return out.reshape(h, w, 3)
        c0, r0 = np.floor(col).astype(np.int32), np.floor(row).astype(np.int32)
        fx, fy = (col - c0).astype(f32), (row - r0).astype(f32)
        idx, wt = [], []
        for dc, dr, ww in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                           (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
            cc, rr = c0 + dc, r0 + dr
            ok = (cc >= 0) & (cc < w) & (rr >= 0) & (rr < h)
            idx.append((rr * w + cc)[ok])
            wt.append((ww[ok, None] * rgb[ok]))
        idx = np.concatenate(idx)
        wt = np.concatenate(wt)
        out = np.empty((h * w, 3), f32)
        for ch in range(3):
            out[:, ch] = np.bincount(idx, weights=wt[:, ch], minlength=h * w)
        return out.reshape(h, w, 3)

    def project(self, P, cam):
        C, R, U, Fw, F, roll = cam
        d = P - C
        xc, yc, zc = d @ R, d @ U, d @ Fw
        ok = zc > 0.02
        xc, yc, zc = xc[ok], yc[ok], zc[ok]
        sx, sy = F * xc / zc, F * yc / zc
        cr, sr = math.cos(roll), math.sin(roll)
        sx, sy = sx * cr - sy * sr, sx * sr + sy * cr
        return sx * (self.h / 2) + self.w / 2 - 0.5, -sy * (self.h / 2) + self.h / 2 - 0.5, zc, ok

    def gas(self, X, Y, cam, t):
        """Glowing gas, dust lanes and the volumetric core, by ray-tracing the galaxy plane."""
        C, R, U, Fw, F, roll = cam
        cr, sr = math.cos(-roll), math.sin(-roll)
        X, Y = X * cr - Y * sr, X * sr + Y * cr
        dx = Fw[0] * F + R[0] * X + U[0] * Y
        dy = Fw[1] * F + R[1] * X + U[1] * Y
        dz = Fw[2] * F + R[2] * X + U[2] * Y
        inv = 1 / np.sqrt(dx * dx + dy * dy + dz * dz)
        dx, dy, dz = dx * inv, dy * inv, dz * inv

        # volumetric core glow: how close each ray passes to the centre
        tc = np.maximum(-(C[0] * dx + C[1] * dy + C[2] * dz), 0)
        bx, by, bz = C[0] + tc * dx, C[1] + tc * dy, C[2] + tc * dz
        b2 = bx * bx + by * by + bz * bz
        core = np.exp(-b2 / 0.0035) * 2.2 + np.exp(-np.sqrt(b2) / 0.07) * 0.45

        # hit the disc plane (y = 0)
        th_ = -C[1] / np.where(np.abs(dy) < 1e-4, -1e-4, dy)
        hit = th_ > 0
        pu, pv = C[0] + th_ * dx, C[2] + th_ * dz
        r = np.sqrt(pu * pu + pv * pv) + f32(1e-4)
        ang = np.arctan2(pv, pu) - f32(t * GAL_SPIN)
        cu, cv = r * np.cos(ang), r * np.sin(ang)
        n1 = sample(self.noise, cu * 1.6 + 0.5, cv * 1.6 + 0.5)
        n2 = sample(self.noise, cu * 3.5 + 0.2, cv * 3.5 + 0.7)
        n3 = sample(self.noise_fine, cu * 5 + 0.1, cv * 5 + 0.3)
        phase = 2 * ang - 4.2 * np.log(r) + 1.6 * (n1 - 0.5)
        arm = (0.5 + 0.5 * np.cos(phase)) ** 3
        dust = (0.5 + 0.5 * np.cos(phase + 0.8)) ** 6
        fall = np.exp(-r * 2.3) * hit
        slant = np.minimum(1 / np.maximum(np.abs(dy), 0.05), 6) * 0.2
        armd = arm * fall * (0.3 + 1.2 * n2) * sstep(0.03, 0.25, r) * slant
        dustd = np.clip(dust * 1.7 * n2 * sstep(0.05, 0.3, r) * np.exp(-r * 1.1) * hit * np.minimum(slant * 2, 1), 0, 0.9)
        hii = np.clip((n3 - 0.72) * 6, 0, 1) * arm * fall * slant * 3.0
        armcol = (np.array([0.22, 0.32, 0.85], f32) * (1 - n1[..., None]) +
                  np.array([0.55, 0.22, 0.85], f32) * n1[..., None])
        col = (armd[..., None] * armcol * 3.2 +
               hii[..., None] * np.array([1.0, 0.25, 0.5], f32) +
               core[..., None] * np.array([1.0, 0.80, 0.55], f32))
        return col, dustd

    def camera(self, t):
        if t < T_WARP:
            p = seg(t, T_BANG, T_WARP)
            D = lerp(16.0, 2.7, 1 - (1 - p) ** 2.5)
            el = 0.38
        elif t < T_ORBIT:
            p = ease(seg(t, T_WARP, T_ORBIT))
            D, el = lerp(2.7, 1.8, p), lerp(0.38, 0.8, p)
        elif t < T_DIVE:
            p = ease(seg(t, T_ORBIT, T_DIVE))
            D, el = lerp(1.8, 0.75, p), lerp(0.8, 1.45, p)
        else:
            p = seg(t, T_DIVE, T_TOTAL)
            D, el = lerp(0.75, 0.62, p), 1.45
        az = 0.4 + 0.045 * (t - T_BANG)
        C = np.array([D * math.cos(el) * math.sin(az), D * math.sin(el), D * math.cos(el) * math.cos(az)], f32)
        Fw = -C / np.linalg.norm(C)
        up = np.array([0, 1, 0], f32) if el < 1.4 else np.array([-math.sin(az), 0, -math.cos(az)], f32)
        R = np.cross(Fw, up)
        R /= np.linalg.norm(R)
        U = np.cross(R, Fw)
        roll = 0.06 * math.sin(t * 0.17) + 0.04
        return C, R.astype(f32), U.astype(f32), Fw.astype(f32), 2.1, roll

    def universe(self, t, sl=None):
        h, w = self.h, self.w
        if sl is not None and (sl[0].stop - sl[0].start) * (sl[1].stop - sl[1].start) > h * w * 0.3:
            sl = None
        cam = self.camera(t)
        C, R, U, Fw, F, roll = cam

        # gas: full frame at half resolution, or full res inside a small window
        if sl is None:
            g, dust = self.gas(self.X2, self.Y2, cam, t)
            g = np.repeat(np.repeat(g, 2, 0), 2, 1)[:h, :w]
            dust = np.repeat(np.repeat(dust, 2, 0), 2, 1)[:h, :w]
            g = (g + np.roll(g, 1, 0) + np.roll(g, 1, 1) + np.roll(np.roll(g, 1, 0), 1, 1)) * 0.25
            img = g
        else:
            img = np.zeros((h, w, 3), f32)
            dust = np.zeros((h, w), f32)
            img[sl], dust[sl] = self.gas(self.X[sl], self.Y[sl], cam, t)

        # galaxy stars
        ang = self.g_th + f32(t * GAL_SPIN)
        P = np.stack([self.g_r * np.cos(ang), self.g_h, self.g_r * np.sin(ang)], 1)
        col, row, zc, ok = self.project(P, cam)
        gk = f32(ease(seg(t, T_BANG + 1.0, T_BANG + 4.0)))       # galaxy is born after the bang
        img *= gk
        stars = self.splat(col, row, self.g_col[ok] * (GAL_BRIGHT * gk / zc ** 1.2)[:, None], bilinear=False)

        # background stars (infinitely far: rotation only)
        d = self.bg_dir
        zc = d @ Fw
        ok = zc > 0.05
        sx, sy = F * (d[ok] @ R) / zc[ok], F * (d[ok] @ U) / zc[ok]
        cr, sr = math.cos(roll), math.sin(roll)
        sx, sy = sx * cr - sy * sr, sx * sr + sy * cr
        tw = (0.65 + 0.35 * np.sin(t * 2.3 + self.bg_ph[ok])) * ease(seg(t, T_BANG + 0.4, T_BANG + 2.5))
        stars += self.splat(sx * (h / 2) + w / 2, -sy * (h / 2) + h / 2, self.bg_col[ok] * tw[:, None])

        # warp stars with motion streaks
        v = warp_speed(t)
        if v > 0.05:
            s = float(np.interp(t, self.warp_t, self.warp_s))
            z = (self.w_z - s) % 30 + 0.2
            streak = min(v * 0.03, 1.5)
            cols, rows, cs = [], [], []
            for k in range(8):
                zk = z + streak * k / 7
                cols.append(F * self.w_x / zk * (h / 2) + w / 2)
                rows.append(-F * self.w_y / zk * (h / 2) + h / 2)
                b = self.w_c * np.clip(1 - z / 30, 0, 1) ** 2 * clamp(v / 6) * (1 - k / 8) * 0.5
                cs.append(b[:, None] * np.array([0.75, 0.85, 1.0], f32))
            stars += self.splat(np.concatenate(cols), np.concatenate(rows), np.concatenate(cs))

        img = img + stars

        # nebula clouds with a little parallax
        az, el = math.atan2(C[0], C[2]), math.asin(C[1] / np.linalg.norm(C))
        neb = sample(self.noise, self.X * 0.2 + 0.3 + az * 0.12, self.Y * 0.2 + 0.1 - el * 0.12) ** 3
        neb2 = sample(self.noise, self.X * 0.33 + 0.7 + az * 0.2, self.Y * 0.33 + 0.5 - el * 0.2) ** 4
        img += neb[..., None] * np.array([0.11, 0.03, 0.17], f32)
        img += neb2[..., None] * np.array([0.02, 0.07, 0.10], f32)
        img *= (1 - dust)[..., None]

        # the big bang: blinding flash, expanding shockwave, rays of light
        if t < T_BANG + 4.0:
            dt = t - T_BANG
            r = np.sqrt(self.X ** 2 + self.Y ** 2) + f32(1e-4)
            th = np.arctan2(self.Y, self.X)
            R = 3.0 * max(dt, 0) ** 0.6
            fade = 1 - ease(seg(t, T_BANG, T_BANG + 3.5))
            shock = np.exp(-((r - R) / (0.03 + 0.06 * R)) ** 2) * fade * 1.0
            core = np.exp(-(r / (0.03 + 0.1 * R)) ** 2) * fade * 1.6
            rays = sample(self.noise_fine, th * f32(1.27) + 3.0, np.log(r) * 0.25 - dt * 0.5) ** 7 * 9
            rays *= np.exp(-r / (0.3 + R)) * fade
            img += shock[..., None] * np.array([1.0, 0.62, 0.32], f32)
            img += core[..., None] * np.array([1.0, 0.9, 0.75], f32)
            img += rays[..., None] * np.array([0.7, 0.8, 1.0], f32)
            img += f32(4.0 * math.exp(-max(dt, 0) / 0.1))          # the flash itself

        # anamorphic lens flare on the core
        cc, rr, zc, ok = self.project(np.zeros((1, 3), f32), cam)
        if ok[0]:
            fx = (cc[0] + 0.5 - w / 2) / (h / 2)
            fy = -(rr[0] + 0.5 - h / 2) / (h / 2)
            fl = (0.35 + 0.9 * ease(seg(t, T_ORBIT, T_DIVE))) * (1 - ease(seg(t, T_DIVE, T_DIVE + 1.5)))
            dyy, dxx = np.abs(self.Y - fy), np.abs(self.X - fx)
            streak = np.exp(-dyy / 0.006) * np.exp(-dxx / 0.9)
            halo = np.exp(-(dxx ** 2 + dyy ** 2) / 0.02)
            img += (streak * fl * 0.6)[..., None] * np.array([0.35, 0.55, 1.0], f32)
            img += (halo * fl * 0.25)[..., None] * np.array([1.0, 0.75, 0.5], f32)
        else:
            fx = fy = 0.0

        # infinity: the universe becomes the eye
        if t > T_DIVE:
            kf = ease(seg(t, T_DIVE, T_DIVE + 2.0))
            op = 1 - ease(seg(t, T_DIVE + 3.0, T_CLOSE))
            ex, ey = self.X - fx, self.Y - fy
            rr_ = np.sqrt(ex * ex + ey * ey)
            th = np.arctan2(ey, ex)
            rp, ri = 0.13, 0.46
            pm = sstep(rp + 0.03, rp - 0.03, rr_)
            img *= (1 - 0.98 * pm * kf)[..., None]
            ring = sstep(rp, rp + 0.06, rr_) * sstep(ri + 0.03, ri - 0.06, rr_)
            fib = np.zeros_like(rr_)
            for n, ph, tw, amp in self.fibers[:6]:
                fib += amp * np.sin(th * n + ph + tw * rr_ * 3)
            fib = (0.5 + 0.25 * fib / 2.6) ** 2
            img += (ring * fib * kf * 1.6)[..., None] * GLOW_COL
            u = ex / 1.5
            base = np.clip(1 - u * u, 0, None)
            up = (0.62 * base ** 0.85) * op - 0.01
            lo = -0.45 * base ** 1.15
            lid = sstep(up + 0.12, up - 0.06, ey) * sstep(lo - 0.12, lo + 0.06, ey) * (base > 0)
            img *= (1 - kf + kf * lid)[..., None]
        return img

    # ---------------------------------------------------------------- black hole + singularity
    def disk(self, rd, phi, t, rs):
        """Accretion disk emission at disk radius rd and angle phi."""
        rin, rout = 1.5 * rs, 6.0 * rs
        m = sstep(rin * 0.95, rin * 1.12, rd) * sstep(rout, rout * 0.55, rd)
        w = 1.4 * (np.maximum(rd, rin) / rs) ** -1.5                  # inner gas orbits faster
        ang = phi + f32(t) * w
        n = sample(self.noise, np.log(np.maximum(rd, 1e-3)) * 2.2 + 0.3, ang * f32(3 / (2 * np.pi)))
        n2 = sample(self.noise_fine, np.log(np.maximum(rd, 1e-3)) * 5.0, ang * f32(6 / (2 * np.pi)) + 0.4)
        streak = 0.3 + 1.3 * n * n + 0.15 * n2
        temp = np.clip((rd - rin) / (rout - rin), 0, 1)
        bright = m * streak * (rs / np.maximum(rd, rin)) ** 1.4 * 1.9
        bright *= 1 - 0.55 * np.cos(phi)                              # doppler: one side brighter
        col = np.stack([np.interp(temp, [0, 0.25, 1], [1.0, 1.0, 0.55]),
                        np.interp(temp, [0, 0.25, 1], [0.92, 0.55, 0.10]),
                        np.interp(temp, [0, 0.25, 1], [0.80, 0.18, 0.04])], -1).astype(f32)
        return bright, col

    def creation(self, t):
        """Inside the pupil: a black hole, the fall, then the singularity. (cached per frame)"""
        if getattr(self, "_cre_t", None) == t:
            return self._cre_img
        X, Y = self.X, self.Y
        h, w = self.h, self.w

        if t < T_SING:
            # camera: drift toward it, then get pulled in
            s = lerp(0.7, 1.15, ease(seg(t, T_STARE, 26.0)))
            s *= math.exp(math.log(16.0) * seg(t, 26.0, T_SING) ** 2.3)
            roll = 0.12 + 0.25 * seg(t, 26.0, T_SING) ** 2
            cr, sr = math.cos(roll), math.sin(roll)
            x = (X * cr - Y * sr) / f32(s)
            y = (X * sr + Y * cr) / f32(s)
            rs = 0.2
            rho = np.sqrt(x * x + y * y) + f32(1e-5)
            th = np.arctan2(y, x)
            outside = sstep(rs * 0.97, rs * 1.03, rho)

            # the disk seen almost edge-on
            incl = 0.17
            yd = y / f32(incl)
            rd = np.sqrt(x * x + yd * yd)
            phi = np.arctan2(yd, x)
            db, dcol = self.disk(rd, phi, t, rs)
            front = (yd < 0).astype(f32)                              # near side passes in front
            db = db * (outside + (1 - outside) * front)

            # light from the far side, bent over and under the shadow
            rl = rs * 1.5 + (rho - rs * 1.03) * 2.4
            lb, lcol = self.disk(rl, -th * 0.5 + 1.0, t, rs)
            arc = np.abs(np.sin(th)) ** 0.7 * np.where(y > 0, 1.0, 0.55)
            lb = lb * arc * outside * sstep(rs * 1.02, rs * 1.1, rho) * sstep(rs * 2.4, rs * 1.5, rho) * 1.8

            ring = np.exp(-((rho - rs * 1.04) / (0.010 + 0.004 / s)) ** 2) * 1.3 * outside

            # background stars bent around it
            defl = np.minimum(rs * rs / rho, rho * 0.98)
            k = (rho - defl) / rho
            ci = np.clip((X * k * (h / 2) + w / 2).astype(int), 0, w - 1)
            ri = np.clip((-Y * k * (h / 2) + h / 2).astype(int), 0, h - 1)
            stars = self.stars[ri, ci] * 0.5 * outside[..., None]

            img = (stars + db[..., None] * dcol + lb[..., None] * lcol +
                   ring[..., None] * np.array([1.0, 0.85, 0.7], f32))
            # faint anamorphic streak across the disk
            img += (np.exp(-np.abs(Y) / 0.01) * np.exp(-np.abs(X) / 1.4) * 0.12)[..., None] * np.array([1.0, 0.6, 0.35], f32)
            # everything goes dark as we cross the horizon
            img *= f32(1 - ease(seg(t, T_SING - 0.6, T_SING)))
        else:
            # the singularity: a single point of light, beating like a heart
            dt = t - T_SING
            r = np.sqrt(X * X + Y * Y) + f32(1e-4)
            th = np.arctan2(Y, X)
            hb = dt % 0.95
            beat = math.exp(-((hb - 0.15) / 0.06) ** 2) + 0.6 * math.exp(-((hb - 0.40) / 0.06) ** 2)
            grow = 1 + 2.5 * seg(t, T_SING, T_BANG)
            k = ease(seg(dt, 0.2, 0.8))
            point = (np.exp(-(r / (0.008 * grow * (1 + 0.7 * beat))) ** 2) * 3.0 * (0.4 + beat) +
                     np.exp(-r / (0.06 * grow)) * 0.4 * (0.3 + beat))
            point += np.exp(-np.abs(Y) / 0.006) * np.exp(-np.abs(X) / (0.4 * grow)) * 0.5 * (0.3 + beat)  # lens streak
            inflow = sample(self.noise_fine, th * f32(4 / (2 * np.pi)) + np.log(r) * 0.9 + dt * 0.2,
                            np.log(r) * 0.5 + dt * 1.1) ** 5 * 7
            inflow *= np.exp(-r * 1.4) * sstep(0.01, 0.08, r) * ease(seg(dt, 0.3, 1.8)) * 0.5
            img = (point[..., None] * np.array([1.0, 0.92, 0.8], f32) +
                   inflow[..., None] * np.array([1.0, 0.75, 0.45], f32)) * f32(k)
            img = img + f32(4.0 * ease(seg(t, T_BANG - 0.25, T_BANG)) ** 2)    # white-out: big bang

        self._cre_t, self._cre_img = t, img
        return img

    # ---------------------------------------------------------------- eye
    def box(self, cx, cy, rad):
        """Pixel slice covering a circle given in screen units."""
        h, w = self.h, self.w
        c0 = int((cx - rad) * h / 2 + w / 2) - 1
        c1 = int((cx + rad) * h / 2 + w / 2) + 2
        r0 = int(-(cy + rad) * h / 2 + h / 2) - 1
        r1 = int(-(cy - rad) * h / 2 + h / 2) + 2
        c0, c1 = max(0, c0), min(w, c1)
        r0, r1 = max(0, r0), min(h, r1)
        if c1 <= c0 or r1 <= r0:
            return None
        return (slice(r0, r1), slice(c0, c1))

    def eye_static(self, z):
        """Everything that does not change while the eye blinks/looks around."""
        if z == 1.0 and self._static is not None:
            return self._static
        x, y = self.X / f32(z), self.Y / f32(z)
        D = State()
        D.x, D.y = x, y
        u = x / A
        base = np.clip(1 - u * u, 0, None)
        D.u, D.base = u, base
        D.up_full = BU * base ** 0.85 + 0.035 * u + 0.02
        D.lo_full = lo = -BL * base ** 1.15 + 0.03 * u - 0.03

        # skin
        tex = sample(self.noise_fine, x * 2.0, y * 2.0)
        tex2 = sample(self.noise, x * 0.5 + 0.3, y * 0.5)
        crease = np.exp(-((y - (D.up_full + 0.10 * base + 0.06)) / 0.03) ** 2) * np.sqrt(base)
        under = np.exp(-((y - (lo - 0.09)) / 0.07) ** 2) * base
        topl = 0.35 + 0.65 * np.clip(0.55 + 0.45 * y, 0, 1)
        D.sk = (0.7 + 0.3 * tex2) * (0.85 + 0.15 * tex) * topl * (1 - 0.55 * crease) * (1 - 0.35 * under)
        D.cdist = np.sqrt((np.abs(x) - A) ** 2 + y ** 2)

        # lower lid: lashes, wet margin, glossy line
        dll = lo - y
        lll = 0.04 * base
        sl_ = np.clip(dll / (lll + 1e-4), 0, 1)
        zl = (dll > 0.012) & (dll < lll + 0.012) & (base > 0.05)
        D.lashl = np.clip((np.cos(x * 150 + sl_ * u * 5) - 0.93) / 0.04, 0, 1) * zl * (1 - sl_) * 0.8
        D.margin = ((dll > 0) & (dll < 0.014) & (base > 0)).astype(f32)[..., None]
        D.wet = np.exp(-((y - (lo + 0.008)) / 0.005) ** 2) * base * 0.35
        D.low_sh = 0.4 + 0.6 * np.clip((y - lo) / 0.06, 0, 1)

        # eyeball
        ey = y + 0.02
        r2 = (x * x + ey * ey) / (RE * RE)
        nz = np.sqrt(np.clip(1 - r2, 0, 1))
        D.shade = 0.10 + 0.90 * nz ** 1.2
        pinkk = sstep(0.6, 1.0, np.abs(u))[..., None]
        scl = SCLERA * (1 - pinkk) + np.array([0.62, 0.30, 0.29], f32) * pinkk
        car = np.exp(-(((x + 0.86 * A) / 0.07) ** 2 + ((y + 0.01) / 0.05) ** 2))[..., None]
        scl = scl * (1 - car) + np.array([0.70, 0.28, 0.28], f32) * car
        ang = np.arctan2(ey, x)
        rr = np.sqrt(r2)
        v1 = np.abs(np.sin(ang * 7 + 1.3 * np.sin(rr * 9 + ang * 3) + 0.6 * np.sin(ang * 23)))
        v2 = np.abs(np.sin(ang * 13 + 2.1 + 1.1 * np.sin(rr * 14 - ang * 5)))
        vein = (np.clip((0.05 - v1) / 0.05, 0, 1) * sstep(0.35, 0.95, rr) +
                0.6 * np.clip((0.035 - v2) / 0.035, 0, 1) * sstep(0.55, 1.0, rr))
        vein = np.clip(vein, 0, 1)[..., None] * 0.7
        D.scl = scl * (1 - vein) + VEIN * vein
        if z == 1.0:
            self._static = D
        return D

    def iris(self, S, x, y, px):
        """Iris + pupil for a block of pixels. Returns colour, emission, iris alpha, pupil alpha."""
        gx, gy = S.gx, S.gy
        dx, dy = x - f32(gx), y - f32(gy)
        m = math.hypot(gx, gy) / RE
        if m > 1e-4:                                     # foreshortening when looking sideways
            fz = math.sqrt(max(1 - m * m, 0.05))
            ux, uy = gx / (m * RE), gy / (m * RE)
            par = (dx * f32(ux) + dy * f32(uy)) * f32(1 / fz - 1)
            dx, dy = dx + par * f32(ux), dy + par * f32(uy)
        rho = np.sqrt(dx * dx + dy * dy)
        th = np.arctan2(dy, dx)
        rp = S.rp * (1 + 0.012 * np.sin(th * 7 + 1) + 0.008 * np.sin(th * 13))
        q = np.clip((rho - rp) / (RI - rp), 0, 1)

        fib = np.zeros_like(q)
        tot = 0.0
        for n, ph, tw, amp in self.fibers:
            fib += amp * np.sin(th * n + ph + tw * q + 0.8 * np.sin(q * 5 + ph))
            tot += amp
        fib = (0.5 + 0.5 * fib / tot) ** 1.6

        qc = 0.32 + 0.03 * np.sin(th * 11 + 0.5) + 0.02 * np.sin(th * 27)
        inner = sstep(qc + 0.06, qc - 0.06, q)
        icol = IRIS_OUTER * (1 - inner[..., None]) + IRIS_INNER * inner[..., None]
        bright = 0.40 + 1.0 * fib
        bright += 0.22 * np.exp(-((q - qc) / 0.035) ** 2)
        crypt = np.sin(th * 8 + 2) * np.sin(q * 14 + 2 * np.sin(th * 5))
        bright *= 1 - np.clip((crypt - 0.55) * 3, 0, 1) * (1 - inner) * 0.55
        limbal = sstep(0.72, 1.0, q)
        bright *= 1 - 0.9 * limbal
        bright *= 1 - 0.5 * sstep(0.06, 0.0, q)          # dark ruff at pupil edge
        col = icol * bright[..., None]
        emis = (S.emit * (0.5 + 0.8 * fib) * (1 - limbal) * (0.45 + 0.8 * inner))[..., None] * GLOW_COL
        ia = sstep(RI + px, RI - px, rho)
        pa = sstep(rp + px, rp - px, rho)
        ring = np.exp(-((rho - RI) / 0.025) ** 2)
        return col, emis, ia, pa, ring

    def eye(self, S):
        t, z = S.t, S.zoom
        px = self.pix / f32(z)
        h, w = self.h, self.w
        gxs, gys = S.gx * z, S.gy * z                    # iris centre on screen

        # once the iris fills the screen, skip everything else
        xm = float(self.X.max())
        far = max(math.hypot(xm - abs(gxs), 1 + abs(gys)), math.hypot(xm + abs(gxs), 1 + abs(gys)))
        if far < RI * z * 0.97:
            self.rain_mask = None
            x, y = self.X / f32(z), self.Y / f32(z)
            col, emis, ia, pa, ring = self.iris(S, x, y, px)
            img = col * (1 - pa)[..., None] * f32(S.light) + emis * (1 - pa)[..., None]
            if S.portal > 0:
                sl = self.box(0, 0, S.rp * z * 1.05)
                if sl is not None:
                    img[sl] += self.creation(t)[sl] * (pa[sl] * f32(S.portal))[..., None]
            return img

        D = self.eye_static(z)
        x, y, u, base = D.x, D.y, D.u, D.base

        # ---------- eyelids (move every frame) ----------
        upper = D.lo_full + 0.012 + (D.up_full - D.lo_full - 0.012) * f32(S.open)
        lower = D.lo_full
        inside = (np.clip((upper - y) / px, 0, 1) * np.clip((y - lower) / px, 0, 1) * (base > 0))

        # ---------- skin ----------
        fold = np.exp(-((y - (upper + 0.045 * base + 0.015)) / 0.04) ** 2) * base
        dist = np.where(y > upper, y - upper, np.maximum(lower - y, 0))
        dist = np.where(base > 0, dist, D.cdist)
        self.rain_mask = sstep(0.03, 0.45, dist) * (1 - inside)     # rain stays behind the eye
        sk = D.sk * (1 - 0.75 * np.exp(-dist / 0.05)) + 0.22 * fold
        sk = sk * 0.55 * np.exp(-dist / 0.045)          # fades into pitch black
        skin = sk[..., None] * SKIN

        # upper lashes (only computed where lashes can be)
        dl = y - upper
        llen = 0.11 * base ** 0.6 + 0.01
        zone = (dl > 0) & (dl < llen) & (base > 0.02)
        lash = D.lashl.copy()
        if zone.any():
            xs, us, s = x[zone], u[zone], dl[zone] / llen[zone]
            sg = np.sign(us)
            th_ = 0.90 + 0.08 * s
            l1 = np.clip((np.cos(xs * 230 - s * us * 9 - s * s * 5 * sg) - th_) / 0.05, 0, 1)
            l2 = np.clip((np.cos(xs * 171 + 1.3 - s * us * 7 - s * s * 6 * sg) - th_) / 0.05, 0, 1)
            lash[zone] = np.maximum(np.maximum(l1, l2) * (1 - s) ** 0.4, lash[zone])
        lash = np.maximum(lash, ((dl > 0) & (dl < 0.014) & (base > 0)).astype(f32))    # lid line
        skin = skin * (1 - 0.92 * lash[..., None])
        skin = skin * (1 - D.margin) + D.margin * np.array([0.50, 0.25, 0.24], f32)

        # ---------- eyeball ----------
        lid_sh = np.clip((upper - y) / 0.15, 0, 1) ** 0.7 * D.low_sh
        ball = D.scl.copy()
        emis = None
        pa_full = None
        sl = self.box(gxs, gys, (RI + 0.12) * z)
        if sl is not None:
            col, em, ia, pa, ring = self.iris(S, x[sl], y[sl], px)
            b = ball[sl] * (1 - 0.6 * ring)[..., None]
            b = b * (1 - ia[..., None]) + col * ia[..., None]
            b = b * (1 - pa[..., None]) + f32(0.004) * pa[..., None]
            ball[sl] = b
            emis = em * (ia * (1 - pa) * (0.35 + 0.65 * lid_sh[sl]))[..., None]
            pa_full = np.zeros((h, w), f32)
            pa_full[sl] = pa
        ball *= (D.shade * (0.15 + 0.85 * lid_sh) * (0.3 + 0.7 * sstep(1.0, 0.7, np.abs(u))))[..., None]

        # specular highlights on the wet cornea
        if sl is not None and z < 3.5:
            xs, ys = x[sl], y[sl]
            hx, hy = xs - f32(S.gx * 0.45 - 0.12), ys - f32(S.gy * 0.45 + 0.13)
            se = np.abs(hx / 0.055) ** 4 + np.abs(hy / 0.038) ** 4
            spec = np.clip((1 - se) / 0.35, 0, 1)
            spec *= 1 - 0.85 * np.clip(np.clip(1 - np.abs(hx) / 0.006, 0, 1) + np.clip(1 - np.abs(hy) / 0.005, 0, 1), 0, 1)
            spec2 = np.exp(-(((xs - f32(S.gx * 0.45 + 0.10)) / 0.014) ** 2 + ((ys - f32(S.gy * 0.45 - 0.09)) / 0.014) ** 2))
            sp = (spec * 1.9 + spec2 * 0.7) * f32(clamp(1 - (z - 1) / 2.5)) * f32(max(S.light, 0.5))
            ball[sl] += (sp * lid_sh[sl])[..., None]
        ball += (D.wet * lid_sh * f32(S.light))[..., None]

        ins = inside[..., None]
        img = (skin * (1 - ins) + ball * ins) * f32(S.light * 0.9 + 0.1)
        if emis is not None:
            img[sl] += emis * ins[sl]

        # portal: another world inside the pupil
        if S.portal > 0 and pa_full is not None:
            ps = self.box(gxs, gys, S.rp * z * 1.05)
            if ps is not None:
                img[ps] += self.creation(t)[ps] * (pa_full[ps] * inside[ps] * f32(S.portal))[..., None]
        return img

    # ---------------------------------------------------------------- frame
    def frame(self, t):
        if t < T_ZOOM:
            S = state_at(t)
            img = self.eye(S)
            if t < T_DARK + 1.5:               # heartbeat in the void
                hb = t % 1.1
                beat = (math.exp(-((hb - 0.15) / 0.07) ** 2) + 0.6 * math.exp(-((hb - 0.42) / 0.07) ** 2))
                beat *= ease(seg(t, 0.4, 1.4)) * (1 - ease(seg(t, T_DARK, T_DARK + 1.5)))
                g = np.exp(-(self.X ** 2 * 1.5 + self.Y ** 2 * 6))[..., None]
                img = img + g * f32(0.10 * beat) * np.array([0.9, 0.05, 0.05], f32)
        elif t < T_BANG:
            self.rain_mask = None
            if not GALAXY_ENDING and t >= T_SING:
                return np.zeros((self.h, self.w, 3), f32)        # inside the black hole: darkness
            img = self.creation(t)
        else:
            self.rain_mask = None
            img = self.universe(t)
        return img

    def post(self, img, fi):
        img = img * self.vignette
        bloom_src = np.clip(img - 0.75, 0, None)
        out = 1 - np.exp(-img * 1.25)                     # filmic tone map
        out = np.clip(out + self.grain[fi % len(self.grain)] * out * 0.8, 0, 1)
        if self.bars > 0:
            out[:self.bars] = 0
            out[-self.bars:] = 0
            bloom_src[:self.bars] = 0
            bloom_src[-self.bars:] = 0
        return (out * 255).astype(np.uint8), bloom_src


def make_bloom(src, size, div=6):
    h, w, _ = src.shape
    h2, w2 = h // div, w // div
    small = src[:h2 * div, :w2 * div].reshape(h2, div, w2, div, 3).mean(axis=(1, 3))
    for _ in range(2):   # cheap blur
        small = (small + np.roll(small, 1, 0) + np.roll(small, -1, 0) +
                 np.roll(small, 1, 1) + np.roll(small, -1, 1)) / 5
    small = np.clip(1 - np.exp(-small * 1.4), 0, 1)
    surf = pygame.image.frombuffer((small * 255).astype(np.uint8).tobytes(), (w2, h2), "RGB")
    surf = pygame.transform.smoothscale(surf, (size[0] // 4, size[1] // 4))
    return pygame.transform.smoothscale(surf, size)



# ----------------------------------------------------------------------------
# code rain
# ----------------------------------------------------------------------------
def rain_rate(t):
    """How fast the rain falls (0 = frozen)."""
    if t < T_LOOK:
        return 1.0
    if t < T_LOOK + 0.35:
        return 0.0                                     # it found you: time stops
    if t < T_STARE:
        return 2.2                                     # ...then everything speeds up
    return 2.2 + 6.0 * ease(seg(t, T_STARE, T_STARE + 1.5))

def rain_level(t):
    """How much rain is on screen (0..1)."""
    if t < T_DARK:
        return 0.15 + 0.2 * ease(seg(t, 0.5, T_DARK))  # system waking up
    if t < T_OPEN:
        return lerp(0.35, 1.0, ease(seg(t, T_DARK, T_OPEN)))
    if t < T_STARE:
        return 1.0
    return 1 - ease(seg(t, T_STARE + 0.3, T_STARE + 2.2))


class Rain:
    LEVELS = 14

    def __init__(self, size):
        self.size = size
        rng = np.random.default_rng(3)
        names = "consolas,dejavusansmono,couriernew,menlo,monospace"
        self.layers = []
        # (font size, surface scale, brightness, speed) : far layer is small, soft and dim
        for fsize, scale, bright, speed in ((12, 0.6, 0.45, 0.55), (17, 1.0, 1.0, 1.0)):
            font = pygame.font.SysFont(names, fsize, bold=True)
            cw, ch = font.size("0")
            ch = int(ch * 0.92)
            W, H = int(size[0] * scale), int(size[1] * scale)
            cols, rows = W // cw + 1, H // ch + 2
            atlas = []
            for lv in range(self.LEVELS):
                k = lv / (self.LEVELS - 1)
                if lv == self.LEVELS - 1:
                    c = RAIN_HEAD
                else:
                    c = tuple(int(RAIN_TRAIL[i] * (0.15 + 0.85 * k) ** 1.4 + (RAIN_HEAD[i] - RAIN_TRAIL[i]) * k ** 6)
                              for i in range(3))
                c = tuple(min(255, int(v * bright)) for v in c)
                atlas.append([font.render(g, True, c, (0, 0, 0)) for g in RAIN_CHARS])
            n = cols
            self.layers.append(dict(
                surf=pygame.Surface((W, H)), scale=scale, cw=cw, ch=ch, cols=cols, rows=rows, atlas=atlas,
                speed=(rng.uniform(5, 16, n) * speed), off=rng.uniform(0, 200, n),
                length=rng.integers(8, 26, n), gate=rng.random(n), flick=rng.uniform(4, 14, n),
                table=rng.integers(0, len(RAIN_CHARS), 4096)))
        ts = np.arange(0, T_TOTAL + 1, 0.01)
        self.clock_t = ts
        self.clock = np.cumsum([rain_rate(x) for x in ts]) * 0.01

    def draw(self, screen, t, mask):
        level = rain_level(t)
        if level <= 0.01 or mask is None:
            return
        tau = float(np.interp(t, self.clock_t, self.clock))
        glitch = T_LOOK < t < T_LOOK + 0.35
        stretch = 1 + 2.5 * ease(seg(t, T_STARE, T_STARE + 1.5))
        out = pygame.Surface(self.size)
        rng = np.random.default_rng(int(t * 60))
        for L in self.layers:
            surf = L["surf"]
            surf.fill((0, 0, 0))
            cw, ch, rows, atlas, tab = L["cw"], L["ch"], L["rows"], L["atlas"], L["table"]
            for c in range(L["cols"]):
                if L["gate"][c] > level * RAIN_DENSITY:
                    continue
                length = int(L["length"][c] * stretch)
                span = rows + length + 6
                head = (L["off"][c] + tau * L["speed"][c]) % span
                hr = int(head)
                x = c * cw
                if glitch:
                    x += int(rng.integers(-4, 5))
                tick = int(tau * L["flick"][c])
                for k in range(length):
                    r = hr - k
                    if r < 0 or r >= rows:
                        continue
                    lv = (self.LEVELS - 1) if k == 0 else int((self.LEVELS - 2) * (1 - k / length) ** 1.8)
                    g = tab[(c * 131 + r * 17 + (tick + r * 7) // 3) & 4095]
                    surf.blit(atlas[lv][g], (x, r * ch), special_flags=pygame.BLEND_ADD)
            if L["scale"] != 1.0:
                out.blit(pygame.transform.smoothscale(surf, self.size), (0, 0), special_flags=pygame.BLEND_ADD)
            else:
                out.blit(surf, (0, 0), special_flags=pygame.BLEND_ADD)

        # soft glow around the bright characters
        small = pygame.transform.smoothscale(out, (self.size[0] // 6, self.size[1] // 6))
        glow = pygame.transform.smoothscale(small, self.size)
        glow.fill((150, 150, 150), special_flags=pygame.BLEND_MULT)
        out.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)

        # fade with the story, flicker on the glitch, and keep it behind the eye
        k = level * (rng.uniform(0.4, 1.6) if glitch else 1.0)
        m = np.clip(mask * k * 255, 0, 255).astype(np.uint8)
        h, w = m.shape
        msurf = pygame.image.frombuffer(np.repeat(m[..., None], 3, 2).tobytes(), (w, h), "RGB")
        out.blit(pygame.transform.smoothscale(msurf, self.size), (0, 0), special_flags=pygame.BLEND_MULT)
        screen.blit(out, (0, 0), special_flags=pygame.BLEND_ADD)


# ----------------------------------------------------------------------------
# ASCII look + HUD
# ----------------------------------------------------------------------------
class AsciiFilter:
    """Rebuilds the final frame out of tiny coloured characters."""

    def __init__(self, size):
        self.size = size
        cw, ch = ASCII_CELL
        font = pygame.font.SysFont("consolas,dejavusansmono,couriernew,menlo,monospace", 22, bold=True)
        raw = []
        for c in ASCII_CHARS:
            g = font.render(c, True, (255, 255, 255), (0, 0, 0))
            s = pygame.Surface(g.get_size(), depth=24)
            s.blit(g, (0, 0))
            raw.append(pygame.surfarray.array3d(s)[:, :, 0].T.astype(f32) / 255)
        hmin = min(a.shape[0] for a in raw)
        wmin = min(a.shape[1] for a in raw)
        raw = np.array([a[:hmin, :wmin] for a in raw])
        ink = raw.max(axis=0)
        ys, xs = np.nonzero(ink > 0.2)
        raw = raw[:, ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        glyphs = []
        for a in raw:
            s = pygame.image.frombuffer(np.repeat((a * 255).astype(np.uint8)[..., None], 3, 2).tobytes(),
                                        (a.shape[1], a.shape[0]), "RGB")
            s = pygame.transform.smoothscale(s, (cw, ch))
            glyphs.append(pygame.surfarray.array3d(s)[:, :, 0].T.astype(f32) / 255)
        glyphs = np.array(glyphs)
        cov = glyphs.mean(axis=(1, 2))
        order = np.argsort(cov)
        self.G = glyphs[order]
        self.cov = cov[order]
        self.ramp = (self.cov - self.cov.min()) / (self.cov.max() - self.cov.min())
        self.cols = size[0] // cw + 1
        self.rows = size[1] // ch + 1
        self.gain = (1 / (self.cov + 0.12)).astype(f32)

    def apply(self, screen, fi):
        """Glyph shape x cell colour, mixed with the smooth image (blending done by pygame in C)."""
        W, H = self.size
        cw, ch = ASCII_CELL
        rows, cols = self.rows, self.cols
        if not hasattr(self, "Gq"):
            g = np.round((0.28 + 0.72 * self.G) * ASCII_MIX * 255).astype(np.uint8)
            self.Gq = np.repeat(g[..., None], 3, 3)                        # n, ch, cw, 3
            k = int(round((1 - ASCII_MIX) * 255))
            self.keep = (k, k, k)
        small = pygame.transform.smoothscale(screen, (cols, rows))
        cell = np.frombuffer(pygame.image.tobytes(small, "RGB"), np.uint8).reshape(rows, cols, 3)
        lum = (cell @ np.array([0.3, 0.59, 0.11], f32)) / 255
        q = np.clip(lum * 1.8, 0, 1) ** 0.75
        idx = np.searchsorted(self.ramp, q).clip(0, len(self.ramp) - 1)
        if fi % 2 == 0 or getattr(self, "_flick", None) is None:     # characters shimmer a little
            rng = np.random.default_rng(fi)
            self._flick = np.where(rng.random(idx.shape) < 0.06, rng.integers(-2, 3, idx.shape), 0)
        idx = np.where(lum < 0.01, 0, (idx + self._flick).clip(1, len(self.ramp) - 1))
        boost = np.minimum(cell * (self.gain[idx] * 0.72 + 0.28)[..., None], 255).astype(np.uint8)
        colr = pygame.transform.scale(pygame.image.frombuffer(boost.tobytes(), (cols, rows), "RGB"),
                                      (cols * cw, rows * ch))
        mask = np.ascontiguousarray(self.Gq[idx].transpose(0, 2, 1, 3, 4)).reshape(rows * ch, cols * cw, 3)
        colr.blit(pygame.image.frombuffer(mask.tobytes(), (cols * cw, rows * ch), "RGB"), (0, 0),
                  special_flags=pygame.BLEND_MULT)
        screen.fill(self.keep, special_flags=pygame.BLEND_MULT)
        screen.blit(colr, (0, 0), special_flags=pygame.BLEND_ADD)


CHAPTERS = [
    (T_DARK, "VOID"), (T_LOOK, "EYE"), (T_STARE, "EYE > LOCKED ON"), (T_ZOOM, "EYE > PUPIL"),
    (T_SING, "EVENT HORIZON"), (T_BANG, "SINGULARITY"), (T_WARP, "BIG BANG"),
    (T_DIVE, "GALAXY"), (T_TOTAL + 1, "INFINITY"),
]
if not GALAXY_ENDING:
    CHAPTERS = CHAPTERS[:5] + [(T_TOTAL + 1, "SINGULARITY")]

class Hud:
    def __init__(self, bar):
        self.font = pygame.font.SysFont("consolas,dejavusansmono,couriernew,menlo,monospace", 15, bold=True)
        self.small = pygame.font.SysFont("consolas,dejavusansmono,couriernew,menlo,monospace", 13)
        self.bar = bar

    def zoom_value(self, t):
        if t < T_STARE:
            return 1.0
        return math.exp(0.32 * (t - T_STARE)) * (1 + 31 * seg(t, T_STARE, T_ZOOM))

    def draw(self, screen, t, fps, ascii_on):
        W, H = screen.get_size()
        start, name = 0.0, CHAPTERS[0][1]
        prev = 0.0
        for end, nm in CHAPTERS:
            if t < end:
                start, name = prev, nm
                break
            prev = end
        typed = name[:int((t - start) * 22) + 1]
        cursor = "_" if int(t * 2.5) % 2 == 0 else " "
        col, dim = (215, 225, 240), (110, 125, 150)
        top = max(8, self.bar // 2 - 9)
        screen.blit(self.font.render("SYS:// > " + typed + cursor, True, col), (24, top))
        tag = self.small.render("EYE OF GOD  v4", True, dim)
        screen.blit(tag, (W - tag.get_width() - 24, top + 2))
        info = "ZOOM x%-10.1f SCENE %-18s T %05.2fs   %4.1f FPS   ASCII %s" % (
            self.zoom_value(t), name, t, fps, "ON" if ascii_on else "OFF")
        screen.blit(self.small.render(info, True, dim), (24, H - max(8, self.bar // 2 + 8)))

def draw(scene, screen, t, fi, rain=None, ascii_f=None, hud=None, fps=30.0):
    img = scene.frame(t)
    rgb, bsrc = scene.post(img, fi)
    surf = pygame.image.frombuffer(rgb.tobytes(), (scene.w, scene.h), "RGB")
    screen.blit(pygame.transform.smoothscale(surf, screen.get_size()), (0, 0))
    screen.blit(make_bloom(bsrc, screen.get_size()), (0, 0), special_flags=pygame.BLEND_ADD)
    if rain is not None and scene.rain_mask is not None:
        mask = scene.rain_mask * scene.vignette[..., 0]
        if scene.bars > 0:
            mask[:scene.bars] = 0
            mask[-scene.bars:] = 0
        rain.draw(screen, t, mask)
    if ascii_f is not None:
        ascii_f.apply(screen, fi)
    if hud is not None:
        hud.draw(screen, t, fps, ascii_f is not None)


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    record = "--record" in sys.argv
    pygame.init()
    screen = pygame.display.set_mode(WINDOW, pygame.SCALED)
    pygame.display.set_caption("Eye of God")
    clock = pygame.time.Clock()
    scene = Scene(*(RECORD_RENDER if record else RENDER))
    rain = Rain(WINDOW) if RAIN else None
    ascii_f = AsciiFilter(WINDOW)
    hud = Hud(scene.bars * WINDOW[1] // scene.h)
    use_ascii, use_hud = ASCII, HUD

    if record:
        os.makedirs("frames", exist_ok=True)
        n = int(T_TOTAL * FPS)
        for i in range(n):
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    pygame.quit()
                    return
            draw(scene, screen, i / FPS, i, rain, ascii_f if use_ascii else None, hud if use_hud else None, FPS)
            pygame.display.flip()
            pygame.image.save(screen, os.path.join("frames", "frame_%05d.png" % i))
            pygame.display.set_caption("Recording %d / %d" % (i + 1, n))
        pygame.quit()
        print("Done! Turn the frames into a video with ffmpeg:")
        print("  ffmpeg -framerate 30 -i frames/frame_%05d.png -c:v libx264 -pix_fmt yuv420p eye_of_god.mp4")
        return

    start = time.perf_counter()
    fi = 0
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_f:
                    pygame.display.toggle_fullscreen()
                elif e.key == pygame.K_r:
                    start = time.perf_counter()
                elif e.key == pygame.K_a:
                    use_ascii = not use_ascii
                elif e.key == pygame.K_h:
                    use_hud = not use_hud
        t = time.perf_counter() - start
        if t > T_TOTAL:
            if not LOOP:
                break
            start = time.perf_counter()
            t = 0.0
        draw(scene, screen, t, fi, rain, ascii_f if use_ascii else None, hud if use_hud else None, clock.get_fps())
        pygame.display.flip()
        fi += 1
        clock.tick(FPS)
    pygame.quit()


if __name__ == "__main__":
    main()