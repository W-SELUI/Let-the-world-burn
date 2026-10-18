#!/usr/bin/env python3
"""
CANDLE  -  a dark ASCII short film for your terminal.

Pitch black. A spark. A candle. It tips, it falls, the floor catches.
Everything burns, then dies down to embers.

    python3 candle_burn.py            play once (stays on the embers, Ctrl+C quits)
    python3 candle_burn.py --loop     replay forever
    python3 candle_burn.py --fps 30   change the frame rate

Needs: Python 3.8+, a 256-colour terminal, at least 70 x 24 characters.
Tip:   make the window big and the font small - the fire gets smoother.
       Screen-record it for your Reel.
"""
import math
import os
import random
import shutil
import sys
import time

FPS = 25

# ---------------------------------------------------------------- timeline (s)
T_SPARK = 1.0       # first spark on the wick (before this: pure black)
T_LIT0 = 1.8        # flame starts to grow
T_LIT1 = 4.2        # flame fully alive
T_TIP0 = 7.4        # the candle starts to tip
TIP_DUR = 1.5
TIP_ANGLE = math.radians(70)
BURN_HOLD = 6.5     # seconds of full inferno after impact
FADE_DUR = 5.0      # seconds for the fire to die down to embers
END_HOLD = 4.0      # extra embers before --loop restarts
GRAVITY = 40.0      # rows / s^2
COOL_FLAME = 64     # cooling of the small candle flame (higher = shorter)

# ---------------------------------------------------------------- palettes
WARM = [16, 52, 52, 88, 88, 94, 130, 130, 166, 172, 208, 214, 220, 222]   # light ramp
LR = " .:-=+*#%@"                                                          # light chars
FCH_A = " .:;+*x#%@"        # fire chars (two sets, picked at random per cell
FCH_B = " ,.:+x*%#&"        # per frame -> the flame shimmers)
FCO = [0, 52, 88, 124, 160, 196, 202, 208, 214, 226]
SPARK_CO = [52, 88, 124, 160, 196, 202, 208, 214, 220, 226]
SMOKE_CO = [234, 235, 236, 237, 238, 240]
EMBER = [(0.88, '@', 208), (0.72, '@', 202), (0.55, '#', 196), (0.40, '%', 160),
         (0.27, '*', 124), (0.15, ':', 88), (0.07, '.', 52)]


def lerp(a, b, k):
    return a + (b - a) * k


