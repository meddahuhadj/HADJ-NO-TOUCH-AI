#!/usr/bin/env python3
"""
HADJ NO-TOUCH AI — icon generator.

Draws the brand mark ("H" glyph + motion cursor, mission-control palette)
with Pillow and renders, from the same local glyph:

  icons/icon.svg                 brand glyph (SVG, also used as favicon)
  icons/icon-192.png             install icon, 192x192
  icons/icon-512.png             install icon, 512x512
  icons/icon-maskable-512.png    maskable icon, full-bleed square, safe-zone glyph
  assets/noise.png               film-grain texture used by the page background

Run:  py -3.12 make_icons.py        (or: python make_icons.py)
Needs: Pillow (PIL)  ->  pip install pillow
"""

import os
import random
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, "icons")
ASSET_DIR = os.path.join(HERE, "assets")

S = 1024  # supersampled master size, downscaled on save

# Palette (matches styles.css tokens)
CYAN = (76, 201, 255)
PALE = (216, 242, 255)
VIO = (139, 123, 255)
GREEN = (61, 220, 151)

# ---------------------------------------------------------------- helpers

def vertical_gradient(size, top, bottom):
    """RGBA image, top->bottom linear gradient (fully opaque)."""
    img = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (size - 1, y)], fill=c + (255,))
    return img


def horizontal_gradient(size, left, right):
    """RGBA image, left->right linear gradient (fully opaque)."""
    img = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(img)
    for x in range(size):
        t = x / (size - 1)
        c = tuple(int(left[i] + (right[i] - left[i]) * t) for i in range(3))
        d.line([(x, 0), (x, size - 1)], fill=c + (255,))
    return img


def radial_alpha(size, cx, cy, radius, strength=255):
    """L (alpha) image with a soft radial glow centred on (cx, cy)."""
    band = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(band)
    bands = 40
    for i in range(bands):
        t = i / (bands - 1)
        r = radius * (0.12 + 0.88 * (t ** 1.35))
        a = int(strength * (1 - t) ** 2)
        if r <= 0:
            continue
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=a)
    return band.filter(ImageFilter.GaussianBlur(radius * 0.06))


def rounded_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


# ---------------------------------------------------------------- drawing

G_BG_TOP = (15, 41, 84)
G_BG_BOT = (5, 9, 18)


def base_background(size, rounded):
    """Deep mission-control floor: gradient + cyan glow + sheen."""
    img = vertical_gradient(size, G_BG_TOP, G_BG_BOT)

    # cyan glow, upper right of centre
    glow_a = radial_alpha(size, int(size * 0.6), int(size * 0.3), int(size * 0.62), 120)
    glow = Image.new("RGBA", (size, size), CYAN + (255,))
    glow.putalpha(glow_a)
    img.alpha_composite(glow)

    # soft sheen, top third
    sheen_a = radial_alpha(size, int(size * 0.38), int(size * 0.22), int(size * 0.5), 26)
    sheen = Image.new("RGBA", (size, size), PALE + (255,))
    sheen.putalpha(sheen_a)
    img.alpha_composite(sheen)

    # faint violet bloom at the bottom-left corner
    vio_a = radial_alpha(size, int(size * 0.12), int(size * 0.95), int(size * 0.45), 40)
    vio = Image.new("RGBA", (size, size), VIO + (255,))
    vio.putalpha(vio_a)
    img.alpha_composite(vio)

    if rounded:
        d = ImageDraw.Draw(img)
        # hairline inner border
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=214,
                            outline=(124, 195, 255, 90), width=6)
        img.putalpha(rounded_mask(size, 220))
    return img


def glyph(size):
    """The brand mark: thick 'H' + air-motion cursor, transparent bg."""
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    s = size

    # --- H shape (mask) ---
    mask = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(mask)
    bar_w = int(s * 0.128)
    cross_h = int(s * 0.128)
    top = int(s * 0.225)
    bottom = int(s * 0.75)
    left_x = int(s * 0.352)
    right_x = int(s * 0.521)
    cy_top = int(s * 0.42)

    d.rounded_rectangle([left_x, top, left_x + bar_w, bottom], radius=int(s * 0.05), fill=255)
    d.rounded_rectangle([right_x, top, right_x + bar_w, bottom], radius=int(s * 0.05), fill=255)
    d.rounded_rectangle([left_x, cy_top, right_x + bar_w, cy_top + cross_h], radius=int(s * 0.04), fill=255)

    # --- fill the H with a cyan->pale gradient ---
    grad = horizontal_gradient(s, (60, 180, 240), (228, 246, 255))
    out.paste(grad, (0, 0), mask)

    # --- motion cursor sweeping above the glyph ---
    d = ImageDraw.Draw(out)
    y_line = int(s * 0.152)
    x0, x1 = int(s * 0.2), int(s * 0.665)

    # track path
    d.line([(x0, y_line), (x1, y_line)], fill=(124, 195, 255, 190), width=int(s * 0.012), joint="curve")

    # origin dot + arrowhead (the "air pointer")
    r = int(s * 0.015)
    d.ellipse([x0 - r, y_line - r, x0 + r, y_line + r], fill=(224, 244, 255, 235))
    head_w = int(s * 0.075)
    d.polygon(
        [(x1 - head_w, y_line - int(s * 0.034)),
         (x1 + head_w, y_line),
         (x1 - head_w, y_line + int(s * 0.034))],
        fill=(76, 201, 255, 235),
    )

    # tracker ring over the H's top-right corner
    cx, cy = right_x + bar_w // 2 + int(s * 0.02), top + int(s * 0.02)
    rr = int(s * 0.095)
    d.arc([cx - rr, cy - rr, cx + rr, cy + rr], start=-20, end=120,
          fill=(124, 195, 255, 170), width=int(s * 0.008))
    d.arc([cx - rr - int(s * 0.02), cy - rr - int(s * 0.02),
           cx + rr + int(s * 0.02), cy + rr + int(s * 0.02)], start=-20, end=120,
          fill=(76, 201, 255, 110), width=int(s * 0.008))

    return out


