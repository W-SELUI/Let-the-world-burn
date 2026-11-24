"""
butterfly.py - a dark mirror cracks open and glowing ASCII butterflies
fly out of the hole, shimmering and leaving glitter behind them.

Setup (once):   pip install pygame-ce numpy
Run:            python butterfly.py

Mouse:
    move      butterflies scatter away from your cursor
    click     crack the mirror right there (more butterflies come out)
Keys:
    F11 / F   fullscreen on/off
    B         switch letters <-> binary only (0 and 1)
    Space     start over
    Esc / Q   quit
"""

import math
import random

import numpy as np
import pygame

# ------------------------------------------------------------------ settings --
HANDLE = "@w_selui"
N_FLIES = 12              # butterflies from the first crack
N_PER_CLICK = 5           # butterflies from each crack you click
FONT_SIZE = 9             # smaller = more letters = more detail
WINDOW = (1280, 760)
FPS = 30
CYCLE_SECONDS = 50        # then it fades and starts again
CHARSET = "letters"       # "letters" or "binary"
GLOW = 1.0                # glow strength, 0 = off
GLITTER = 1.0             # glitter amount, 0 = off
BUTTERFLY_SIZE = 1.0      # 1.2 = bigger, 0.8 = smaller

TAU = 2 * math.pi
GOLD = 0.6180339887
# 70 characters from light to dense - classic image-to-ASCII shading
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
RAMP_CODES = np.array([ord(c) for c in RAMP], dtype=np.int32)
TWINKLE = ".+*+."

# colour tints: icy blue, cyan, lavender, white
TINTS = [(150, 205, 255), (110, 235, 255), (185, 170, 255), (225, 235, 255)]


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ink_colour(b, tint):
    """Dim = dark tint, bright = tint, very bright = towards white."""
    b = min(1.0, max(0.0, b))
    r, g, bl = TINTS[tint]
    k = b ** 0.85
    w = max(0.0, b - 0.8) * 2.5            # top end goes white-hot
    return (int(min(255, r * k + (255 - r) * w * k)),
            int(min(255, g * k + (255 - g) * w * k)),
            int(min(255, bl * k + (255 - bl) * w * k)))


def char_for(dx, dy):
    a = math.degrees(math.atan2(dy, dx)) % 180
    if a < 22 or a >= 158:
        return "-"
    if a < 68:
        return "\\"
    if a < 112:
        return "|"
    return "/"


# ------------------------------------------------------------ butterfly art --
# Local coordinates: x = out along the wing, y = towards the head.
def _E(x, y, cx, cy, rx, ry, rot):
    dx, dy = x - cx, y - cy
    c, s = math.cos(rot), math.sin(rot)
    u, v = (dx * c + dy * s) / rx, (-dx * s + dy * c) / ry
    return u * u + v * v


def wing_light(x, y, shimmer):
    """Brightness of one wing at (x, y): 0 = not wing."""
    ang = np.arctan2(y, x)
    scallop = 1 + 0.05 * np.sin(ang * 30)                 # wavy outer edge
    fore = _E(x, y, 0.55, 0.30, 0.60, 0.30, 0.42) * scallop
    hind = _E(x, y, 0.40, -0.33, 0.37, 0.33, -0.70) * scallop
    tail = _E(x, y, 0.47, -0.80, 0.06, 0.17, -0.35)
    m = np.minimum(np.minimum(fore, hind), tail)
    inside = (m < 1) & (x > 0.05)

    lum = 0.74 + 0.14 * np.clip(1 - x, 0, 1)                # base, brighter at root
    lum = lum + 0.32 * np.clip(np.sin(5 * (x - 0.6 * y) - shimmer), 0, 1) ** 6   # shimmer
    vein = np.abs(np.sin(ang * 6.5 + 0.4)) < 0.085          # radiating veins
    lum = np.where(vein, 0.3, lum)
    disc = np.abs(_E(x, y, 0.33, 0.16, 0.18, 0.09, 0.35) - 1) < 0.2
    lum = np.where(disc, 0.3, lum)                           # cell vein
    band = m > 0.64
    lum = np.where(band, 0.36, lum)                          # dark border
    dots1 = band & (m > 0.71) & (m < 0.83) & (np.sin(ang * 16) > 0.62)
    dots2 = band & (m > 0.87) & (m < 0.95) & (np.sin(ang * 16 + math.pi) > 0.7)
    lum = np.where(dots1, 1.0, lum)
    lum = np.where(dots2, 0.9, lum)                          # white spots
    tip = (np.hypot(x - 0.83, y - 0.58) < 0.06) | (np.hypot(x - 0.95, y - 0.44) < 0.045)
    lum = np.where(tip & inside, 1.0, lum)
    lum = np.where(m > 0.97, 0.6, lum)                       # crisp rim
    return np.where(inside, np.clip(lum, 0, 1), 0.0)


