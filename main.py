#!/usr/bin/env python3
"""Draw Friday 20 November 2026's world news as one 1024x1024 front page.

Standard library only. Deterministic: two runs write identical bytes.
Writes to $MAKEFUN_OUTPUT_DIR/entry.png when set, else /output/entry.png.

Layout (top to bottom): masthead with the date, two illustrated lead
panels (the Trump-Xi-Putin summit and the ICJ genocide ruling), a world
map strip with numbered markers, and a 3-column grid of 36 short stories in
six colour-coded sections (World, Politics, Tech, Business, Culture,
Sport). All text uses a hand-built 5x7 bitmap font; the PNG is encoded
by hand (zlib + CRC), so the program needs no third-party packages.
"""

import os
import struct
import zlib

W = 1024
H = 1024

PAPER = (247, 243, 234)
INK = (20, 20, 20)
FAINT = (90, 86, 78)
RULE = (60, 56, 48)
RED = (176, 42, 32)
BLUE = (29, 78, 137)
PURPLE = (106, 63, 160)
GREEN = (31, 122, 77)
ORANGE = (194, 106, 0)
TEAL = (14, 122, 122)
PANEL = (255, 255, 255)
PANEL_LINE = (120, 114, 100)
MAP_LAND = (205, 212, 196)
MAP_SEA = (214, 230, 238)
GOLD = (198, 148, 40)


