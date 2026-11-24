"""
ring.py - bits drifting in a void swirl together and forge a shiny silver
ring with a diamond, drawn entirely in ASCII.

Setup (once):   pip install pygame-ce numpy
Run:            python ring.py

Keys:
    Space     forge it again
    F11 / F   fullscreen on/off
    B         switch letters <-> binary only (0 and 1)
    Esc / Q   quit
"""

import math
import random

import numpy as np
import pygame

# ------------------------------------------------------------------ settings --
HANDLE = "@w_selui"
FONT_SIZE = 9             # smaller = more letters = more detail
WINDOW = (1280, 760)
FPS = 30
N_BITS = 2600             # bits that fly in to build the ring
SPIN = 0.32               # how fast the finished ring turns
SHINE_EVERY = 4.5         # seconds between shine sweeps
GLOW = 1.0
CHARSET = "letters"

TAU = 2 * math.pi
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
RAMP_CODES = np.array([ord(c) for c in RAMP], dtype=np.int32)

# ring shape (local units)
R_RING = 1.0              # radius of the band
A_TH = 0.075              # band thickness (half)
B_W = 0.17                # band width (half)

# timeline (seconds)
T_SWIRL = 2.5             # bits start flying in
T_LAND0, T_LAND1 = 4.2, 6.6   # band builds up around the circle
T_GEM0, T_GEM1 = 7.4, 8.6     # diamond forms
T_DONE = 9.2

# palettes: 0 silver, 1 diamond, 2 cool bits, 3..8 heat (white-hot -> deep red)
PALETTES = [(222, 228, 240), (205, 235, 255), (120, 190, 255),
            (255, 248, 230), (255, 222, 160), (255, 180, 95),
            (250, 135, 60), (215, 85, 40), (150, 55, 35)]


