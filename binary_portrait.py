"""
Binary Portrait - rebuilds your photo live out of tiny 0s and 1s, then scans it into place.

How to use:
  1. Put a photo in this folder named  me.jpg  (or me.png)
  2. In VS Code's terminal run:   python binary_portrait.py   (or:  py binary_portrait.py)
  3. Watch it render. An MP4 (1080x1920, ready for reels/stories) is saved in the "renders" folder.

Keys:  Esc = quit   Space = play again (records a new video)
"""

import datetime
import math
import os
import random
import subprocess
import sys

import numpy as np
import pygame

HERE = os.path.dirname(os.path.abspath(__file__))   # the folder this file is in
W, H = 1080, 1920            # story size
FPS = 60
CELL_W, CELL_H = 12, 15      # size of one digit
TOP, BOTTOM = 80, 96         # room for the terminal lines

# timeline (seconds)
T_INTRO, T_NOISE, T_EMERGE, T_CALIB, T_SCAN, T_HOLD = 1.5, 1.3, 4.8, 0.9, 2.4, 2.6
A1 = T_INTRO
A2 = A1 + T_NOISE
A3 = A2 + T_EMERGE
A4 = A3 + T_CALIB
A5 = A4 + T_SCAN
END = A5 + T_HOLD

LEVELS = 32                  # brightness steps for the digits


def find_photo():
    for name in ("me.jpg", "me.jpeg", "me.png", "me.webp", "me.JPG", "me.PNG"):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            return p
    return None


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