# ---------------------------------------------------------------- PNG out
def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def encode_png(width, height, rgb):
    """rgb: bytes, 3 per pixel, row-major. Returns whole PNG bytes."""
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, width, height, bg):
        self.w = width
        self.h = height
        self.px = bytearray(bg) * (width * height)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(color)

    def rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            self.px[base:(base + (x1 - x0) * 3)] = bytes(color) * (x1 - x0)

    def hline(self, x, y, w, color, thick=1):
        self.rect(x, y, w, thick, color)

    def vline(self, x, y, h, color, thick=1):
        self.rect(x, y, thick, h, color)

    def line(self, x0, y0, x1, y1, color, thick=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            if thick == 1:
                self.set(x0, y0, color)
            else:
                self.rect(x0 - thick // 2, y0 - thick // 2, thick, thick, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, color, fill=True):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if fill:
                    if d2 <= r * r:
                        self.set(xx, yy, color)
                else:
                    if abs(d2 - r * r) <= r:
                        self.set(xx, yy, color)

    def ring(self, cx, cy, r, color, thick=2):
        for t in range(thick):
            self.circle(cx, cy, r - t, color, fill=False)

    def poly(self, pts, color):
        """Scanline-fill a simple polygon given as [(x, y), ...]."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                xa = int(round(xs[i]))
                xb = int(round(xs[i + 1]))
                self.rect(xa, y, xb - xa + 1, 1, color)

    def polyline(self, pts, color, thick=1, closed=False):
        n = len(pts)
        rng = range(n) if closed else range(n - 1)
        for i in rng:
            a = pts[i]
            b = pts[(i + 1) % n]
            self.line(a[0], a[1], b[0], b[1], color, thick)


# ---------------------------------------------------------------- 5x7 font
# Each glyph: 7 rows, bit 4 = leftmost pixel. Written from scratch.
FONT = {
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F),
    "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    " ": (0, 0, 0, 0, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 0x0C, 0x0C),
    ",": (0, 0, 0, 0, 0x0C, 0x04, 0x08),
    ":": (0, 0x0C, 0x0C, 0, 0x0C, 0x0C, 0),
    ";": (0, 0x0C, 0x0C, 0, 0x0C, 0x04, 0x08),
    "-": (0, 0, 0, 0x0E, 0, 0, 0),
    "'": (0x04, 0x04, 0x08, 0, 0, 0, 0),
    "/": (0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10),
    "(": (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02),
    ")": (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    "&": (0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D),
    "%": (0x19, 0x1A, 0x02, 0x04, 0x08, 0x0B, 0x13),
    "+": (0, 0x04, 0x04, 0x0E, 0x04, 0x04, 0),
    "?": (0x0E, 0x11, 0x01, 0x06, 0x04, 0, 0x04),
    "!": (0x04, 0x04, 0x04, 0x04, 0x04, 0, 0x04),
    "=": (0, 0, 0x1F, 0, 0x1F, 0, 0),
    "$": (0x04, 0x0F, 0x14, 0x0E, 0x05, 0x1E, 0x04),
    '"': (0x0A, 0x0A, 0x0A, 0, 0, 0, 0),
    "_": (0, 0, 0, 0, 0, 0, 0x1F),
    "*": (0, 0x04, 0x15, 0x0E, 0x15, 0x04, 0),
    "<": (0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02),
    ">": (0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08),
}

BLANK = (0, 0, 0, 0, 0, 0, 0)


def text_w(s, scale):
    return len(s) * 6 * scale - scale


def draw_text(cv, x, y, s, scale, color):
    """Uppercase-only bitmap text; returns width drawn."""
    s = s.upper()
    cx = x
    for ch in s:
        glyph = FONT.get(ch, BLANK)
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits & (1 << (4 - col)):
                    cv.rect(cx + col * scale, y + row * scale, scale, scale, color)
        cx += 6 * scale
    return cx - x - scale


def wrap(s, max_chars):
    """Greedy word wrap to lines of at most max_chars characters."""
    words = s.upper().split(" ")
    lines = []
    cur = ""
    for word in words:
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= max_chars:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_para(cv, x, y, w, s, scale, color, leading=None):
    """Wrapped paragraph; returns y just below the last line."""
    max_chars = max(1, (w + scale) // (6 * scale))
    lh = leading if leading is not None else 9 * scale
    for line in wrap(s, max_chars):
        draw_text(cv, x, y, line, scale, color)
        y += lh
    return y

# ---------------------------------------------------------------- icons
# Tiny 22x22 pictograms drawn from primitives, one per story kind.

def _flag(cv, x, y, w, h, stripes):
    for i, c in enumerate(stripes):
        cv.rect(x, y + i * h // len(stripes), w, h // len(stripes) + 1, c)


def icon(cv, x, y, kind):
    """Draw a small icon of the given kind inside a 22x22 box at (x, y)."""
    if kind == "summit":  # three flags on poles
        for i, stripes in enumerate(
            (((176, 42, 32), (255, 255, 255), (29, 78, 137)),
             ((222, 41, 16), (222, 41, 16), (222, 41, 16)),
             ((255, 255, 255), (0, 57, 166), (213, 0, 50)))):
            fx = x + i * 7
            cv.vline(fx + 3, y + 2, 18, INK)
            _flag(cv, fx, y + 2, 7, 7, stripes)
    elif kind == "court":  # scales of justice
        cv.vline(x + 11, y + 3, 15, INK, 2)
        cv.hline(x + 3, y + 5, 16, INK, 2)
        cv.line(x + 4, y + 5, x + 1, y + 12, INK)
        cv.line(x + 4, y + 5, x + 7, y + 12, INK)
        cv.line(x + 18, y + 5, x + 15, y + 12, INK)
        cv.line(x + 18, y + 5, x + 21, y + 12, INK)
        cv.line(x + 1, y + 12, x + 7, y + 12, INK)
        cv.line(x + 15, y + 12, x + 21, y + 12, INK)
        cv.rect(x + 7, y + 18, 8, 2, INK)
    elif kind == "rocket":  # space probe
        cv.poly([(x + 11, y + 1), (x + 15, y + 9), (x + 13, y + 16),
                 (x + 9, y + 16), (x + 7, y + 9)], INK)
        cv.circle(x + 11, y + 8, 2, PAPER)
        cv.line(x + 7, y + 12, x + 3, y + 18, RED, 2)
        cv.line(x + 15, y + 12, x + 19, y + 18, RED, 2)
        cv.line(x + 11, y + 16, x + 11, y + 21, GOLD, 2)
    elif kind == "storm":  # cyclone cloud + rain
        cv.circle(x + 8, y + 8, 5, INK)
        cv.circle(x + 14, y + 7, 6, INK)
        cv.rect(x + 3, y + 9, 16, 4, INK)
        for dx in (4, 10, 16):
            cv.line(x + dx, y + 15, x + dx - 2, y + 20, BLUE, 2)
    elif kind == "ship":  # boat on waves
        cv.poly([(x + 2, y + 9), (x + 20, y + 9), (x + 17, y + 15),
                 (x + 5, y + 15)], INK)
        cv.vline(x + 11, y + 2, 8, INK)
        cv.poly([(x + 12, y + 3), (x + 19, y + 7), (x + 12, y + 7)], RED)
        cv.line(x + 1, y + 18, x + 7, y + 18, BLUE, 2)
        cv.line(x + 9, y + 18, x + 15, y + 18, BLUE, 2)
        cv.line(x + 17, y + 18, x + 21, y + 18, BLUE, 2)
    elif kind == "flame":  # fire
        cv.poly([(x + 11, y + 1), (x + 16, y + 8), (x + 19, y + 13),
                 (x + 15, y + 20), (x + 7, y + 20), (x + 3, y + 13),
                 (x + 6, y + 8)], (230, 110, 20))
        cv.poly([(x + 11, y + 9), (x + 14, y + 13), (x + 13, y + 18),
                 (x + 9, y + 18), (x + 8, y + 13)], GOLD)
    elif kind == "gavel":  # court hammer
        cv.line(x + 4, y + 4, x + 14, y + 14, INK, 3)
        cv.rect(x + 13, y + 2, 7, 5, INK)
        cv.rect(x + 2, y + 13, 7, 5, INK)
        cv.rect(x + 4, y + 19, 14, 2, INK)
    elif kind == "chart":  # market bars
        for i, h in enumerate((6, 12, 9, 16)):
            cv.rect(x + 2 + i * 5, y + 18 - h, 3, h, GREEN)
        cv.line(x + 1, y + 2, x + 6, y + 7, RED, 2)
        cv.line(x + 6, y + 7, x + 11, y + 4, RED, 2)
        cv.line(x + 11, y + 4, x + 20, y + 8, RED, 2)
    elif kind == "ball":  # football
        cv.circle(x + 11, y + 11, 9, INK, fill=False)
        cv.poly([(x + 11, y + 7), (x + 15, y + 10), (x + 13, y + 15),
                 (x + 9, y + 15), (x + 7, y + 10)], INK)
        cv.line(x + 11, y + 7, x + 11, y + 2, INK)
        cv.line(x + 15, y + 10, x + 20, y + 8, INK)
        cv.line(x + 7, y + 10, x + 2, y + 8, INK)
    elif kind == "chip":  # AI chip
        cv.rect(x + 5, y + 5, 12, 12, INK)
        cv.rect(x + 8, y + 8, 6, 6, PAPER)
        for i in range(3):
            cv.hline(x + 7 + i * 4, y + 1, 2, INK, 4)
            cv.hline(x + 7 + i * 4, y + 17, 2, INK, 4)
            cv.vline(x + 1, y + 7 + i * 4, 2, INK, 4)
            cv.vline(x + 20, y + 7 + i * 4, 2, INK, 4)
    elif kind == "globe":  # world
        cv.circle(x + 11, y + 11, 9, BLUE, fill=False)
        cv.circle(x + 11, y + 11, 9, MAP_LAND)
        cv.hline(x + 3, y + 11, 16, BLUE)
        cv.line(x + 5, y + 4, x + 8, y + 18, BLUE)
        cv.line(x + 17, y + 4, x + 14, y + 18, BLUE)
    elif kind == "star":  # celebrity / culture
        cv.poly([(x + 11, y + 1), (x + 13, y + 8), (x + 20, y + 8),
                 (x + 15, y + 12), (x + 17, y + 19), (x + 11, y + 15),
                 (x + 5, y + 19), (x + 7, y + 12), (x + 2, y + 8),
                 (x + 9, y + 8)], GOLD)
    elif kind == "plane":  # jet
        cv.poly([(x + 2, y + 12), (x + 18, y + 7), (x + 20, y + 9),
                 (x + 12, y + 13), (x + 8, y + 18), (x + 6, y + 15),
                 (x + 4, y + 15)], INK)
    elif kind == "bolt":  # energy / power
        cv.poly([(x + 13, y + 1), (x + 6, y + 12), (x + 10, y + 12),
                 (x + 9, y + 21), (x + 16, y + 10), (x + 12, y + 10)], GOLD)
    elif kind == "book":  # study / faith
        cv.poly([(x + 2, y + 5), (x + 11, y + 3), (x + 11, y + 19),
                 (x + 2, y + 21)], PANEL)
        cv.poly([(x + 20, y + 5), (x + 11, y + 3), (x + 11, y + 19),
                 (x + 20, y + 21)], PANEL)
        cv.polyline([(x + 2, y + 5), (x + 11, y + 3), (x + 20, y + 5),
                     (x + 20, y + 21), (x + 11, y + 19), (x + 2, y + 21),
                     (x + 2, y + 5)], INK)
        cv.vline(x + 11, y + 3, 16, INK)
    elif kind == "drop":  # drought / water
        cv.poly([(x + 11, y + 2), (x + 18, y + 12), (x + 11, y + 20),
                 (x + 4, y + 12)], BLUE)
    elif kind == "hand":  # podium with microphone (politics / diplomacy)
        cv.poly([(x + 4, y + 20), (x + 18, y + 20), (x + 15, y + 10),
                 (x + 7, y + 10)], INK)
        cv.vline(x + 11, y + 3, 8, INK)
        cv.circle(x + 11, y + 3, 2, INK)
    else:  # dot
        cv.circle(x + 11, y + 11, 4, RED)


# ---------------------------------------------------------------- world map
# Coarse continent outlines in (lon, lat). Drawn squashed into a strip.
CONTINENTS = [
    # North America
    [(-168, 66), (-150, 70), (-135, 69), (-125, 71), (-110, 73), (-95, 80),
     (-85, 80), (-75, 73), (-65, 62), (-55, 47), (-65, 45), (-70, 42),
     (-75, 35), (-80, 32), (-84, 30), (-90, 21), (-95, 19), (-97, 16),
     (-92, 14), (-86, 12), (-82, 9), (-79, 9), (-83, 15), (-90, 14),
     (-97, 16), (-105, 20), (-110, 23), (-114, 29), (-120, 34),
     (-125, 40), (-125, 49), (-135, 58), (-150, 60), (-165, 60)],
    # Greenland
    [(-55, 60), (-45, 60), (-40, 65), (-30, 68), (-20, 70), (-25, 76),
     (-40, 80), (-58, 76), (-60, 70)],
    # South America
    [(-79, 9), (-77, 4), (-80, -3), (-81, -6), (-77, -12), (-72, -18),
     (-70, -23), (-70, -30), (-72, -37), (-73, -44), (-70, -52),
     (-66, -55), (-68, -50), (-65, -45), (-62, -40), (-57, -35),
     (-52, -32), (-48, -28), (-41, -23), (-39, -17), (-35, -9),
     (-35, -6), (-40, -3), (-44, -2), (-50, 0), (-53, 4), (-58, 6),
     (-62, 9), (-68, 11), (-72, 12), (-77, 8)],
    # Eurasia
    [(-10, 36), (-9, 43), (-2, 44), (-1, 46), (-4, 48), (-2, 50), (2, 51),
     (5, 53), (8, 55), (8, 57), (10, 59), (5, 60), (5, 62), (12, 65),
     (18, 69), (25, 71), (30, 70), (35, 68), (40, 68), (45, 66),
     (50, 68), (55, 68), (60, 69), (65, 68), (68, 66), (68, 70),
     (75, 72), (85, 74), (95, 76), (105, 77), (115, 73), (125, 73),
     (135, 72), (145, 72), (155, 70), (162, 69), (170, 67), (178, 65),
     (178, 62), (170, 60), (162, 60), (158, 56), (150, 59), (142, 55),
     (142, 50), (140, 46), (135, 44), (130, 42), (127, 40), (122, 38),
     (120, 34), (122, 30), (118, 25), (114, 22), (110, 21), (108, 18),
     (106, 10), (104, 9), (103, 2), (100, 7), (98, 10), (95, 15),
     (92, 21), (88, 22), (85, 19), (80, 15), (80, 10), (77, 8),
     (76, 12), (73, 20), (70, 22), (66, 25), (62, 25), (58, 26),
     (54, 27), (50, 29), (48, 30), (44, 29), (40, 31), (36, 33),
     (35, 36), (30, 36), (28, 37), (23, 36), (19, 40), (15, 44),
     (12, 44), (8, 44), (3, 42), (0, 38), (-2, 37), (-6, 36), (-9, 37)],
    # Africa
    [(-6, 35), (0, 36), (10, 37), (11, 34), (20, 32), (30, 31), (32, 31),
     (35, 28), (37, 22), (39, 18), (43, 12), (48, 11), (51, 10),
     (46, 5), (42, 0), (40, -5), (40, -10), (36, -18), (33, -26),
     (30, -32), (26, -34), (20, -35), (17, -32), (15, -27), (12, -18),
     (12, -10), (9, -1), (9, 4), (4, 6), (-8, 5), (-13, 8), (-17, 15),
     (-17, 20), (-16, 25), (-15, 30), (-10, 31)],
    # Australia
    [(114, -22), (114, -30), (115, -35), (120, -34), (124, -33),
     (129, -32), (132, -32), (135, -35), (138, -35), (140, -38),
     (145, -38), (150, -37), (153, -32), (153, -27), (150, -23),
     (146, -19), (142, -15), (142, -11), (137, -12), (135, -15),
     (132, -12), (130, -13), (126, -14), (122, -17), (118, -20)],
    # Japan
    [(130, 31), (132, 33), (135, 34), (137, 35), (139, 36), (141, 39),
     (141, 42), (143, 43), (145, 44), (142, 45), (140, 42), (139, 38),
     (137, 37), (135, 35), (132, 33)],
    # Indonesia
    [(95, 5), (100, 0), (105, -6), (110, -7), (115, -8), (120, -10),
     (118, -8), (114, -4), (110, 0), (108, 2), (104, 1), (100, 3)],
    # New Zealand
    [(167, -45), (170, -43), (173, -41), (175, -38), (177, -38),
     (175, -40), (172, -43), (168, -46)],
    # Britain
    [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 53), (1, 51)],
]


def draw_map(cv, x, y, w, h, markers):
    """markers: list of (lon, lat, number)."""
    cv.rect(x, y, w, h, MAP_SEA)
    for pts in CONTINENTS:
        mapped = []
        for lon, lat in pts:
            mx = x + int((lon + 180.0) / 360.0 * w)
            my = y + int((80.0 - lat) / 140.0 * h)
            mapped.append((mx, my))
        cv.poly(mapped, MAP_LAND)
        cv.polyline(mapped, (110, 118, 104), 1, closed=True)
    for lon, lat, num in markers:
        mx = x + int((lon + 180.0) / 360.0 * w)
        my = y + int((80.0 - lat) / 140.0 * h)
        # keep the dot fully inside the band (Fiji / Wellington sit at the
        # 180-degree edge, so clamp rather than clip)
        mx = max(x + 10, min(x + w - 10, mx))
        my = max(y + 10, min(y + h - 10, my))
        cv.circle(mx, my, 8, RED)
        cv.ring(mx, my, 8, (255, 255, 255), 1)
        label = str(num)
        draw_text(cv, mx - (3 * len(label) - 1), my - 3, label, 1, (255, 255, 255))

# ---------------------------------------------------------------- stories
# (section, short label, icon kind, map marker number or None)
# Labels are factual, dated 20 Nov 2026 (events of 20 Nov, first reported
# 20 Nov, or the big 19 Nov stories still leading the news on 20 Nov).
SECTIONS = {
    "WORLD": RED,
    "POLITICS": BLUE,
    "TECH": PURPLE,
    "BUSINESS": GREEN,
    "CULTURE": ORANGE,
    "SPORT": TEAL,
}

STORIES = [
    ("WORLD", "TRUMP-XI-PUTIN SUMMIT: PEACE PACT", "summit", 1),
    ("WORLD", "ICJ: MYANMAR COMMITTED GENOCIDE", "gavel", 2),
    ("POLITICS", "TRUMP PUSHES IRAN DECISION TO 2027", "hand", None),
    ("TECH", "VOYAGER 1 PASSES LIGHT-DAY MARK", "rocket", None),
    ("TECH", "HAYABUSA2 ENGINE FAULT ENDS LANDING", "rocket", 3),
    ("CULTURE", "GTA 6 SALES PASS ODYSSEY'S $1.8BN", "star", None),
    ("WORLD", "CYCLONE AKVAN: 300,000 EVACUATED", "storm", 4),
    ("POLITICS", "EUROPE READY FOR TALKS WITH RUSSIA", "hand", 5),
    ("BUSINESS", "ANTHROPIC DEBUTS AT ~$1.5TN VALUE", "chart", None),
    ("WORLD", "UKRAINE HITS CRIMEAN BRIDGE AGAIN", "bolt", 6),
    ("WORLD", "BOAT SINKS OFF SENEGAL; DOZENS LOST", "ship", 7),
    ("WORLD", "ISRAEL ENDS GAZA OP; LEBANON STRIKE", "flame", 8),
    ("WORLD", "TANKER BURNS AFTER MINE NEAR HORMUZ", "ship", 9),
    ("POLITICS", "FOSSIL-FUEL LINE CUT FROM COP31 DRAFT", "book", None),
    ("WORLD", "HOUTHIS HIT RIYADH; PIF TOWER DAMAGED", "flame", 10),
    ("CULTURE", "FIONA THE HIPPO DIES AT CINCINNATI ZOO", "star", None),
    ("CULTURE", "TRUMP PARDONS BASEBALL GREAT PETE ROSE", "star", None),
    ("POLITICS", "MODI MEETS PRINCE AND PRINCESS OF WALES", "hand", None),
    ("SPORT", "NICHOLLS TON AS NZ REACH 243/5 VS INDIA", "ball", 11),
    ("BUSINESS", "SENSEX +1.21%, NIFTY +1.14% ON RALLY", "chart", None),
    ("POLITICS", "KOREA COURT CLEARS EX-PM HAN DUCK-SOO", "gavel", None),
    ("WORLD", "FIJI DECLARES DISASTER OVER DROUGHT", "drop", 12),
    ("POLITICS", "US AND VENEZUELA RESTORE MILITARY TIES", "hand", None),
    ("WORLD", "N. KOREA EXPANDING ENRICHMENT: UN", "bolt", None),
    ("TECH", "CALIFORNIA PROBES NVIDIA OVER CHINA CHIPS", "chip", None),
    ("TECH", "CANADA BACKS AI CENTRES; US PUSHES BACK", "chip", None),
    ("TECH", "IEA: DATA-CENTRE POWER MAY DOUBLE BY 2030", "bolt", None),
    ("CULTURE", "STUDY: ISLAM LARGEST FAITH BY 2035", "book", None),
    ("WORLD", "FIRE AT EX-LEADER YUNUS'S HOME", "flame", None),
    ("WORLD", "BOY RESCUED 8 HRS AFTER TBILISI BLAST", "hand", None),
    ("WORLD", "ONE DEAD, 15 HURT IN FRENCH FLAT FIRE", "flame", None),
    ("TECH", "BAYKAR DELIVERS FIRST 3 KIZILELMA JETS", "plane", None),
    ("WORLD", "SWISS DRILLS TO PROTECT KEY SITES", "bolt", None),
    ("WORLD", "INDIA EVACUATES 80,000 AS STORM DANA NEARS", "storm", None),
    ("TECH", "MUSK: STARLINK CUT WOULD HIT UKRAINE FRONT", "chip", None),
    ("SPORT", "ENGLAND BEAT CROATIA", "ball", None),
]

# Map markers: (lon, lat, number) — numbered to match STORIES above.
MAP_MARKERS = [
    (116, 39, 1),    # Beijing summit
    (4, 52, 2),      # The Hague, ICJ
    (139, 35, 3),    # Japan, Hayabusa2
    (86, 20, 4),     # Odisha, Cyclone Akvan
    (20, 60, 5),     # Europe / Ukraine talks (placed clear of The Hague)
    (36, 45, 6),     # Crimean Bridge
    (-17, 15, 7),    # Senegal coast
    (34, 31, 8),     # Gaza / Lebanon
    (57, 26, 9),     # Strait of Hormuz
    (47, 25, 10),    # Riyadh
    (175, -41, 11),  # Wellington, NZ v India
    (178, -18, 12),  # Fiji drought
]


# ---------------------------------------------------------------- layout
def draw_masthead(cv):
    cv.rect(0, 0, W, 4, INK)
    cv.rect(0, 8, W, 1, RULE)
    title = "WORLD IN A DAY"
    tw = text_w(title, 6)
    draw_text(cv, (W - tw) // 2, 16, title, 6, INK)
    draw_text(cv, 12, 30, "THE NEWS", 1, FAINT)
    draw_text(cv, W - 12 - text_w("ONE DAY, ONE PAGE", 1), 30, "ONE DAY, ONE PAGE", 1, FAINT)
    # red date band
    cv.rect(0, 66, W, 34, RED)
    date = "FRIDAY 20 NOVEMBER 2026"
    dw = text_w(date, 3)
    draw_text(cv, (W - dw) // 2, 72, date, 3, (255, 255, 255))
    draw_text(cv, 12, 78, "36 STORIES", 1, (255, 255, 255))
    draw_text(cv, W - 12 - text_w("SIX SECTIONS", 1), 78, "SIX SECTIONS", 1,
              (255, 255, 255))
    cv.rect(0, 104, W, 2, INK)


def draw_lead(cv, x, y, w, h, tag, headline, sub, draw_art):
    cv.rect(x, y, w, h, PANEL)
    cv.rect(x, y, w, 1, PANEL_LINE)
    cv.rect(x, y + h - 1, w, 1, PANEL_LINE)
    cv.rect(x, y, 1, h, PANEL_LINE)
    cv.rect(x + w - 1, y, 1, h, PANEL_LINE)
    cv.rect(x + 10, y + 10, text_w(tag, 1) + 10, 13, RED)
    draw_text(cv, x + 15, y + 12, tag, 1, (255, 255, 255))
    art_x = x + w - 118
    draw_art(cv, art_x, y + 30, 104, 84)
    draw_text(cv, x + 12, y + 30, headline[0], 3, INK)
    draw_text(cv, x + 12, y + 54, headline[1], 3, INK)
    draw_para(cv, x + 12, y + 84, w - 140, sub, 2, INK, leading=17)


def art_summit(cv, x, y, w, h):
    # globe arc behind, three flags, three figures at a table
    cv.circle(x + w // 2, y + h // 2 - 6, 34, (200, 220, 235))
    cv.circle(x + w // 2, y + h // 2 - 6, 34, BLUE, fill=False)
    for i, stripes in enumerate(
            (((176, 42, 32), (255, 255, 255), (29, 78, 137)),
             ((222, 41, 16), (222, 41, 16), (222, 41, 16)),
             ((255, 255, 255), (0, 57, 166), (213, 0, 50)))):
        fx = x + 8 + i * 32
        cv.vline(fx + 10, y + 6, 30, INK)
        _flag(cv, fx, y + 6, 20, 14, stripes)
    cv.rect(x + 4, y + 62, w - 8, 8, (120, 82, 50))
    for i in range(3):
        cx = x + 22 + i * 32
        cv.circle(cx, y + 48, 8, (240, 210, 180))
        cv.poly([(cx - 12, y + 62), (cx + 12, y + 62), (cx + 6, y + 54),
                 (cx - 6, y + 54)], (40, 40, 40))


def art_court(cv, x, y, w, h):
    # courthouse: pediment, columns, steps, scales in front
    cv.poly([(x + 6, y + 26), (x + w // 2, y + 4), (x + w - 6, y + 26)], INK)
    cv.circle(x + w // 2, y + 17, 5, GOLD)
    for i in range(4):
        cx = x + 16 + i * 26
        cv.rect(cx, y + 28, 8, 34, INK)
    cv.rect(x + 4, y + 62, w - 8, 4, INK)
    cv.rect(x + 2, y + 68, w - 4, 4, INK)
    cv.rect(x, y + 74, w, 4, INK)
    icon(cv, x + w // 2 - 11, y + 44, "court")


def draw_map_band(cv, y, h):
    draw_text(cv, 12, y + 4, "THE DAY ON THE MAP", 2, INK)
    draw_text(cv, W - 12 - text_w("12 STORIES MARKED", 1), y + 8,
              "12 STORIES MARKED", 1, FAINT)
    draw_map(cv, 8, y + 26, W - 16, h - 34, MAP_MARKERS)
    labels = [("N. AMERICA", -100, 55), ("S. AMERICA", -60, -15),
              ("EUROPE", -15, 58), ("AFRICA", 20, 5), ("ASIA", 95, 55),
              ("AUSTRALIA", 134, -25)]
    for name, lon, lat in labels:
        lx = 8 + int((lon + 180.0) / 360.0 * (W - 16))
        ly = y + 26 + int((80.0 - lat) / 140.0 * (h - 34))
        draw_text(cv, lx - text_w(name, 1) // 2, ly, name, 1, (70, 76, 66))


def draw_grid(cv, y0):
    # section legend
    lx = 12
    draw_text(cv, lx, y0 + 2, "SECTIONS:", 1, FAINT)
    lx += text_w("SECTIONS: ", 1) + 6
    for name, color in SECTIONS.items():
        cv.rect(lx, y0, 10, 10, color)
        lx += 14
        draw_text(cv, lx, y0 + 2, name, 1, INK)
        lx += text_w(name, 1) + 14
    gy = y0 + 18
    cols = 3
    rows = 12
    cw = 333
    ch = 42
    gap = 8
    for idx, (section, label, kind, _mark) in enumerate(STORIES):
        col = idx % cols
        row = idx // cols
        x = 4 + col * (cw + gap)
        yy = gy + row * (ch + 1)
        color = SECTIONS[section]
        cv.rect(x, yy, 3, ch, color)
        cv.rect(x + 3, yy, cw - 3, ch, PANEL)
        cv.rect(x + 3, yy + ch - 1, cw - 3, 1, (200, 194, 180))
        num = "%02d" % (idx + 1)
        draw_text(cv, x + 8, yy + 3, num, 1, color)
        draw_text(cv, x + 26, yy + 3, section, 1, FAINT)
        icon(cv, x + cw - 26, yy + 2, kind)
        draw_para(cv, x + 8, yy + 13, cw - 40, label, 2, INK, leading=15)
    return gy + rows * (ch + 1)


def draw_footer(cv, y):
    cv.rect(0, y, W, 1, RULE)
    msg = ("FRIDAY 20 NOVEMBER 2026 - 36 STORIES FROM SIX SECTIONS - "
           "DRAWN BY AN AI AGENT FOR MAKE.FUN")
    draw_text(cv, (W - text_w(msg, 1)) // 2, y + 5, msg, 1, FAINT)


def build():
    cv = Canvas(W, H, PAPER)
    draw_masthead(cv)
    draw_lead(cv, 8, 112, 500, 186, "LEAD - WORLD",
              ("TRUMP, XI AND", "PUTIN MEET IN CHINA"),
              "First three-way summit ends with a peace declaration "
              "on nuclear arms and global security.", art_summit)
    draw_lead(cv, 516, 112, 500, 186, "LEAD - WORLD",
              ("COURT: MYANMAR", "COMMITTED GENOCIDE"),
              "The ICJ rules on the Rohingya crackdown of 2017. "
              "The verdict cannot be appealed.", art_court)
    draw_map_band(cv, 306, 164)
    end_y = draw_grid(cv, 478)
    draw_footer(cv, end_y)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    cv = build()
    data = encode_png(W, H, bytes(cv.px))
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