def assemble(rounded):
    img = base_background(S, rounded)
    g = glyph(S)
    if not rounded:
        # maskable: pull the glyph inside the safe zone
        scale = 0.9
        g = g.resize((int(S * scale), int(S * scale)), Image.LANCZOS)
        off = int(S * (1 - scale) / 2)
        img.alpha_composite(g, (off, off))
    else:
        img.alpha_composite(g, (0, 0))
    return img


def save_icon(img, path):
    res = 192 if "192" in path else 512
    img.resize((res, res), Image.LANCZOS).save(path, optimize=True)


def make_noise(path, size=128, seed=7):
    """Light film-grain texture; page overlays it with mix-blend-mode: overlay."""
    rnd = random.Random(seed)
    px = [rnd.randrange(56, 200) for _ in range(size * size)]
    img = Image.new("L", (size, size))
    img.putdata(px)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.convert("RGB").save(path, optimize=True)


SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0f2952"/>
      <stop offset="0.55" stop-color="#0a1426"/>
      <stop offset="1" stop-color="#05090f"/>
    </linearGradient>
    <linearGradient id="hg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#3cb4ee"/>
      <stop offset="1" stop-color="#e4f6ff"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.62" cy="0.3" r="0.62">
      <stop offset="0" stop-color="#4cc9ff" stop-opacity="0.5"/>
      <stop offset="1" stop-color="#4cc9ff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1024" height="1024" fill="url(#bg)"/>
  <rect width="1024" height="1024" fill="url(#glow)"/>
  <rect x="90" y="90" width="844" height="844" rx="220" fill="none"
        stroke="#7cc3ff" stroke-opacity="0.24" stroke-width="8"/>
  <g>
    <rect x="360" y="230" width="131" height="532" rx="52" fill="url(#hg)"/>
    <rect x="534" y="230" width="131" height="532" rx="52" fill="url(#hg)"/>
    <rect x="360" y="430" width="305" height="131" rx="42" fill="url(#hg)"/>
  </g>
  <g fill="none" stroke-linecap="round">
    <path d="M205 156 H 680" stroke="#7cc3ff" stroke-opacity="0.75" stroke-width="12"/>
    <path d="M592 104 A 128 128 0 0 1 756 220" stroke="#4cc9ff" stroke-opacity="0.55" stroke-width="8"/>
  </g>
  <circle cx="205" cy="156" r="17" fill="#e0f4ff"/>
  <path d="M644 121 L 782 156 L 644 191 Z" fill="#4cc9ff"/>
</svg>
"""


def main():
    os.makedirs(ICON_DIR, exist_ok=True)
    os.makedirs(ASSET_DIR, exist_ok=True)

    any_icon = assemble(rounded=True)
    save_icon(any_icon, os.path.join(ICON_DIR, "icon-512.png"))
    any_icon.resize((192, 192), Image.LANCZOS).save(os.path.join(ICON_DIR, "icon-192.png"), optimize=True)

    mask = assemble(rounded=False)
    mask.resize((512, 512), Image.LANCZOS).save(os.path.join(ICON_DIR, "icon-maskable-512.png"), optimize=True)

    with open(os.path.join(ICON_DIR, "icon.svg"), "w", encoding="utf-8") as f:
        f.write(SVG)

    make_noise(os.path.join(ASSET_DIR, "noise.png"))

    print("wrote:", ", ".join(
        os.path.join(ICON_DIR, n) for n in
        ["icon.svg", "icon-192.png", "icon-512.png", "icon-maskable-512.png"]
    ))
    print("wrote:", os.path.join(ASSET_DIR, "noise.png"))


if __name__ == "__main__":
    main()