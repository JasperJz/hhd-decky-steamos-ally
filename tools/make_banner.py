"""Render assets/store-banner.png (Decky store card image, 640x400).

Self-contained and deterministic: no network, only Pillow and a bundled or
system font. Re-run after editing the layout constants below:

    python tools/make_banner.py
"""
from PIL import Image, ImageDraw, ImageFont

W, H = 640, 400
S = 2  # supersample factor for smooth edges

BG_TOP = (26, 34, 51)
BG_BOTTOM = (13, 17, 23)
ACCENT = (102, 192, 244)
TEXT = (232, 237, 245)
MUTED = (159, 176, 195)
STROKE = (208, 227, 245)

FONT_CANDIDATES = [
    ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/seguisb.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",),
    ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",),
]


def font(size, bold=True):
    for group in FONT_CANDIDATES:
        for name in group[: 2 if bold else 1]:
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
    return ImageFont.load_default()


def rounded(draw, box, radius, **kw):
    draw.rounded_rectangle(box, radius=radius, **kw)


def gamepad(draw, cx, cy, s, stroke, width):
    # Body: wide rounded shape with the grip corners cut by the canvas.
    body_w, body_h = 3.0 * s, 1.62 * s
    rounded(draw, [cx - body_w / 2, cy - body_h / 2, cx + body_w / 2, cy + body_h / 2],
            0.72 * s, outline=stroke, width=width)
    # D-pad (left).
    arm = 0.46 * s
    draw.line([cx - 0.86 * s, cy - arm, cx - 0.86 * s, cy + arm], fill=stroke, width=width)
    draw.line([cx - 0.86 * s - arm, cy, cx - 0.86 * s + arm, cy], fill=stroke, width=width)
    # Lightning bolt (center-right of pad).
    bx, by, bs = cx + 0.28 * s, cy, 0.30 * s
    draw.polygon([(bx - 0.35 * bs, by - 1.35 * bs), (bx + 0.30 * bs, by - 1.35 * bs),
                  (bx - 0.02 * bs, by - 0.30 * bs), (bx + 0.45 * bs, by - 0.30 * bs),
                  (bx - 0.35 * bs, by + 1.35 * bs), (bx + 0.02 * bs, by + 0.25 * bs),
                  (bx - 0.45 * bs, by + 0.25 * bs)], outline=stroke, width=width)
    # Action buttons (right).
    for dx, dy in ((0.62, -0.18), (0.82, 0.02)):
        r = 0.055 * s
        draw.ellipse([cx + dx * s - r, cy + dy * s - r, cx + dx * s + r, cy + dy * s + r],
                     fill=stroke)


def render():
    img = Image.new("RGB", (W * S, H * S))
    d = ImageDraw.Draw(img)
    for y in range(H * S):
        t = y / (H * S - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM))
        d.line([(0, y), (W * S, y)], fill=color)
    # Soft glow behind the pad.
    glow = Image.new("L", (W * S, H * S), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([40 * S, 40 * S, 360 * S, 360 * S], fill=44)
    img = Image.composite(Image.new("RGB", img.size, ACCENT), img,
                          glow.point(lambda p: p))
    d = ImageDraw.Draw(img)

    gamepad(d, 150 * S, 205 * S, 84 * S, STROKE, max(3, round(3.2 * S)))

    title = font(52 * S)
    sub = font(23 * S, bold=False)
    d.text((300 * S, 148 * S), "HHD Decky", font=title, fill=TEXT)
    d.text((302 * S, 224 * S), "for SteamOS handhelds", font=sub, fill=MUTED)
    d.text((302 * S, 258 * S), "requires the HHD backend", font=sub, fill=MUTED)

    out = img.resize((W, H), Image.LANCZOS)
    return out


if __name__ == "__main__":
    import pathlib
    target = pathlib.Path(__file__).resolve().parent.parent / "assets" / "store-banner.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    render().save(target, optimize=True)
    print(target)