class Scene:
    def __init__(self, W, H):
        self.W, self.H = W, H

        # ---- layout
        self.gy = H - max(2, H // 10)                        # first ground row
        self.sr = self.gy - max(9, int(self.gy * 0.45))      # the ledge the candle stands on
        self.cx = int(W * 0.42)
        self.BH = 12 if H >= 30 else 10                      # candle height
        self.HW = 3.5                                        # candle half width
        self.pvx = self.cx + 4                               # tipping pivot (ledge edge)
        self.pvy = float(self.sr)
        self.lx0, self.lx1 = self.cx - 10, self.cx + 4       # ledge span

        # ---- fire simulation
        self.heat = [[0] * W for _ in range(H)]
        pool = max(4096, W * 6)
        self.pdx = [random.choice((-1, 0, 0, 1)) for _ in range(pool)]
        self.pdc = [random.randrange(256) for _ in range(pool)]
        self.pdx_n = [random.choice((-1, 0, 0, 0, 0, 0, 0, 1)) for _ in range(pool)]
        self.pdc_n = [random.randrange(70, 256) for _ in range(pool)]
        self.ig = [0.0] * W                                  # ground ignition 0..1
        self.jit = [random.random() * 3.0 for _ in range(W)]
        self.ph = [[random.random() * 6.283 for _ in range(W)] for _ in range(H)]
        self.fire_cool = int(max(6, 2 * 215 / max(8.0, self.gy * 1.25)))

        # ---- candle state
        self.phase = 'table'
        self.th = 0.0
        self.ox, self.oy = self.cx + 0.5, float(self.sr)
        self.w = self.alpha = self.vx = self.vy = 0.0
        self.t = 0.0
        self.fi = 0.0
        self.flick = 0.5
        self.t_land = None
        self.t_fade = None
        self.burn = 1.0
        self.ix = self.cx
        self.shake = 0.0
        self.parts = []
        self.tip = (self.cx + 0.5, self.sr - 7.0)

    # ------------------------------------------------------------ geometry
    def low_off(self, th):
        s, c = math.sin(th), math.cos(th)
        return max((u * s - v * c) / 2.0
                   for u in (-self.HW, self.HW) for v in (0, self.BH))

    def tip_pos(self):
        v = self.BH + 2.0
        s, c = math.sin(self.th), math.cos(self.th)
        return self.ox + v * s, self.oy - v * c / 2.0

    def finished(self):
        return self.t_fade is not None and self.t > self.t_fade + FADE_DUR + END_HOLD

    # ------------------------------------------------------------ candle motion
    def _pivot_pose(self, th):
        self.th = th
        self.ox = self.pvx - self.HW * math.cos(th)
        self.oy = self.pvy - (self.HW / 2.0) * math.sin(th)

    def _candle(self, dt):
        t = self.t
        if self.phase == 'table':
            if t < T_TIP0 - 0.8:
                th = 0.0
            elif t < T_TIP0:
                k = (t - (T_TIP0 - 0.8)) / 0.8
                th = 0.09 * k * abs(math.sin(t * 30))        # nervous wobble
            else:
                s = min(1.0, (t - T_TIP0) / TIP_DUR)
                th = TIP_ANGLE * s * s
            self._pivot_pose(th)
            if t >= T_TIP0 + TIP_DUR:
                self.phase = 'fall'
                self.w = 2 * TIP_ANGLE / TIP_DUR
                self.vx, self.vy = 3.0, 0.0
                dist = max(1.0, self.gy - self.oy - 1.8)
                tf = math.sqrt(2 * dist / GRAVITY)
                need = self.th + self.w * tf + 0.5 * 3.0 * tf * tf
                k = math.ceil((need - math.pi / 2) / math.pi)
                target = math.pi / 2 + k * math.pi            # land lying flat
                self.alpha = 2 * (target - self.th - self.w * tf) / (tf * tf)
        elif self.phase == 'fall':
            self.w += self.alpha * dt
            self.th += self.w * dt
            self.vy += GRAVITY * dt
            self.oy += self.vy * dt
            self.ox += self.vx * dt
            if self.oy + self.low_off(self.th) >= self.gy:
                self.phase = 'land'
                self.t_land = t
                self.lt = 0.0
                self.th0 = self.th
                k = round((self.th - math.pi / 2) / math.pi)
                self.tgt = math.pi / 2 + k * math.pi
                self.vxs = self.vx * 0.7
                self.oy = self.gy - self.low_off(self.th)
                self.ix = self.tip_pos()[0]
                self.shake = 1.0
                for _ in range(40):                           # impact burst
                    a = random.uniform(math.pi * 1.05, math.pi * 1.95)
                    sp = random.uniform(8, 24)
                    life = random.uniform(0.6, 1.6)
                    self.parts.append([self.ix, self.gy - 1, math.cos(a) * sp * 1.4,
                                       math.sin(a) * sp * 0.8, life, life, 'e'])
        else:  # land
            self.lt += dt
            k = min(1.0, self.lt / 0.25)
            e = k * k * (3 - 2 * k)
            self.th = self.th0 + (self.tgt - self.th0) * e
            self.ox += self.vxs * dt
            self.vxs *= math.exp(-5 * dt)
            lift = 1.4 * math.sin(math.pi * self.lt / 0.4) if self.lt < 0.4 else 0.0
            self.oy = self.gy - self.low_off(self.th) - lift

    # ------------------------------------------------------------ particles
    def _spawn(self, dt):
        R = random
        W, gy = self.W, self.gy
        tx, ty = self.tip
        if self.fi > 0.4 and R.random() < (0.10 if self.t_land is None else 0.04):
            self.parts.append([tx, ty - 2, R.uniform(-1.5, 1.5), -R.uniform(2, 6),
                               1.5, 1.5, 'e'])
        if self.t_land is not None:
            cols = [x for x in range(W) if self.ig[x] > 0.5]
            if cols:
                n = (sum(self.ig) / W) * max(self.burn, 0.10) * W * 0.07
                cnt = int(n) + (1 if R.random() < n - int(n) else 0)
                for _ in range(cnt):
                    x = R.choice(cols) + R.random()
                    life = R.uniform(1.0, 2.8)
                    self.parts.append([x, gy - R.random() * 3, R.uniform(-3, 3),
                                       -R.uniform(4, 15), life, life, 'e'])
                if self.t_fade is not None:
                    sm = max(4 * self.burn * (1 - self.burn), 0.18)
                    n = sm * W * 0.03
                    cnt = int(n) + (1 if R.random() < n - int(n) else 0)
                    for _ in range(cnt):
                        x = R.choice(cols) + R.random()
                        life = R.uniform(2.0, 4.5)
                        self.parts.append([x, gy - 1, R.uniform(-0.6, 0.6),
                                           -R.uniform(1.0, 2.6), life, life, 's'])

    def _move_parts(self, dt):
        keep = []
        W, H = self.W, self.H
        for p in self.parts:
            p[4] -= dt
            if p[4] <= 0:
                continue
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            if p[6] == 'e':
                p[3] += 6.0 * dt                              # sparks arc back down a bit
            p[2] += (random.random() - 0.5) * 6 * dt
            if 0 <= p[0] < W and 0 <= p[1] < H:
                keep.append(p)
        self.parts = keep

    # ------------------------------------------------------------ main step
    def step(self, dt):
        R = random
        W, H, gy = self.W, self.H, self.gy
        self.t += dt
        t = self.t

        if t < T_LIT0:
            self.fi = 0.0
        else:
            x = min(1.0, (t - T_LIT0) / (T_LIT1 - T_LIT0))
            self.fi = x * x * (3 - 2 * x)
        self.flick = 0.6 * self.flick + 0.4 * R.random()
        self.shake *= 0.86

        if self.t_land is not None and self.t_fade is None and t >= self.t_land + BURN_HOLD:
            self.t_fade = t
        if self.t_fade is None:
            self.burn = 1.0
        else:
            k = min(1.0, (t - self.t_fade) / FADE_DUR)
            self.burn = (1 - k) ** 1.6

        self._candle(dt)
        self.tip = self.tip_pos()

        # ground fire spread
        cool = COOL_FLAME
        if self.t_land is not None:
            tt = t - self.t_land
            r = 1.5 + 6.5 * tt + 14 * tt * tt
            ix, ig, jit = self.ix, self.ig, self.jit
            for x in range(W):
                if abs(x + 0.5 - ix) + jit[x] <= r:
                    v = ig[x] + dt * 2.2
                    ig[x] = 1.0 if v > 1.0 else v
            kf = min(1.0, tt / 2.2)
            cool = lerp(COOL_FLAME, self.fire_cool, kf) + (1 - self.burn) * 45

        # heat rises, cools and drifts sideways
        old = self.heat
        if self.t_land is None:
            pdx, pdc = self.pdx_n, self.pdc_n                 # calm candle flame
        else:
            pdx, pdc = self.pdx, self.pdc                     # wild fire
        top = len(pdx) - W - 1
        cool = int(cool)
        rr = random.randrange
        new = []
        for y in range(H):
            if y >= gy:
                new.append([0] * W)
            else:
                bp = [0] + old[y + 1] + [0]
                o = rr(top)
                new.append([v if (v := bp[i + 1 + d] - ((c * cool) >> 8)) > 0 else 0
                            for i, (d, c) in enumerate(zip(pdx[o:o + W], pdc[o:o + W]))])
        self.heat = new

        # sources: the candle flame ...
        fl = self.fi * (0.8 + 0.2 * self.flick) * (self.burn if self.t_land else 1.0)
        tx, ty = self.tip
        sx = int(math.floor(tx + (R.random() - 0.5) * 0.9))
        sy = int(math.floor(ty)) - 1
        if 0 <= sy < H:
            if self.fi > 0:
                v = int(255 * fl)
                for dx, k in ((0, 1.0), (-1, 0.55), (1, 0.55)):
                    if 0 <= sx + dx < W:
                        vv = int(v * k)
                        if vv > new[sy][sx + dx]:
                            new[sy][sx + dx] = vv
            elif t >= T_SPARK and 0 <= sx < W and R.random() < 0.55:
                new[sy][sx] = int(35 + R.random() * 100)      # the spark before it catches
        # ... and the burning ground (tongues of fire that rise and fall)
        if self.t_land is not None:
            row = new[gy]
            b = self.burn
            sin = math.sin
            for x in range(W):
                g = self.ig[x]
                if g > 0:
                    tongue = 0.72 + 0.28 * sin(x * 0.37 + t * 3.1) * sin(x * 0.11 - t * 1.9)
                    v = int(255 * g * b * tongue * (0.8 + 0.2 * R.random()))
                    if v > row[x]:
                        row[x] = v

        self._spawn(dt)
        self._move_parts(dt)

    # ------------------------------------------------------------ drawing
    def render(self):
        W, H, gy, sr, t = self.W, self.H, self.gy, self.sr, self.t
        heat, ig, burn = self.heat, self.ig, self.burn
        landed = self.t_land is not None
        pdc = self.pdc
        top = len(pdc) - W - 1
        rr = random.randrange
        sin = math.sin

        ch = [[' '] * W for _ in range(H)]
        co = [[0] * W for _ in range(H)]

        # flame light
        fx, fy = self.tip[0], self.tip[1] - 1.5
        fs = self.fi * (0.75 + 0.25 * self.flick) * (burn if landed else 1.0)

        def lightf(x, y):
            dx = (x + 0.5 - fx) / 24.0
            dy = (y + 0.5 - fy) / 12.0
            d2 = dx * dx + dy * dy
            if d2 >= 1.0:
                return 0.0
            b = 1.0 - d2
            return b * b * fs

        def lit(x, y):
            L = lightf(x, y)
            if landed:
                gl = ig[x] * max(0.0, 1.0 - (gy - y) / (0.85 * gy + 1)) * (0.25 + 0.75 * burn)
                hm = heat[y][x]
                if y + 1 < H and heat[y + 1][x] > hm:
                    hm = heat[y + 1][x]
                if y > 0 and heat[y - 1][x] > hm:
                    hm = heat[y - 1][x]
                L += gl * 0.9 + hm * 0.6 / 255.0
            return L

        def put(x, y, L):
            if L >= 0.035:
                ch[y][x] = LR[min(9, int(L * 10))]
                co[y][x] = WARM[min(13, int(L * 14))]
                return True
            return False

        # the air near the flame: faint specks revealed by the light
        if fs > 0.03:
            x0, x1 = max(0, int(fx - 25)), min(W, int(fx + 26))
            y0, y1 = max(0, int(fy - 13)), min(H, int(fy + 14))
            for y in range(y0, y1):
                o = rr(top)
                for x in range(x0, x1):
                    b = lightf(x, y)
                    if b > 0.03 and pdc[o + x] < b * 70:
                        ch[y][x] = '.'
                        co[y][x] = WARM[min(5, 1 + int(b * 6))]

        # ground: invisible until the light (or the fire) reaches it
        ember = [g * (0.12 + 0.88 * burn) for g in ig] if landed else None
        for y in range(gy, H):
            depth = (y - gy) / max(1, H - gy)
            ph = self.ph[y]
            for x in range(W):
                e = 0.0
                if ember is not None and ember[x] > 0.01:
                    e = ember[x] * (1.0 - 0.45 * depth) * (
                        0.55 + 0.25 * sin(t * 3.2 + ph[x]) + 0.2 * sin(t * 7.1 + ph[x] * 3.7))
                if e > 0.07:
                    for thr, c_, k_ in EMBER:
                        if e >= thr:
                            ch[y][x], co[y][x] = c_, k_
                            break
                else:
                    put(x, y, lit(x, y) * (1.0 - 0.5 * depth))

        occ = set()

        # the ledge (only seen by firelight)
        for x in range(self.lx0, self.lx1):
            for y in (sr, sr + 1):
                L = lit(x, y) * (1.0 if y == sr else 0.6)
                if put(x, y, L):
                    occ.add((x, y))

        # the candle, softly shaded (rotated + rasterised)
        ox, oy, th = self.ox, self.oy, self.th
        s, c = math.sin(th), math.cos(th)
        BH, HW = self.BH, self.HW
        x0, x1 = max(0, int(ox - 17)), min(W, int(ox + 18))
        y0, y1 = max(0, int(oy - 10)), min(H, int(oy + 10))
        for y in range(y0, y1):
            Y = 2.0 * (oy - y - 0.5)
            for x in range(x0, x1):
                X = x + 0.5 - ox
                u = X * c - Y * s
                v = X * s + Y * c
                au = abs(u)
                if au <= HW and 0 <= v <= BH:
                    shade = 1.0 - 0.45 * (au / HW) ** 2
                elif au <= 0.7 and BH < v <= BH + 1.8:
                    shade = 0.9
                else:
                    continue
                if put(x, y, lit(x, y) * shade):
                    occ.add((x, y))

        # ---- fire: soft (blurred) so it reads as light, not as text
        any_heat = False
        hb = []
        for y in range(0, min(H, gy + 1)):
            row = heat[y]
            if max(row) < 8:
                hb.append(None)
                continue
            any_heat = True
            p = [0] + row + [0]
            hb.append([min(255, ((p[i] + 2 * p[i + 1] + p[i + 2]) * 85) >> 8)
                       for i in range(W)])
        if any_heat:
            # wider blur for the halo of light around the fire
            zero = [0] * W
            h2 = []
            for r_ in hb:
                if r_ is None:
                    h2.append(zero)
                else:
                    p = [0, 0] + r_ + [0, 0]
                    h2.append([(p[i] + p[i + 1] * 2 + p[i + 2] * 3 + p[i + 3] * 2 + p[i + 4]) // 9
                               for i in range(W)])
            n = len(h2)
            for y in range(n):
                r_ = hb[y]
                if r_ is None and max(h2[y]) < 4 and (y == 0 or max(h2[y - 1]) < 4) \
                        and (y + 1 >= n or max(h2[y + 1]) < 4):
                    continue
                cy, ky = ch[y], co[y]
                a = h2[y - 1] if y > 0 else zero
                b_ = h2[y]
                d_ = h2[y + 1] if y + 1 < n else zero
                o = rr(top)
                for x in range(W):
                    v = r_[x] if r_ is not None else 0
                    if v >= 26:
                        bnd = (v * 10) >> 8
                        if bnd < 3 and (x, y) in occ:
                            continue
                        bit = pdc[o + x] & 1
                        cy[x] = FCH_B[bnd] if bit else FCH_A[bnd]
                        ky[x] = FCO[bnd]
                    else:
                        gv = (a[x] + 2 * b_[x] + d_[x]) >> 2     # halo glow
                        if gv >= 5 and pdc[o + x] < gv * 6 and cy[x] == ' ':
                            cy[x] = '.' if gv < 22 else ':'
                            ky[x] = 52 if gv < 18 else 88

        # sparks + smoke
        for p in self.parts:
            ix, iy = int(p[0]), int(p[1])
            if 0 <= ix < W and 0 <= iy < H:
                r = max(0.0, min(1.0, p[4] / p[5]))
                if p[6] == 'e':
                    ch[iy][ix] = '*' if r > 0.55 else ('+' if r > 0.25 else '.')
                    co[iy][ix] = SPARK_CO[min(9, int(r * 9.99))]
                else:
                    ch[iy][ix] = '.' if r < 0.5 else ':'
                    co[iy][ix] = SMOKE_CO[min(5, int(r * 5.99))]

        # camera shake on impact
        if self.shake > 0.06:
            sdx = int(round(random.uniform(-1, 1) * self.shake * 3))
            sdy = int(round(random.uniform(-1, 1) * self.shake * 1.5))
            if sdx or sdy:
                ch, co = self._shift(ch, co, sdx, sdy)
        return ch, co

    def _shift(self, ch, co, dx, dy):
        W, H = self.W, self.H
        blank_c, blank_k = [' '] * W, [0] * W
        nch, nco = [], []
        for y in range(H):
            sy = y - dy
            if 0 <= sy < H:
                rc, rk = ch[sy], co[sy]
                if dx > 0:
                    rc, rk = [' '] * dx + rc[:W - dx], [0] * dx + rk[:W - dx]
                elif dx < 0:
                    rc, rk = rc[-dx:] + [' '] * (-dx), rk[-dx:] + [0] * (-dx)
                nch.append(rc)
                nco.append(rk)
            else:
                nch.append(blank_c[:])
                nco.append(blank_k[:])
        return nch, nco

    def frame_string(self):
        ch, co = self.render()
        out = ["\x1b[H\x1b[48;5;16m"]
        for y in range(self.H):
            row = []
            prev = -1
            cy, ky = ch[y], co[y]
            for x in range(self.W):
                g = cy[x]
                if g != ' ' and ky[x] != prev:
                    prev = ky[x]
                    row.append("\x1b[38;5;%dm" % prev)
                row.append(g)
            out.append("".join(row))
        return "\n".join(out)

    def plain(self):
        ch, _ = self.render()
        return "\n".join("".join(r) for r in ch)


# ---------------------------------------------------------------- runner
def main():
    args = sys.argv[1:]
    loop = '--loop' in args
    fps = FPS
    if '--fps' in args:
        try:
            fps = float(args[args.index('--fps') + 1])
        except (IndexError, ValueError):
            pass
    size = shutil.get_terminal_size((100, 32))
    W, H = size.columns - 1, size.lines - 1
    if W < 70 or H < 24:
        print("Terminal too small (%dx%d). Please enlarge it to at least 71x25." %
              (size.columns, size.lines))
        return
    if os.name == 'nt':
        os.system('')                     # enables ANSI escapes on Windows 10+
    out = sys.stdout
    out.write("\x1b[?1049h\x1b[?25l\x1b[48;5;16m\x1b[2J")
    try:
        scene = Scene(W, H)
        dt = 1.0 / fps
        nxt = time.perf_counter()
        while True:
            scene.step(dt)
            out.write(scene.frame_string())
            out.flush()
            if loop and scene.finished():
                scene = Scene(W, H)
            nxt += dt
            wait = nxt - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            else:
                nxt = time.perf_counter()
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        out.flush()


if __name__ == "__main__":
    main()