def body_light(u, y):
    ax = np.abs(u)
    lum = np.zeros_like(u)
    abdomen = (ax / 0.055) ** 2 + ((y + 0.38) / 0.40) ** 2 < 1
    lum = np.where(abdomen, np.where(np.sin(y * 45) > 0.55, 0.55, 0.85), lum)
    thorax = (ax / 0.085) ** 2 + ((y - 0.10) / 0.13) ** 2 < 1
    lum = np.where(thorax, 0.95, lum)
    head = np.hypot(ax, y - 0.28) < 0.065
    lum = np.where(head, 1.0, lum)
    t = np.clip((y - 0.32) / 0.48, 0, 1)
    ant_x = 0.03 + 0.23 * t ** 1.6
    antenna = (y > 0.32) & (y < 0.8) & (np.abs(ax - ant_x) < 0.017)
    lum = np.where(antenna, np.maximum(lum, 0.75), lum)
    club = np.hypot(ax - 0.26, y - 0.82) < 0.036
    return np.where(club, 0.95, lum)


SUB = np.array([(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)])  # 2x2 samples


# --------------------------------------------------------------------- scene --
class Scene:
    def __init__(self, cols, rows, aspect):
        self.cols, self.rows, self.aspect = cols, rows, aspect      # aspect = cw/ch
        self.F = cols * 0.55
        self.ZM = 7.0
        self.cracks, self.flies, self.glitter = [], [], []
        self.stars = [(random.randrange(cols), random.randrange(rows), random.uniform(0, TAU))
                      for _ in range(cols * rows // 900)]
        gx = cols * random.uniform(0.58, 0.78)
        gy = rows * random.uniform(0.35, 0.55)
        self.add_crack(gx, gy, t0=2.0, n_flies=N_FLIES, big=True)

    def project(self, X, Y, Z):
        return (self.cols / 2 + X * self.F / Z,
                self.rows / 2 - Y * self.F * self.aspect / Z)

    def unproject(self, cx, cy, Z):
        return [(cx - self.cols / 2) * Z / self.F,
                -(cy - self.rows / 2) * Z / (self.F * self.aspect), Z]

    def add_crack(self, gx, gy, t0, n_flies, big=False):
        cr = make_crack(gx, gy, self.cols, self.rows, self.aspect, big)
        cr.update(t0=t0, cell=(gx, gy), gate=self.unproject(gx, gy, self.ZM))
        self.cracks.append(cr)
        base = len(self.flies)
        for j in range(n_flies):
            i = base + j
            z = random.uniform(3.2, 8.0)
            hx = 0.9 * z * (self.cols / 2) / self.F
            hy = 0.9 * z * (self.rows / 2) / (self.F * self.aspect)
            self.flies.append(dict(
                gate=cr["gate"],
                born=t0 + 0.9 + j * (0.6 if big else 0.35) + 0.15 * math.sin(i * 3.1),
                home=[(((i * GOLD * 2.3) % 1) - 0.5) * 2 * hx * 0.8,
                      (((i * 0.37 + 0.2) % 1) - 0.5) * 2 * hy * 0.7, z],
                w=[random.uniform(0.15, 0.32) for _ in range(3)],
                ph=[random.uniform(0, TAU) for _ in range(3)],
                reach=random.uniform(0.25, 0.45) * z * 0.6,
                size=random.uniform(0.5, 0.62) * BUTTERFLY_SIZE,
                beat=random.uniform(1.3, 1.9),
                tint=random.choice((0, 0, 1, 2, 3)),
                push=[0.0, 0.0]))

    def where(self, f, t):
        a = t - f["born"]
        w, ph, r, home, g = f["w"], f["ph"], f["reach"], f["home"], f["gate"]
        roam = [home[0] + math.sin(w[0] * t + ph[0]) * r * 1.6,
                home[1] + math.sin(w[1] * t + ph[1]) * r * 0.75,
                home[2] + math.sin(w[2] * t + ph[2]) * 1.0]
        u = smooth(a / 3.0)
        sw = math.sin(math.pi * u) * 0.6
        swirl = [math.cos(a * 2.2 + ph[0]) * sw, 0.0, math.sin(a * 2.2 + ph[0]) * sw]
        return [g[i] * (1 - u) + roam[i] * u + swirl[i] for i in range(3)]


def make_crack(cx, cy, cols, rows, asp, big):
    """A black hole with a jagged rim, and straight crack lines shooting out."""
    unit = max(cols, rows / asp)
    hole_r = unit * (0.04 if big else 0.028)
    reach = unit * (0.36 if big else 0.2)
    bumps = [random.uniform(0.7, 1.3) for _ in range(18)]

    def rim(a):
        i = (a % TAU) / TAU * 18
        k = int(i)
        p, q = bumps[k % 18], bumps[(k + 1) % 18]
        return hole_r * (p + (q - p) * (i - k))

    cells = {}

    def put(X, Y, d, b, ch):
        x, y = int(round(cx + X)), int(round(cy + Y * asp))
        if 0 <= x < cols and 0 <= y < rows:
            old = cells.get((x, y))
            if old is None or old[1] < b:
                cells[(x, y)] = (d, b, ch)

    n = random.randint(9, 13)
    for k in range(n):
        a = TAU * k / n + random.uniform(-0.22, 0.22)
        length = reach * random.uniform(0.4, 1.0)
        r = rim(a) + 0.6
        bend_at = length * random.uniform(0.4, 0.7)
        bent = False
        while r < length:
            if not bent and r > bend_at:
                a += random.uniform(-0.12, 0.12)
                bent = True
            b = 0.13 + 0.37 * math.exp(-(r - hole_r) / (reach * 0.35))
            if random.random() > 0.04:
                put(math.cos(a) * r, math.sin(a) * r, r, b, char_for(math.cos(a), math.sin(a)))
            r += 0.5
    items = sorted((d, x, y, b, ch) for (x, y), (d, b, ch) in cells.items())

    inside, rim_cells = [], []
    R = int(hole_r * 1.4) + 2
    for yy in range(int(cy - R * asp) - 1, int(cy + R * asp) + 2):
        for xx in range(int(cx - R) - 1, int(cx + R) + 2):
            if 0 <= xx < cols and 0 <= yy < rows:
                X, Y = xx - cx, (yy - cy) / asp
                r, a = math.hypot(X, Y), math.atan2(Y, X)
                edge = rim(a)
                if r < edge - 0.5:
                    inside.append((xx, yy, r / edge))
                elif r < edge + 0.5:
                    rim_cells.append((xx, yy, char_for(-math.sin(a), math.cos(a))))
    return dict(d=np.array([i[0] for i in items]),
                x=np.array([i[1] for i in items], dtype=int),
                y=np.array([i[2] for i in items], dtype=int),
                b=np.array([i[3] for i in items]),
                c=np.array([ord(i[4]) for i in items], dtype=np.int32),
                inside=inside, rim=rim_cells, hole_r=hole_r)


# ------------------------------------------------------------------- render --
def draw_butterfly(sc, f, t, a, sx, sy, z, ch, br, tn):
    """Render one butterfly as shaded ASCII into the grid. Returns its size in cells."""
    cols, rows, asp = sc.cols, sc.rows, sc.aspect
    grow = 0.25 + 0.75 * smooth(a / 1.0)
    S = f["size"] * grow * sc.F / z                     # cells per local unit
    phase = f["beat"] * a * TAU + f["ph"][0]
    flap = 0.5 + 0.5 * math.sin(phase)
    cth = math.cos(-0.1 + 1.3 * flap)                   # 1 = wings open flat
    light = (0.6 + 0.4 * max(cth, 0)) * (1.0 if z < 4 else max(0.55, 1 - (z - 4) * 0.1))
    sy += 0.25 * S * asp * 0.1 * math.cos(phase)        # bob

    p0, p1 = sc.where(f, t - 0.2), sc.where(f, t + 0.2)
    roll = math.atan2(p1[0] - p0[0] + f["push"][0] * 0.01, p1[1] - p0[1] + 0.35)
    roll = max(-0.45, min(0.45, roll))                  # stay mostly upright = readable
    cr, sr = math.cos(roll), math.sin(roll)

    R = S * 1.3
    x0, x1 = max(0, int(sx - R)), min(cols, int(sx + R) + 1)
    y0, y1 = max(0, int(sy - R * asp)), min(rows, int(sy + R * asp) + 1)
    if x1 <= x0 or y1 <= y0:
        return S
    gy, gx = np.mgrid[y0:y1, x0:x1]
    px = (gx[..., None] + SUB[:, 0] - sx) / S
    py = -(gy[..., None] + SUB[:, 1] - sy) / (S * asp)
    u = px * cr - py * sr
    v = (px * sr + py * cr) / 0.92                      # slight tilt away from us
    xw = np.abs(u) / max(cth, 0.07)
    lum = np.maximum(wing_light(xw, v, t * 2.3 + f["ph"][1]) * light, body_light(u, v) * light)
    lum = lum.mean(axis=2)                              # anti-aliased edges

    on = lum > 0.06
    if on.any():
        idx = np.clip((lum * (len(RAMP) - 1)).astype(int), 1, len(RAMP) - 1)
        ys, xs = np.nonzero(on)
        ch[ys + y0, xs + x0] = RAMP_CODES[idx[ys, xs]]
        br[ys + y0, xs + x0] = np.minimum(1.0, lum[ys, xs] * 1.05)
        tn[ys + y0, xs + x0] = f["tint"]

    # glitter shed from the wings
    if GLITTER > 0:
        for _ in range(int(2 * GLITTER + random.random())):
            side = random.choice((-1, 1))
            gxp = sx + side * S * random.uniform(0.3, 1.1) * max(cth, 0.2)
            gyp = sy + S * asp * random.uniform(-0.7, 0.7)
            sc.glitter.append([gxp, gyp, random.uniform(-0.08, 0.08), random.uniform(0.02, 0.1),
                               0.0, random.uniform(0.8, 1.6), f["tint"]])
    return S


def build_grid(sc, t, binary, mouse_cell):
    cols, rows = sc.cols, sc.rows
    ch = np.zeros((rows, cols), dtype=np.int32)
    br = np.zeros((rows, cols), dtype=np.float32)
    tn = np.zeros((rows, cols), dtype=np.int8)
    halos, portals = [], []

    for (x, y, p) in sc.stars:
        if math.sin(t * 1.1 + p) > 0.6:
            ch[y, x], br[y, x] = ord("."), 0.08

    for cr in sc.cracks:
        dt = t - cr["t0"]
        if dt < 0:
            continue
        prog = cr["hole_r"] + dt * 140
        n = np.searchsorted(cr["d"], prog)
        if n:
            ch[cr["y"][:n], cr["x"][:n]] = cr["c"][:n]
            fresh = np.clip(1 - (prog - cr["d"][:n]) / 20, 0, 1)
            br[cr["y"][:n], cr["x"][:n]] = cr["b"][:n] + fresh * 0.35
        open_ = smooth(dt / 0.35)
        pulse = 0.75 + 0.25 * math.sin(t * 2.0 + cr["cell"][0])
        for (x, y, rr) in cr["inside"]:
            if rr > open_:
                continue
            ch[y, x] = 0
            if rr < 0.18:
                c_, b_ = "O", 0.42
            elif rr < 0.32:
                c_, b_ = "o", 0.32
            elif rr < 0.48 and (x + y) % 2 == 0:
                c_, b_ = ":", 0.22
            elif rr < 0.62 and (x * 3 + y) % 4 == 0:
                c_, b_ = ".", 0.16
            else:
                continue
            ch[y, x], br[y, x] = ord(c_), b_ * pulse * open_
        if open_ > 0.05:
            for (x, y, c_) in cr["rim"]:
                ch[y, x], br[y, x] = ord(c_), 0.75 * open_
            portals.append((cr["cell"], cr["hole_r"] * 3.2, 0.6 * pulse * open_, 0))

    # butterflies, far ones first so near ones cover them
    mx, my = mouse_cell
    live = []
    for f in sc.flies:
        a = t - f["born"]
        if a < 0:
            continue
        pos = sc.where(f, t)
        z = max(2.2, pos[2])
        sx, sy = sc.project(pos[0], pos[1], z)
        dx, dy = sx + f["push"][0] - mx, (sy + f["push"][1] - my) / sc.aspect
        d = math.hypot(dx, dy)
        if 0.01 < d < 22 and a > 1.5:
            k = (22 - d) * 0.1
            f["push"][0] += dx / d * k
            f["push"][1] += dy / d * k * sc.aspect
        f["push"][0] *= 0.965
        f["push"][1] *= 0.965
        live.append((z, f, a, sx + f["push"][0], sy + f["push"][1]))
    live.sort(key=lambda e: -e[0])
    for z, f, a, sx, sy in live:
        S = draw_butterfly(sc, f, t, a, sx, sy, z, ch, br, tn)
        halos.append(((sx, sy), S * 2.6, 0.28 * (1.0 if z < 4 else max(0.5, 1 - (z - 4) * 0.12)), f["tint"]))

    # glitter:  . + * + .   (twinkles, drifts down, fades)
    keep = []
    for g in sc.glitter:
        g[0] += g[2]
        g[1] += g[3]
        g[4] += 1 / FPS
        x, y = int(g[0]), int(g[1])
        if g[4] < g[5] and 0 <= x < cols and 0 <= y < rows:
            ph = g[4] / g[5]
            if ch[y, x] == 0 or br[y, x] < 0.3:
                ch[y, x] = ord(TWINKLE[min(4, int(ph * 5))])
                br[y, x] = 0.4 + 0.6 * math.sin(math.pi * ph) * (0.7 + 0.3 * math.sin(g[4] * 25))
                tn[y, x] = 3 if random.random() < 0.5 else g[6]
            keep.append(g)
    sc.glitter = keep[-1200:]

    if binary:
        on = (ch != 0) & (br > 0.2)
        bits = np.where(br > 0.6, ord("1"), ord("0"))
        ch = np.where(on, bits, ch)

    return ch, br, tn, len(live), halos + portals


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
        n = 128
        yy, xx = np.mgrid[0:n, 0:n]
        r = np.hypot(xx - n / 2, yy - n / 2) / (n / 2)
        v = np.clip(1 - r, 0, 1) ** 2.2
        self.halo_base = {}
        for i, (cr, cg, cb) in enumerate(TINTS):
            arr = np.dstack([v * cr * 0.55, v * cg * 0.55, v * cb * 0.55]).astype(np.uint8)
            self.halo_base[i] = pygame.surfarray.make_surface(arr.transpose(1, 0, 2))
        self.halo_cache = {}

    def glyph(self, code, level, tint):
        key = (code, level, tint)
        g = self.cache.get(key)
        if g is None:
            g = self.font.render(chr(code), True, ink_colour(level / 15, tint))
            self.cache[key] = g
        return g

    def halo(self, tint, size, strength):
        key = (tint, size // 6, int(strength * 10))
        h = self.halo_cache.get(key)
        if h is None:
            s = max(4, (size // 6) * 6)
            h = pygame.transform.smoothscale(self.halo_base[tint], (s, int(s * 0.8)))
            k = int(255 * min(1.0, strength))
            h.fill((k, k, k), special_flags=pygame.BLEND_MULT)
            if len(self.halo_cache) > 400:
                self.halo_cache.clear()
            self.halo_cache[key] = h
        return h

    def draw(self, screen, ch, br, tn, fade, flash, shake, glows):
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
        for c, l, x, y, tt in zip(ch[ys, xs].tolist(), levels.tolist(), xs.tolist(),
                                  ys.tolist(), tn[ys, xs].tolist()):
            if l > 0:
                item = (self.glyph(c, l, tt), (x * cw, y * chh))
                seq.append(item)
                if l >= 11:
                    hot.append(item)
        blit = (lambda s, q: s.fblits(q)) if hasattr(self.layer, "fblits") else \
               (lambda s, q: s.blits(q, doreturn=False))
        blit(self.layer, seq)
        blit(self.bright, hot)

        off = (int(random.uniform(-shake, shake)), int(random.uniform(-shake, shake)))
        screen.fill((0, 0, 0))

        # soft coloured auras behind butterflies + light inside the holes
        for (gx, gy), size_cells, k, tint in glows:
            size = int(size_cells * cw)
            if size > 6 and k * fade > 0.02:
                hs = self.halo(tint, size, k * fade)
                screen.blit(hs, (int(gx * cw - hs.get_width() / 2) + off[0],
                                 int(gy * chh - hs.get_height() / 2) + off[1]),
                            special_flags=pygame.BLEND_ADD)

        screen.blit(self.layer, off, special_flags=pygame.BLEND_ADD)

        if GLOW > 0:                    # bloom from the brightest letters only
            s1 = pygame.transform.smoothscale(self.bright, (max(1, w // 5), max(1, h // 5)))
            s2 = pygame.transform.smoothscale(s1, (max(1, w // 14), max(1, h // 14)))
            s1.blit(pygame.transform.smoothscale(s2, s1.get_size()), (0, 0),
                    special_flags=pygame.BLEND_ADD)
            blur = pygame.transform.smoothscale(s1, (w, h))
            for _ in range(max(1, int(GLOW))):
                screen.blit(blur, off, special_flags=pygame.BLEND_ADD)

        if flash > 0:
            f = int(70 * flash)
            screen.fill((int(f * 0.8), int(f * 0.9), f), special_flags=pygame.BLEND_ADD)


def draw_hud(screen, ren, t, shown, letters, cracks, fps):
    w, h = screen.get_size()
    dim, pink = (110, 118, 128), (225, 110, 150)
    f = ren.hud
    lh = f.get_linesize()
    screen.blit(f.render(f"t {t:05.2f}s", True, pink), (w - 100, 8))
    for i, line in enumerate((f"{HANDLE} · 2026", f"butterflies {shown}",
                              f"letters {letters:,}", f"cracks {cracks}")):
        screen.blit(f.render(line, True, dim), (10, h - 26 - (4 - i) * lh))
    pygame.draw.line(screen, (30, 34, 40), (0, h - 22), (w, h - 22))
    screen.blit(f.render("py butterfly.py", True, dim), (6, h - 19))
    txt = f.render(f"running · {fps:.0f} fps", True, dim)
    screen.blit(txt, (w - txt.get_width() - 8, h - 19))


# --------------------------------------------------------------------- main --
def main():
    global CHARSET
    pygame.init()
    pygame.display.set_caption("butterfly.py")
    screen = pygame.display.set_mode(WINDOW, pygame.RESIZABLE)
    clock = pygame.time.Clock()
    ren = Renderer()

    def new_scene():
        w, h = screen.get_size()
        return Scene(w // ren.cw, (h - 90) // ren.ch, ren.cw / ren.ch), pygame.time.get_ticks()

    sc, start = new_scene()
    full = False
    while True:
        t = (pygame.time.get_ticks() - start) / 1000
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_q)):
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_F11, pygame.K_f):
                full = not full
                screen = pygame.display.set_mode((0, 0) if full else WINDOW,
                                                 pygame.FULLSCREEN if full else pygame.RESIZABLE)
                sc, start = new_scene()
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_b:
                CHARSET = "binary" if CHARSET == "letters" else "letters"
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                sc, start = new_scene()
            elif e.type == pygame.VIDEORESIZE and not full:
                screen = pygame.display.set_mode(e.size, pygame.RESIZABLE)
                sc, start = new_scene()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                cx, cy = e.pos[0] / ren.cw, e.pos[1] / ren.ch
                if cy < sc.rows:
                    sc.add_crack(cx, cy, t0=t, n_flies=N_PER_CLICK)

        if t > CYCLE_SECONDS + 1.5:
            sc, start = new_scene()
            t = 0.0
        fade = 1.0 if t < CYCLE_SECONDS else max(0.0, 1 - (t - CYCLE_SECONDS) / 1.5)

        dt = t - max((c["t0"] for c in sc.cracks if c["t0"] <= t), default=-9)
        flash = max(0.0, 1 - dt / 0.15) if dt >= 0 else 0.0
        shake = 5 * max(0.0, 1 - dt / 0.45) if dt >= 0 else 0.0

        mxp, myp = pygame.mouse.get_pos()
        mouse_cell = (mxp / ren.cw, myp / ren.ch) if pygame.mouse.get_focused() else (-999, -999)

        ch, br, tn, shown, glows = build_grid(sc, t, CHARSET == "binary", mouse_cell)
        ren.draw(screen, ch, br, tn, fade, flash, shake, glows)
        draw_hud(screen, ren, t, shown, int((ch != 0).sum()), len(sc.cracks), clock.get_fps())
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()