def ease(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def colour(level, pal):
    b = level / 15
    r, g, bl = PALETTES[pal]
    k = b ** 0.9
    w = max(0.0, b - 0.82) * 3.0                        # brightest = white-hot
    return (int(min(255, r * k + (255 - r) * w)),
            int(min(255, g * k + (255 - g) * w)),
            int(min(255, bl * k + (255 - bl) * w)))


# --------------------------------------------------------------- the model --
def build_band(nu=460, nv=44):
    """Comfort-fit band: torus with a rounded-rectangle cross-section."""
    u = np.linspace(0, TAU, nu, endpoint=False)
    v = np.linspace(0, TAU, nv, endpoint=False)
    U, V = [a.ravel() for a in np.meshgrid(u, v, indexing="ij")]
    er = np.stack([np.cos(U), np.sin(U), np.zeros_like(U)], 1)
    ez = np.array([0.0, 0.0, 1.0])
    c, s = np.cos(V), np.sin(V)
    rx = A_TH * np.sign(c) * np.abs(c) ** 0.5
    rz = B_W * np.sign(s) * np.abs(s) ** 0.5
    P = R_RING * er + rx[:, None] * er + rz[:, None] * ez
    N = (np.sign(c) * np.abs(c) ** 1.5 / A_TH)[:, None] * er + \
        (np.sign(s) * np.abs(s) ** 1.5 / B_W)[:, None] * ez
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    return P, N, U


def build_gem():
    """Round brilliant diamond on 4 prongs, sitting on top of the band."""
    g, table, crown_h, pav_h = 0.3, 0.165, 0.12, 0.26
    y0 = R_RING + A_TH + 0.2
    P, N, F = [], [], []
    facets = 8

    def facet_centre(phi, shift):
        k = np.floor((phi + shift) / (TAU / facets))
        return (k + 0.5) * TAU / facets - shift, k

    phi = np.linspace(0, TAU, 260, endpoint=False)
    for t in np.linspace(0, 1, 14):                               # crown
        r, y = g + (table - g) * t, y0 + crown_h * t
        shift = 0.0 if t < 0.5 else TAU / 16
        pc, k = facet_centre(phi, shift)
        n = np.stack([np.cos(pc), np.full_like(pc, (g - table) / crown_h), np.sin(pc)], 1)
        P.append(np.stack([r * np.cos(phi), np.full_like(phi, y), r * np.sin(phi)], 1))
        N.append(n); F.append(k + (0 if t < 0.5 else 20))
    for rr in np.linspace(0, table, 8):                           # table
        P.append(np.stack([rr * np.cos(phi), np.full_like(phi, y0 + crown_h), rr * np.sin(phi)], 1))
        N.append(np.tile([0.0, 1.0, 0.0], (len(phi), 1))); F.append(np.full(len(phi), 40.0))
    for t in np.linspace(0, 1, 18):                               # pavilion
        r, y = g * (1 - t), y0 - pav_h * t
        pc, k = facet_centre(phi, TAU / 16)
        n = np.stack([np.cos(pc), np.full_like(pc, -g / pav_h), np.sin(pc)], 1)
        P.append(np.stack([r * np.cos(phi), np.full_like(phi, y), r * np.sin(phi)], 1))
        N.append(n); F.append(k + 60)
    gem_P, gem_N, gem_F = np.concatenate(P), np.concatenate(N), np.concatenate(F)
    gem_N /= np.linalg.norm(gem_N, axis=1, keepdims=True)

    # prongs (metal)
    pp, pn = [], []
    a = np.linspace(0, TAU, 10, endpoint=False)
    for k in range(4):
        ph = TAU / 8 + k * TAU / 4
        for t in np.linspace(0, 1, 22):
            cx = (g * 0.85 + g * 0.2 * t) * math.cos(ph)
            cz = (g * 0.85 + g * 0.2 * t) * math.sin(ph)
            cy = (R_RING + A_TH - 0.02) + (y0 + 0.05 - R_RING - A_TH + 0.02) * t
            pp.append(np.stack([cx + 0.022 * np.cos(a), np.full_like(a, cy), cz + 0.022 * np.sin(a)], 1))
            pn.append(np.stack([np.cos(a), np.zeros_like(a), np.sin(a)], 1))
    return gem_P, gem_N, gem_F, np.concatenate(pp), np.concatenate(pn), y0


BAND_P, BAND_N, BAND_U = build_band()
GEM_P, GEM_N, GEM_F, PRONG_P, PRONG_N, GEM_Y = build_gem()


def rotation(t):
    th = 0.6 + SPIN * t
    tilt = -0.3 + 0.05 * math.sin(t * 0.5)
    cy, sy = math.cos(th), math.sin(th)
    cx, sx = math.cos(tilt), math.sin(tilt)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    return Rx @ Ry


# ------------------------------------------------------------------ shading --
LIGHT = np.array([-0.45, 0.7, -0.55]); LIGHT /= np.linalg.norm(LIGHT)


def studio(R, t):
    """Reflection of a photo studio: soft boxes + a moving shine band."""
    e = 0.08 + 0.85 * np.clip((R[:, 1] - 0.45) / 0.3, 0, 1)          # overhead softbox
    e = e + 0.75 * np.exp(-((R[:, 0] - 0.55) / 0.13) ** 2)           # strip light right
    e = e + 0.45 * np.exp(-((R[:, 0] + 0.65) / 0.10) ** 2)           # strip light left
    e = e + 0.12 * np.clip(-R[:, 1], 0, 1)                           # floor bounce
    s = -1.7 + 3.4 * ((t % SHINE_EVERY) / SHINE_EVERY) * 1.6
    e = e + 1.1 * np.exp(-(((R[:, 0] * 0.8 + R[:, 1] * 0.6) - s) / 0.09) ** 2)
    return e


def shade_metal(P, N, t):
    V = -P / np.linalg.norm(P, axis=1, keepdims=True)
    nv = np.sum(N * V, axis=1)
    R = 2 * nv[:, None] * N - V
    diff = np.clip(N @ LIGHT, 0, 1)
    spec = np.clip(R @ LIGHT, 0, 1) ** 50
    rim = (1 - np.abs(nv)) ** 3
    return np.clip(0.06 + 0.2 * diff + 0.7 * studio(R, t) + 0.8 * spec + 0.25 * rim, 0, 1)


def shade_gem(P, N, F, t, spin):
    V = -P / np.linalg.norm(P, axis=1, keepdims=True)
    nv = np.sum(N * V, axis=1)
    R = 2 * nv[:, None] * N - V
    e = studio(R, t)
    fire = 0.5 + 0.5 * np.sin(F * 1.7 + spin * 9 + t * 1.3)            # facets flash in turn
    return np.clip(0.22 + 0.55 * e ** 1.5 + 0.5 * fire ** 6, 0, 1)


# -------------------------------------------------------------------- scene --
class Forge:
    def __init__(self, cols, rows, aspect):
        self.cols, self.rows, self.aspect = cols, rows, aspect
        self.Z = 4.6
        self.F = 0.92 * rows * self.Z / (2 * (R_RING + 0.5) * aspect)
        # when each part of the band lands (sweeps around the circle)
        start = random.uniform(0, TAU)
        frac = ((BAND_U - start) % TAU) / TAU
        self.band_arr = T_LAND0 + frac * (T_LAND1 - T_LAND0) + np.random.uniform(0, 0.25, len(BAND_U))
        self.gem_arr = np.random.uniform(T_GEM0 + 0.4, T_GEM1, len(GEM_P))
        self.prong_arr = np.random.uniform(T_GEM0, T_GEM0 + 0.6, len(PRONG_P))

        # the bits: each flies to a target point and lands at its arrival time
        nb = N_BITS
        pick = np.random.randint(0, len(BAND_P), nb)
        gpick = np.random.randint(0, len(GEM_P), 350)
        self.target = np.concatenate([BAND_P[pick], GEM_P[gpick]])
        self.arrive = np.concatenate([self.band_arr[pick], self.gem_arr[gpick]])
        self.fly = np.random.uniform(1.3, 2.2, len(self.target))
        n = len(self.target)
        d = np.random.normal(size=(n, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        self.start = d * np.random.uniform(1.8, 4.2, (n, 1)) * np.array([1.6, 1.0, 1.0])
        self.drift = np.random.normal(scale=0.03, size=(n, 3))
        self.bit = np.where(np.random.random(n) < 0.5, ord("0"), ord("1"))
        self.stars = []
        self.burst_done = False

    def project(self, P):
        Z = P[:, 2]
        return (self.cols / 2 + P[:, 0] * self.F / Z,
                self.rows / 2 - P[:, 1] * self.F * self.aspect / Z)


def bits_position(fg, t):
    """Where every bit is: drifting in the void, then spiralling in."""
    s = np.clip((t - (fg.arrive - fg.fly)) / fg.fly, 0, 1)
    e = ease(s)
    drift_t = np.minimum(t, fg.arrive - fg.fly)[:, None]
    p0 = fg.start + fg.drift * drift_t
    a0, a1 = np.arctan2(p0[:, 1], p0[:, 0]), np.arctan2(fg.target[:, 1], fg.target[:, 0])
    da = (a1 - a0) % TAU + TAU                     # one extra turn: a real swirl
    ang = a0 + da * e
    r0, r1 = np.hypot(p0[:, 0], p0[:, 1]), np.hypot(fg.target[:, 0], fg.target[:, 1])
    r = r0 + (r1 - r0) * e
    z = p0[:, 2] + (fg.target[:, 2] - p0[:, 2]) * e
    return np.stack([r * np.cos(ang), r * np.sin(ang), z], 1), s


def build_frame(fg, t, binary):
    cols, rows = fg.cols, fg.rows
    n = cols * rows
    M = rotation(t)
    spin = 0.6 + SPIN * t
    off = np.array([0.0, -0.18, fg.Z])

    # ---- surfaces that have landed
    vis = fg.band_arr <= t
    P = BAND_P[vis] @ M.T + off
    N = BAND_N[vis] @ M.T
    heat = np.clip(1 - (t - fg.band_arr[vis]) / 2.8, 0, 1)
    lum = shade_metal(P, N, t)
    lum = np.maximum(lum * (1 - heat * 0.6), heat * 0.95)
    pal = np.where(heat < 0.04, 0, 3 + np.minimum(5, ((1 - heat) * 6).astype(int)))

    gv = fg.gem_arr <= t
    GP = GEM_P[gv] @ M.T + off
    GN = GEM_N[gv] @ M.T
    glum = shade_gem(GP, GN, GEM_F[gv], t, spin)
    pv = fg.prong_arr <= t
    PP = PRONG_P[pv] @ M.T + off
    PN = PRONG_N[pv] @ M.T
    plum = shade_metal(PP, PN, t)

    allP = np.concatenate([P, GP, PP])
    allL = np.concatenate([lum, glum, plum])
    allK = np.concatenate([pal, np.ones(len(GP), int), np.zeros(len(PP), int)])

    ch = np.zeros(n, dtype=np.int32)
    br = np.zeros(n, dtype=np.float32)
    pa = np.zeros(n, dtype=np.int8)
    if len(allP):
        sx, sy = fg.project(allP)
        ix, iy = sx.astype(int), sy.astype(int)
        ok = (ix >= 0) & (ix < cols) & (iy >= 0) & (iy < rows)
        idx = (iy * cols + ix)[ok]
        z, L, K = allP[ok, 2], allL[ok], allK[ok]
        zmin = np.full(n, np.inf)
        np.minimum.at(zmin, idx, z)
        front = z <= zmin[idx] + 0.07                  # only the side facing us
        lsum = np.zeros(n); cnt = np.zeros(n)
        np.add.at(lsum, idx[front], L[front])
        np.add.at(cnt, idx[front], 1)
        order = np.argsort(-z[front])
        pa[idx[front][order]] = K[front][order]
        has = cnt > 0
        lv = np.zeros(n)
        lv[has] = np.maximum(lsum[has] / cnt[has], 0.07)
        br[has] = lv[has]
        ch[has] = RAMP_CODES[np.clip((lv[has] * (len(RAMP) - 1)).astype(int), 1, len(RAMP) - 1)]
        zfront = zmin
    else:
        zfront = np.full(n, np.inf)

    # ---- bits (void drift + swirl)
    bp, s = bits_position(fg, t)
    flying = t < fg.arrive
    if flying.any():
        Q = bp[flying] @ M.T + off
        okz = Q[:, 2] > 0.5
        Q = Q[okz]
        sx, sy = fg.project(Q)
        ix, iy = sx.astype(int), sy.astype(int)
        ok = (ix >= 0) & (ix < cols) & (iy >= 0) & (iy < rows)
        idx = (iy * cols + ix)[ok]
        sf = s[flying][okz][ok]
        twinkle = 0.5 + 0.5 * np.sin(t * 3 + idx * 0.37)
        b = np.where(sf > 0, 0.35 + 0.65 * sf, 0.1 + 0.18 * twinkle)
        front = Q[ok, 2] < zfront[idx]
        idx, b, sf = idx[front], b[front], sf[front]
        ch[idx] = fg.bit[flying][okz][ok][front]
        br[idx] = b
        pa[idx] = np.where(sf > 0.55, 3 + np.minimum(5, ((1 - sf) * 8).astype(int)), 2)

    # ---- diamond completes: starburst
    if t >= T_GEM1 and not fg.burst_done:
        fg.burst_done = True
        g = (np.array([[0.0, GEM_Y + 0.03, 0.0]]) @ M.T + off)
        gx, gy = fg.project(g)
        fg.stars.append([gx[0], gy[0], 0.0, 1.1, 7])

    # ---- glints on the finished metal and stone
    if t > T_DONE:
        bright = np.nonzero(br > 0.93)[0]
        if len(bright) and random.random() < 0.5:
            k = random.choice(bright.tolist())
            fg.stars.append([k % cols, k // cols, 0.0, random.uniform(0.4, 0.8),
                             random.choice((1, 2, 2, 3))])
    keep = []
    for st in fg.stars:
        st[2] += 1 / FPS
        if st[2] < st[3]:
            k = math.sin(math.pi * st[2] / st[3])
            x, y, arm = int(st[0]), int(st[1]), st[4]
            for dx, dy, c, f in [(0, 0, "*", 1.0)] + \
                    [(d, 0, "-", 1 - abs(d) / (arm + 1)) for d in range(-arm * 2, arm * 2 + 1) if d] + \
                    [(0, d, "|", 1 - abs(d) / (arm + 1)) for d in range(-arm, arm + 1) if d]:
                xx, yy = x + dx, y + dy
                if 0 <= xx < cols and 0 <= yy < rows:
                    j = yy * cols + xx
                    if k * f > br[j] or ch[j] == 0:
                        ch[j], br[j], pa[j] = ord(c), min(1.0, k * f + 0.1), 1
            keep.append(st)
    fg.stars = keep

    if binary:
        on = ch != 0
        keepc = np.isin(ch, [ord(c) for c in "*-|"])
        ch = np.where(on & ~keepc, np.where(br > 0.55, ord("1"), ord("0")), ch)

    phase = ("void" if t < T_SWIRL else "gathering" if t < T_LAND0 else
             "forging" if t < T_LAND1 else "cooling" if t < T_GEM0 else
             "setting the stone" if t < T_DONE else "polished")
    return ch.reshape(rows, cols), br.reshape(rows, cols), pa.reshape(rows, cols), \
        int(flying.sum()), phase


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
                if l >= 11:
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


def draw_hud(screen, ren, t, bits, letters, phase, fps):
    w, h = screen.get_size()
    dim, pink = (110, 118, 128), (225, 110, 150)
    f = ren.hud
    lh = f.get_linesize()
    screen.blit(f.render(f"t {t:05.2f}s", True, pink), (w - 100, 8))
    for i, line in enumerate((f"{HANDLE} · 2026", f"bits in flight {bits:,}",
                              f"letters {letters:,}", phase)):
        screen.blit(f.render(line, True, dim), (10, h - 26 - (4 - i) * lh))
    pygame.draw.line(screen, (30, 34, 40), (0, h - 22), (w, h - 22))
    screen.blit(f.render("py ring.py", True, dim), (6, h - 19))
    txt = f.render(f"running · {fps:.0f} fps", True, dim)
    screen.blit(txt, (w - txt.get_width() - 8, h - 19))


def main():
    global CHARSET
    pygame.init()
    pygame.display.set_caption("ring.py")
    screen = pygame.display.set_mode(WINDOW, pygame.RESIZABLE)
    clock = pygame.time.Clock()
    ren = Renderer()

    def new_forge():
        w, h = screen.get_size()
        return Forge(w // ren.cw, (h - 90) // ren.ch, ren.cw / ren.ch), pygame.time.get_ticks()

    fg, start = new_forge()
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
                fg, start = new_forge()
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_b:
                CHARSET = "binary" if CHARSET == "letters" else "letters"
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                fg, start = new_forge()
            elif e.type == pygame.VIDEORESIZE and not full:
                screen = pygame.display.set_mode(e.size, pygame.RESIZABLE)
                fg, start = new_forge()
        t = (pygame.time.get_ticks() - start) / 1000
        ch, br, pa, bits, phase = build_frame(fg, t, CHARSET == "binary")
        ren.draw(screen, ch, br, pa, min(1.0, t / 0.8 + 0.2))
        draw_hud(screen, ren, t, bits, int((ch != 0).sum()), phase, clock.get_fps())
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()