class Portrait:
    def __init__(self, photo_path):
        self.cols = W // CELL_W
        self.rows = (H - TOP - BOTTOM) // CELL_H
        self.ox = (W - self.cols * CELL_W) // 2
        self.oy = TOP + ((H - TOP - BOTTOM) - self.rows * CELL_H) // 2
        self.n = self.cols * self.rows
        self.name = os.path.basename(photo_path)
        self.load_photo(photo_path)
        self.make_glyphs()
        idx = np.arange(self.n)
        self.r = idx // self.cols
        self.c = idx % self.cols
        self.pos = [(self.ox + int(c) * CELL_W, self.oy + int(r) * CELL_H) for r, c in zip(self.r, self.c)]
        self.row_y = self.r / self.rows
        self.reset()

    # ---------- the photo -> brightness + colour for every digit ----------
    def load_photo(self, path):
        img = pygame.image.load(path).convert()
        iw, ih = img.get_size()
        cr = self.cols * CELL_W / (self.rows * CELL_H)       # crop the photo to the grid's shape (cover)
        if iw / ih > cr:
            sw, sh = int(ih * cr), ih
        else:
            sw, sh = iw, int(iw / cr)
        crop = img.subsurface(pygame.Rect((iw - sw) // 2, (ih - sh) // 2, sw, sh)).copy()
        small = pygame.transform.smoothscale(crop, (self.cols, self.rows))
        rgb = pygame.surfarray.array3d(small).transpose(1, 0, 2).reshape(-1, 3).astype(np.float32)
        lum = 0.6 * (rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)) / 255 + 0.4 * rgb.max(1) / 255
        lo, hi = np.percentile(lum, 2), np.percentile(lum, 98)
        v = np.clip((lum - lo) / max(0.05, hi - lo), 0, 1)
        self.target = v ** 1.1
        # colours, lifted a little so dark areas still show their colour
        m = np.maximum(rgb.max(1, keepdims=True), 1)
        boost = np.minimum(3.0, 255 / m)
        col = np.clip(rgb * boost * 0.82 + 46, 0, 255).astype(np.uint8).reshape(self.rows, self.cols, 3)   # vivid + a touch of light
        cs = pygame.surfarray.make_surface(col.transpose(1, 0, 2))
        cs = pygame.transform.scale(cs, (self.cols * CELL_W, self.rows * CELL_H))   # sharp blocks, one per digit
        self.colour = pygame.Surface((W, H))
        self.colour.fill((0, 0, 0))
        self.colour.blit(cs, (self.ox, self.oy))
        # focus point for the ending push-in: centre of the brightest area (usually the face)
        vv = self.target.reshape(self.rows, self.cols)
        wts = np.where(vv > np.percentile(vv, 80), vv, 0)
        if wts.sum() > 0:
            ys, xs = np.mgrid[0:self.rows, 0:self.cols]
            self.focus = (self.ox + (xs * wts).sum() / wts.sum() * CELL_W, self.oy + (ys * wts).sum() / wts.sum() * CELL_H)
        else:
            self.focus = (W / 2, H * 0.42)

    def make_glyphs(self):
        font = None
        for name in ("consolas", "cascadiamono", "dejavusansmono", "couriernew"):
            if pygame.font.match_font(name):
                font = pygame.font.SysFont(name, 16, bold=True)
                break
        font = font or pygame.font.Font(None, 19)
        self.glyph = []
        for ch in "01":
            base = font.render(ch, True, (255, 255, 255), (0, 0, 0))
            row = []
            for k in range(LEVELS + 1):
                g = base.copy()
                lv = int(255 * k / LEVELS)
                g.fill((lv, lv, lv), special_flags=pygame.BLEND_RGB_MULT)
                row.append(g)
            self.glyph.append(row)
        # trim every glyph to exactly one cell so digits never overlap -> plain (fast) blits
        gw, gh = base.get_size()
        cx, cy = (gw - CELL_W) // 2, (gh - CELL_H) // 2
        for row in self.glyph:
            for k, g in enumerate(row):
                cell = pygame.Surface((CELL_W, CELL_H)); cell.fill((0, 0, 0))
                cell.blit(g, (-cx, -cy))
                row[k] = cell
        self.gofs = (0, 0)

    def reset(self):
        self.delay = np.random.rand(self.n).astype(np.float32) * 0.55 + (1 - self.target) * 0.35
        self.digit = (np.random.rand(self.n) < 0.5).astype(np.int8)
        self.sparks = []

    # ---------- one frame ----------
    def digits_frame(self, t, surf, flash_surf):
        n = self.n
        noise_amt = max(0.0, 1 - max(0.0, (t - A2) / (T_EMERGE * 0.9)))
        fade_in = smooth((t - (A1 - 0.2)) / 0.6)
        emerge = smooth((t - A2) / T_EMERGE)
        scan = (t - A4) / T_SCAN if t >= A4 else -1.0
        done = t >= A5

        flips = 0.003 if done else 0.02 + 0.18 * noise_amt
        flip = np.random.rand(n) < flips
        k = np.clip((emerge * 1.4 - self.delay) / 0.45, 0, 1)
        k = k * k * (3 - 2 * k)
        v = (0.06 + np.random.rand(n).astype(np.float32) * 0.5 * noise_amt) * (1 - k) + self.target * k
        flash = None
        if scan >= 0:
            locked = self.row_y < scan
            v = np.where(locked, self.target, v)
            ahead = (self.row_y >= scan) & (self.row_y < scan + 0.05) & (scan < 1)
            flip |= ahead & (np.random.rand(n) < 0.35)                          # digits jitter right before the beam
            v = np.where(ahead, np.clip(v + (np.random.rand(n) - 0.3) * 0.35, 0, 1), v)
            burn = (scan - self.row_y)                                           # rows just passed flash white, then cool
            flash = np.where(locked & (burn < 0.06), 1 - burn / 0.06, 0) * (1.0 if scan < 1.1 else 0)
        self.digit ^= flip.astype(np.int8)
        v = v * fade_in
        lvl = np.clip((v * LEVELS).astype(np.int32), 0, LEVELS)

        surf.fill((0, 0, 0))
        idx = np.nonzero(lvl >= 2)[0]
        g, pos, dg = self.glyph, self.pos, self.digit
        lv = lvl.tolist(); dl = dg.tolist()
        surf.fblits([(g[dl[i]][lv[i]], pos[i]) for i in idx.tolist()])
        surf.blit(self.colour, (0, 0), special_flags=pygame.BLEND_RGB_MULT)     # real colours
        if flash is not None:
            fl = np.clip((flash * 0.85 * (v > 0.03) * LEVELS).astype(np.int32), 0, LEVELS)
            fi = np.nonzero(fl >= 1)[0]
            if len(fi):
                fll = fl.tolist()
                surf.fblits([(g[dl[i]][fll[i]], pos[i]) for i in fi.tolist()], pygame.BLEND_RGB_ADD)
        return scan


def make_beam():
    """the scan light: white-hot core, long soft glow trailing above, short glow below"""
    h = 200
    beam = pygame.Surface((W, h))
    beam.fill((0, 0, 0))
    core = 150
    for y in range(h):
        d = y - core
        if d < 0:
            a = math.exp(d / 38.0) * 0.55
        else:
            a = math.exp(-d / 9.0) * 0.8
        if abs(d) <= 1:
            a = 1.0
        beam.fill((int(255 * min(1, a * 0.85)), int(255 * min(1, a * 0.95)), int(255 * min(1, a))), pygame.Rect(0, y, W, 1))
    # fade towards the left/right edges a touch
    edge = pygame.Surface((W, h))
    for x in range(W):
        e = 0.55 + 0.45 * math.sin(math.pi * x / W)
        lv = int(255 * e)
        edge.fill((lv, lv, lv), pygame.Rect(x, 0, 1, h))
    beam.blit(edge, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return beam, core


def make_scanlines():
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for y in range(0, H, 4):
        s.fill((0, 0, 0, 34), pygame.Rect(0, y, W, 2))
    return s


def mono(size, bold=False):
    for name in ("consolas", "cascadiamono", "dejavusansmono", "couriernew"):
        if pygame.font.match_font(name):
            return pygame.font.SysFont(name, size, bold=bold)
    return pygame.font.Font(None, int(size * 1.3))


RAW_FMT = None


def raw_format(surface):
    """the pixel layout pygame already uses, so frames go to the encoder without converting"""
    masks = surface.get_masks()[:3]
    if surface.get_bytesize() == 4 and surface.get_pitch() == surface.get_width() * 4:
        if masks == (0xFF0000, 0xFF00, 0xFF):
            return "bgr0"
        if masks == (0xFF, 0xFF00, 0xFF0000):
            return "rgb0"
    return None


def open_video(fmt=None):
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None, None
    out_dir = os.path.join(HERE, "renders")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"binary-portrait-{datetime.datetime.now():%Y%m%d-%H%M%S}.mp4")
    cmd = [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", fmt or "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", out]
    flags = 0x08000000 if sys.platform == "win32" else 0          # no extra console window on Windows
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, creationflags=flags)
    except Exception:
        return None, None
    return proc, out


def run(record=True, max_frames=None, frame_hook=None):
    pygame.init()
    info = pygame.display.Info()
    wh = int(min(info.current_h * 0.88, 1000)) if info.current_h > 0 else 960
    win = pygame.display.set_mode((int(wh * 9 / 16), wh))
    pygame.display.set_caption("Binary Portrait")
    photo = find_photo()
    if not photo:
        f = mono(20)
        win.fill((4, 5, 6))
        for i, line in enumerate(["no photo found.", "", "put a photo named  me.jpg", "in the same folder as this program,",
                                  "then run it again.", "", "press any key to close"]):
            win.blit(f.render(line, True, (180, 200, 210)), (24, 40 + i * 30))
        pygame.display.flip()
        while True:
            e = pygame.event.wait()
            if e.type in (pygame.QUIT, pygame.KEYDOWN):
                pygame.quit(); return None

    pt = Portrait(photo)
    beam, core = make_beam()
    scanlines = make_scanlines()
    f_top, f_bot, f_tag = mono(24), mono(22), mono(17)
    frame = pygame.Surface((W, H)).convert()
    clock = pygame.time.Clock()
    saved = None

    while True:                                       # one loop = one full render (Space plays again)
        pt.reset()
        fmt = raw_format(frame)
        proc, out = open_video(fmt) if record else (None, None)
        total = int(END * FPS)
        for fi in range(total):
            if max_frames and fi >= max_frames:
                break
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    if proc:
                        proc.stdin.close(); proc.wait()
                    pygame.quit(); return out
            t = fi / FPS
            frame.fill((4, 5, 6))

            # ---- digits ----
            scan = -1.0
            if t > A1 - 0.2:
                scan = pt.digits_frame(t, frame, None)
                # soft glow (bloom) around bright digits: blurred at a small size, then stretched back up
                small = pygame.transform.smoothscale(frame, (W // 6, H // 6))
                small.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_MULT)
                glow = pygame.transform.scale(pygame.transform.smoothscale(small, (W // 2, H // 2)), (W, H))
                frame.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

            gy0, gy1 = pt.oy, pt.oy + pt.rows * CELL_H
            # ---- calibration pass: a faint quick sweep down and back up ----
            if A3 <= t < A4:
                k = (t - A3) / T_CALIB
                y = gy0 + (gy1 - gy0) * (k / 0.55 if k < 0.55 else 1 - (k - 0.55) / 0.45)
                dim = beam.copy(); dim.fill((70, 70, 70), special_flags=pygame.BLEND_RGB_MULT)
                frame.blit(dim, (0, int(y) - core), special_flags=pygame.BLEND_RGB_ADD)

            # ---- main scan: beam, sparks, edge markers ----
            if 0 <= scan < 1:
                y = gy0 + (gy1 - gy0) * scan
                frame.blit(beam, (0, int(y) - core), special_flags=pygame.BLEND_RGB_ADD)
                for _ in range(7):
                    x = random.uniform(0, W)
                    cc = pt.colour.get_at((int(x), min(H - 1, max(0, int(y) - 4))))
                    pt.sparks.append([x, y, random.uniform(-1.2, 1.2), random.uniform(-7, -2.5), 1.0, cc])
                # edge markers that follow the beam
                mk = (220, 235, 255)
                for side in (0, 1):
                    x0 = 18 if side == 0 else W - 18
                    dx = 22 if side == 0 else -22
                    pygame.draw.line(frame, mk, (x0, y - 14), (x0, y + 14), 3)
                    pygame.draw.line(frame, mk, (x0, y - 14), (x0 + dx, y - 14), 3)
                    pygame.draw.line(frame, mk, (x0, y + 14), (x0 + dx, y + 14), 3)
                tag = f_tag.render(f"y {int(y):04d} / {H}", True, mk)
                frame.blit(tag, (W - 30 - tag.get_width(), int(y) - 40))
                tag2 = f_tag.render(f"row {int(scan * pt.rows):03d}", True, mk)
                frame.blit(tag2, (30, int(y) - 40))
            # sparks drift up and fade
            alive = []
            for s in pt.sparks:
                s[0] += s[2]; s[1] += s[3]; s[3] *= 0.97; s[4] -= 1 / (FPS * 0.6)
                if s[4] > 0:
                    a = s[4]
                    c = s[5]
                    col = (int(min(255, 120 + c[0] * 0.6) * a), int(min(255, 120 + c[1] * 0.6) * a), int(min(255, 120 + c[2] * 0.6) * a))
                    frame.fill(col, pygame.Rect(int(s[0]), int(s[1]), 3, 3), special_flags=pygame.BLEND_RGB_ADD)
                    alive.append(s)
            pt.sparks = alive

            # ---- slow push-in at the end ----
            if t > A5:
                z = 1 + 0.09 * smooth((t - A5) / T_HOLD)
                fx, fy = pt.focus
                cw, ch = W / z, H / z
                x0 = min(max(0, fx - cw / 2), W - cw)
                y0 = min(max(0, fy - ch * 0.45), H - ch)
                crop = frame.subsurface(pygame.Rect(int(x0), int(y0), int(cw), int(ch))).copy()
                frame.blit(pygame.transform.smoothscale(crop, (W, H)), (0, 0))

            frame.blit(scanlines, (0, 0))

            # ---- terminal lines ----
            ink = (205, 220, 228)
            cmd = f"> render {pt.name} --mode=binary"
            typed = cmd[:int(min(1, t / 1.0) * len(cmd))]
            cursor = "_" if (t < A1 and int(t * 3) % 2 == 0) else ""
            frame.blit(f_top.render(typed + cursor, True, ink), (30, 26))
            if t > A1 - 0.2:
                done = t >= A5
                p = 1.0 if done else min(0.99, max(0.0, (t - A1) / (A5 - A1)))
                stage = ("render complete" if done else "decoding pixels" if t < A2 else
                         "reconstructing" if t < A3 else "calibrating" if t < A4 else "scanning")
                bars = 22
                fill = int(round(p * bars))
                line = f"{stage:<16} [{'#' * fill}{'.' * (bars - fill)}] {int(p * 100):3d}%   {pt.n:,} bits"
                frame.blit(f_bot.render(line, True, ink), (30, H - 62))

            # ---- out: video file + window ----
            if proc:
                try:
                    proc.stdin.write(frame.get_buffer().raw if fmt else pygame.image.tobytes(frame, "RGB"))
                except Exception:
                    proc = None
            if frame_hook:
                frame_hook(fi, frame)
            win.blit(pygame.transform.scale(frame, win.get_size()), (0, 0))
            pygame.display.flip()
            clock.tick(FPS)

        if proc:
            proc.stdin.close(); proc.wait()
            saved = out
        if max_frames:
            pygame.quit(); return saved

        # finished: hold the last frame; show where the video went (window only, not in the video)
        note = mono(16).render(f"saved: renders/{os.path.basename(saved)}" if saved else "done", True, (150, 170, 180))
        hint = mono(16).render("space = play again   esc = quit", True, (110, 125, 135))
        win.blit(pygame.transform.smoothscale(frame, win.get_size()), (0, 0))
        win.blit(note, (12, 10)); win.blit(hint, (12, 30))
        pygame.display.flip()
        again = False
        while not again:
            e = pygame.event.wait()
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit(); return saved
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                again = True


if __name__ == "__main__":
    run()
