#!/usr/bin/env python3
"""tinyfont.py -- write the two TrueType fonts the tests embed,
tests/data/tiny.ttf and tests/data/tiny-bold.ttf.

They are fonts only in form: every character is a rectangle, as wide and as
high as its code makes it, and e-acute is composed of the e and the full
stop. That is enough to test what the package does with a font -- finding a
glyph in either kind of character map, measuring, subsetting with the parts
of a composed glyph, embedding -- with files of a few kilobytes that belong
to nobody else. The regular font has a character beyond the basic plane and
so a map of format 12; the bold one has format 4 only.
"""
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "tests", "data")

LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,-:()"
OTHER = [0x00E9, 0x03A9, 0x0416, 0x20AC, 0x4E2D]
BEYOND = [0x1F600]


def rectangle(x0, y0, x1, y1):
    flags = bytes([1, 1, 1, 1])
    xs = struct.pack(">4h", x0, 0, x1 - x0, 0)
    ys = struct.pack(">4h", y0, y1 - y0, 0, y0 - y1)
    body = struct.pack(">hhhhh", 1, x0, y0, x1, y1) + struct.pack(">HH", 3, 0) + flags + xs + ys
    return body + b"\0" * (len(body) % 2)


def composed(first, second, dx, dy, box):
    body = struct.pack(">hhhhh", -1, *box)
    body += struct.pack(">HHhh", 0x0023, first, 0, 0)
    body += struct.pack(">HHhh", 0x0003, second, dx, dy)
    return body + b"\0" * (len(body) % 2)


def table_sum(data):
    data += b"\0" * (-len(data) % 4)
    return sum(struct.unpack(">%dI" % (len(data) // 4), data)) & 0xFFFFFFFF


def build(family, style_name, mac_style, weight, beyond):
    codes = [ord(c) for c in LATIN] + OTHER + (BEYOND if beyond else [])
    glyph_of = {0x20: 1}
    glyphs = [rectangle(50, 0, 450, 700), b""]
    advances = [500, 250]
    for code in codes:
        if code == 0xE9:
            continue
        width = 300 + (code * 37) % 400 + weight
        height = 400 + (code * 53) % 350
        glyph_of[code] = len(glyphs)
        glyphs.append(rectangle(40, 0, width - 40, height))
        advances.append(width)
    # e-acute: the e with the full stop above it
    e, stop = glyph_of[ord("e")], glyph_of[ord(".")]
    glyph_of[0xE9] = len(glyphs)
    glyphs.append(composed(e, stop, 0, 760, (40, 0, advances[e] - 40, 1500)))
    advances.append(advances[e])
    count = len(glyphs)

    loca, glyf = [], b""
    for g in glyphs:
        loca.append(len(glyf) // 2)
        glyf += g
    loca.append(len(glyf) // 2)
    x_max = max(advances)

    head = struct.pack(">IIIIHH", 0x00010000, 0x00010000, 0, 0x5F0F3CF5, 0x000B, 1000)
    head += b"\0" * 16 + struct.pack(">hhhhHHhhh", 0, 0, x_max, 1500, mac_style, 8, 2, 0, 0)
    hhea = struct.pack(">IhhhHhhhhhh", 0x00010000, 800, -200, 0, x_max, 0, 0, x_max, 1, 0, 0)
    hhea += b"\0" * 8 + struct.pack(">hH", 0, count)
    maxp = struct.pack(">IH13H", 0x00010000, count, 4, 1, 8, 2, 2, 0, 0, 0, 0, 0, 0, 2, 1)
    hmtx = b"".join(struct.pack(">Hh", a, 40) for a in advances)
    loca_table = struct.pack(">%dH" % len(loca), *loca)
    post = struct.pack(">IIhhI", 0x00030000, 0, -100, 50, 0) + b"\0" * 16

    # the character maps: format 4 over the basic plane, format 12 over all
    basic = sorted(c for c in glyph_of if c < 0x10000)
    runs = []
    for code in basic:
        if runs and code == runs[-1][1] + 1 and glyph_of[code] == glyph_of[runs[-1][1]] + 1:
            runs[-1][1] = code
        else:
            runs.append([code, code])
    ends = [r[1] for r in runs] + [0xFFFF]
    starts = [r[0] for r in runs] + [0xFFFF]
    deltas = [(glyph_of[r[0]] - r[0]) & 0xFFFF for r in runs] + [1]
    n = len(ends)
    power = 1
    while power * 2 <= n:
        power *= 2
    four = struct.pack(">HHHHHH", 4, 16 + 8 * n, 0, n * 2, power * 2, power.bit_length() - 1)
    four += struct.pack(">H", n * 2 - power * 2)
    four += struct.pack(">%dH" % n, *ends) + b"\0\0" + struct.pack(">%dH" % n, *starts)
    four += struct.pack(">%dH" % n, *deltas) + struct.pack(">%dH" % n, *([0] * n))
    subtables = [(3, 1, four)]
    if beyond:
        every = sorted(glyph_of)
        groups = b"".join(struct.pack(">III", c, c, glyph_of[c]) for c in every)
        twelve = struct.pack(">HHIII", 12, 0, 16 + len(groups), 0, len(every)) + groups
        subtables.append((3, 10, twelve))
    cmap = struct.pack(">HH", 0, len(subtables))
    offset = 4 + 8 * len(subtables)
    for platform, encoding, sub in subtables:
        cmap += struct.pack(">HHI", platform, encoding, offset)
        offset += len(sub)
    for _, _, sub in subtables:
        cmap += sub

    names = [(1, family), (2, style_name), (4, family + " " + style_name),
             (6, family.replace(" ", "") + "-" + style_name.replace(" ", ""))]
    strings = b""
    records = b""
    for name_id, text in names:
        encoded = text.encode("utf-16-be")
        records += struct.pack(">HHHHHH", 3, 1, 0x409, name_id, len(encoded), len(strings))
        strings += encoded
    name = struct.pack(">HHH", 0, len(names), 6 + 12 * len(names)) + records + strings

    tables = sorted([(b"cmap", cmap), (b"glyf", glyf), (b"head", head), (b"hhea", hhea),
                     (b"hmtx", hmtx), (b"loca", loca_table), (b"maxp", maxp),
                     (b"name", name), (b"post", post)])
    count_tables = len(tables)
    power = 1
    while power * 2 <= count_tables:
        power *= 2
    font = struct.pack(">IHHHH", 0x00010000, count_tables, power * 16,
                       power.bit_length() - 1, count_tables * 16 - power * 16)
    offset = 12 + 16 * count_tables
    body = b""
    for tag, data in tables:
        font += struct.pack(">4sIII", tag, table_sum(data), offset, len(data))
        padded = data + b"\0" * (-len(data) % 4)
        body += padded
        offset += len(padded)
    font += body
    # the checksum adjustment in the head table
    at = font.index(struct.pack(">I", 0x5F0F3CF5)) - 4
    adjustment = (0xB1B0AFBA - table_sum(font)) & 0xFFFFFFFF
    return font[:at] + struct.pack(">I", adjustment) + font[at + 4:]


def main():
    with open(os.path.join(DATA, "tiny.ttf"), "wb") as f:
        f.write(build("Tiny", "Regular", 0, 0, True))
    with open(os.path.join(DATA, "tiny-bold.ttf"), "wb") as f:
        f.write(build("Tiny", "Bold", 1, 120, False))


if __name__ == "__main__":
    main()
