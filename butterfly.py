"""
Butterfly Crack - a dark mirror cracks open and binary butterflies fly out.

Everything is drawn with text characters (0, 1 and ASCII symbols) in the terminal.
Run:   python butterfly_crack.py
Stop:  Ctrl + C

No installs needed. Works best in Windows Terminal, PowerShell, or any
terminal that supports colours. Make the window big (or full screen) first.
"""

import math
import os
import random
import shutil
import sys
import time

FPS = 30
BINARY = "01"
SHARD_CHARS = "/\\|_-.,'`01#%*"

# All colours use the 256-colour grey ramp: 232 (almost black) .. 255 (white).
BLACK, WHITE = 232, 255


# ---------------------------------------------------------------- terminal --

def setup_terminal():
    if os.name == "nt":
        os.system("")  # turns on colour codes in the Windows console
    sys.stdout.write("\x1b[?25l\x1b[2J")  # hide cursor, clear screen
    sys.stdout.flush()


def restore_terminal():
    sys.stdout.write("\x1b[0m\x1b[?25h\x1b[2J\x1b[H")
    sys.stdout.flush()


def terminal_size():
    size = shutil.get_terminal_size((100, 30))
    return max(40, size.columns), max(15, size.lines - 1)


# ------------------------------------------------------------------ canvas --

class Canvas:
    """A grid of characters and grey levels that is redrawn every frame."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.clear()

    def clear(self):
        self.chars = [[" "] * self.w for _ in range(self.h)]
        self.cols = [[BLACK] * self.w for _ in range(self.h)]

    def put(self, x, y, ch, col):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h and ch != " ":
            self.chars[y][x] = ch
            self.cols[y][x] = max(BLACK, min(WHITE, int(col)))

    def render(self, fade=1.0):
        out = ["\x1b[H"]
        current = None
        for y in range(self.h):
            row_chars, row_cols = self.chars[y], self.cols[y]
            for x in range(self.w):
                col = BLACK + int((row_cols[x] - BLACK) * fade)
                if col != current:
                    out.append(f"\x1b[38;5;{col}m")
                    current = col
                out.append(row_chars[x])
            if y < self.h - 1:
                out.append("\n")
        sys.stdout.write("".join(out))
        sys.stdout.flush()


# --------------------------------------------------------------- the crack --

def line_char(dx, dy):
    """Pick a character that looks like a line going in direction (dx, dy)."""
    ang = math.degrees(math.atan2(dy * 2, dx)) % 180  # *2: cells are tall
    if ang < 22 or ang >= 158:
        return random.choice("-_")
    if ang < 68:
        return "\\"
    if ang < 112:
        return "|"
    return "/"


def make_crack(cx, cy, w, h):
    """Return a list of (distance, x, y, char) points that form the crack."""
    points = []
    reach = max(w, h * 2) * 0.75

    def ray(x, y, angle, length, depth):
        dist0 = math.hypot(x - cx, (y - cy) * 2)
        steps = int(length)
        for i in range(steps):
            angle += random.uniform(-0.22, 0.22)
            dx, dy = math.cos(angle), math.sin(angle) * 0.5
            step = max(abs(dx), abs(dy))
            dx, dy = dx / step, dy / step
            x, y = x + dx, y + dy
            points.append((dist0 + i, x, y, line_char(dx, dy)))
            if depth < 1 and random.random() < 0.025:
                side = random.choice((-1, 1))
                ray(x, y, angle + side * random.uniform(0.4, 0.9),
                    random.uniform(4, length - i + 1) * 0.6, depth + 1)

    n = random.randint(7, 9)
    for k in range(n):
        base = (2 * math.pi / n) * k + random.uniform(-0.25, 0.25)
        ray(cx, cy, base, random.uniform(reach * 0.4, reach * 0.85), 0)

    # ring-shaped cracks around the impact point, like real broken glass
    for radius in (random.uniform(5, 7), random.uniform(10, 14)):
        start = random.uniform(0, 2 * math.pi)
        arc = random.uniform(math.pi * 0.8, math.pi * 1.6)
        a = start
        while a < start + arc:
            x = cx + math.cos(a) * radius
            y = cy + math.sin(a) * radius * 0.5
            ch = line_char(-math.sin(a), math.cos(a))
            points.append((radius + 2, x, y, ch))
            a += 0.9 / radius
    points.sort(key=lambda p: p[0])
    return points


# -------------------------------------------------------------- butterflies --

# '#' spots get filled with random 0s and 1s every frame.
WINGS = [
    [" .##.^.##. ",
     "(####|####)",
     " `##/ \\##` "],
    ["   .#^#.   ",
     "  (##|##)  ",
     "   `/ \\`   "],
    ["    \\^/    ",
     "    (|)    ",
     "    / \\    "],
    ["   .#^#.   ",
     "  (##|##)  ",
     "   `/ \\`   "],
]
TINY = [["\\|/"], ["-|-"]]


class Butterfly:
    def __init__(self, x, y):
        self.x, self.y = x, y
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.25, 0.55)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed * 0.5 - 0.15
        self.age = 0
        self.phase = random.uniform(0, 6.28)
        self.flap_offset = random.randint(0, 3)
        self.shade = random.randint(248, 255)

    def update(self, dust):
        self.age += 1
        # gentle flutter and wandering
        self.vy += math.sin(self.age * 0.3 + self.phase) * 0.03
        self.vx += random.uniform(-0.03, 0.03)
        self.vy += random.uniform(-0.03, 0.03)
        speed = math.hypot(self.vx, self.vy * 2)
        if speed > 0.7:
            self.vx, self.vy = self.vx / speed * 0.7, self.vy / speed * 0.7
        self.x += self.vx
        self.y += self.vy
        if random.random() < 0.6:
            dust.append(Particle(self.x + random.uniform(-2, 2), self.y + 1,
                                 random.uniform(-0.05, 0.05), 0.04,
                                 random.choice(BINARY), 246, 18))

    def draw(self, cv):
        if self.age < 10:
            sprite = TINY[(self.age // 3) % 2]
        else:
            sprite = WINGS[(self.age // 3 + self.flap_offset) % 4]
        top = self.y - len(sprite) // 2
        left = self.x - len(sprite[0]) // 2
        for r, row in enumerate(sprite):
            for c, ch in enumerate(row):
                if ch == " ":
                    continue
                if ch == "#":
                    cv.put(left + c, top + r, random.choice(BINARY), self.shade - 4)
                elif ch in "|^":
                    cv.put(left + c, top + r, ch, WHITE)
                else:
                    cv.put(left + c, top + r, ch, self.shade)

    def gone(self, w, h):
        return self.x < -8 or self.x > w + 8 or self.y < -4 or self.y > h + 4


# -------------------------------------------------------------- particles --

class Particle:
    def __init__(self, x, y, vx, vy, ch, col, life, gravity=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.ch, self.col, self.life, self.max_life = ch, col, life, life
        self.gravity = gravity

    def update(self):
        self.vy += self.gravity
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, cv):
        t = self.life / self.max_life
        cv.put(self.x, self.y, self.ch, BLACK + (self.col - BLACK) * t)


# ------------------------------------------------------------------- scene --

def background_noise(cv, noise):
    """Faint binary flicker - the dark mirror is never fully dead."""
    w, h = cv.w, cv.h
    for _ in range(max(1, w * h // 900)):
        noise.append([random.randrange(w), random.randrange(h),
                      random.choice(BINARY), random.randint(10, 30)])
    for n in noise:
        n[3] -= 1
        cv.put(n[0], n[1], n[2], BLACK + min(n[3], 6) * 0.9)
    noise[:] = [n for n in noise if n[3] > 0]


def run_cycle():
    w, h = terminal_size()
    cv = Canvas(w, h)
    cx = w / 2 + random.uniform(-w * 0.15, w * 0.15)
    cy = h / 2 + random.uniform(-h * 0.15, h * 0.15)

    crack = make_crack(cx, cy, w, h)
    hole_r = max(7.0, min(w, h * 2) * 0.17)
    bumps = [random.uniform(0.75, 1.25) for _ in range(16)]

    def hole_radius(angle):
        i = (angle % (2 * math.pi)) / (2 * math.pi) * 16
        a, b = bumps[int(i) % 16], bumps[(int(i) + 1) % 16]
        return hole_r * (a + (b - a) * (i - int(i)))

    def in_hole(x, y, extra=0.0):
        dx, dy = x - cx, (y - cy) * 2
        return math.hypot(dx, dy) < hole_radius(math.atan2(dy, dx)) + extra

    noise, shards, dust, flies = [], [], [], []
    frame = 0
    crack_progress = 0.0
    hole_open = False
    spawned = 0
    to_spawn = random.randint(14, 20)

    # frame timeline
    T_CRACK = int(FPS * 2.5)      # dark mirror until here
    T_SHATTER = T_CRACK + int(FPS * 1.6)
    T_FLY = T_SHATTER + int(FPS * 0.6)
    T_FADE = T_FLY + int(FPS * 13)
    T_END = T_FADE + int(FPS * 1.5)

    while frame < T_END:
        start = time.time()
        cv.clear()
        background_noise(cv, noise)

        # ---- the crack spreads out from the impact point
        if frame >= T_CRACK:
            crack_progress += 3.2
            for dist, x, y, ch in crack:
                if dist > crack_progress:
                    break
                if hole_open and in_hole(x, y, 0.5):
                    continue
                age = crack_progress - dist
                cv.put(x, y, ch, WHITE - min(age * 0.35, 13))
            # impact flash
            f = frame - T_CRACK
            if f < 8:
                for _ in range(10 - f):
                    a = random.uniform(0, 6.28)
                    r = random.uniform(0, f + 1)
                    cv.put(cx + math.cos(a) * r, cy + math.sin(a) * r * 0.5,
                           random.choice("*+."), WHITE)
                cv.put(cx, cy, "*", WHITE)

        # ---- the middle breaks open into a hole
        if frame == T_SHATTER:
            hole_open = True
            reach = int(hole_r * 1.3) + 1
            for yy in range(int(cy - reach / 2) - 1, int(cy + reach / 2) + 2):
                for xx in range(int(cx - reach) - 1, int(cx + reach) + 2):
                    if in_hole(xx, yy):
                        dx, dy = xx - cx, yy - cy
                        d = math.hypot(dx, dy) or 1
                        shards.append(Particle(
                            xx, yy, dx / d * random.uniform(0.1, 0.6),
                            dy / d * random.uniform(0.0, 0.3) - 0.2,
                            random.choice(SHARD_CHARS),
                            random.randint(244, 255), random.randint(20, 45),
                            gravity=0.04))

        if hole_open:
            for yy in range(cv.h):
                for xx in range(cv.w):
                    if cv.chars[yy][xx] != " " and in_hole(xx, yy):
                        cv.chars[yy][xx] = " "
            # jagged glass edge around the hole
            for i in range(int(hole_r * 9)):
                a = i / (hole_r * 9) * 2 * math.pi
                r = hole_radius(a) + 0.6
                cv.put(cx + math.cos(a) * r, cy + math.sin(a) * r * 0.5,
                       line_char(-math.sin(a), math.cos(a)), 252)
            # the void inside: deep, slowly drifting binary
            for _ in range(int(hole_r * 1.5)):
                a = random.uniform(0, 6.28)
                r = random.uniform(0, hole_radius(a) - 1)
                cv.put(cx + math.cos(a) * r, cy + math.sin(a) * r * 0.5,
                       random.choice(BINARY), random.randint(234, 238))

        for p in shards:
            p.update()
            p.draw(cv)
        shards[:] = [p for p in shards if p.life > 0]

        # ---- butterflies escape through the hole
        if frame >= T_FLY and spawned < to_spawn and frame % 12 == 0:
            flies.append(Butterfly(cx + random.uniform(-1, 1), cy))
            spawned += 1

        for p in dust:
            p.update()
            p.draw(cv)
        dust[:] = [p for p in dust if p.life > 0]

        for b in flies:
            b.update(dust)
            b.draw(cv)
        flies[:] = [b for b in flies if not b.gone(w, h)]

        fade = 1.0
        if frame >= T_FADE:
            fade = max(0.0, 1 - (frame - T_FADE) / (T_END - T_FADE))
        cv.render(fade)

        frame += 1
        time.sleep(max(0.0, 1 / FPS - (time.time() - start)))


def main():
    setup_terminal()
    try:
        while True:
            run_cycle()
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        restore_terminal()


if __name__ == "__main__":
    main()