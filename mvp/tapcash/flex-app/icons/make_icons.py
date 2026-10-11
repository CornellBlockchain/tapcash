"""Draw the TapCash "D · Tilt" logo as Flex/Stax device icons (black on white).

Same geometry as the Figma logo, with thicker strokes so it survives 32-64 px.
Run inside the ledger-app-dev-tools image (it has Pillow), from flex-app/:
  python3 icons/make_icons.py
"""
from PIL import Image, ImageDraw

S = 8  # supersampling: draw on a 512*S canvas
STROKE, ARC_STROKE = 28, 24  # in 512-px logo units (Figma logo uses 14)


def draw_logo(marks=True):
    im = Image.new("L", (512 * S, 512 * S), 255)
    d = ImageDraw.Draw(im)
    u = lambda *v: [x * S for x in v]
    d.rounded_rectangle(u(176, 136, 336, 376), radius=32 * S, outline=0, width=STROKE * S)
    d.rounded_rectangle(u(206, 290, 306, 346), radius=12 * S, outline=0, width=(STROKE - 10) * S)
    # vibration marks on the top-right and bottom-left corners (PIL angles: clockwise from 3 o'clock)
    for (cx, cy), (a0, a1) in ([((308, 164), (275, 355)), ((204, 348), (95, 175))] if marks else []):
        for r, trim in [(74, 4), (124, 12)]:
            d.arc(u(cx - r, cy - r, cx + r, cy + r), a0 + trim, a1 - trim, fill=0, width=ARC_STROKE * S)
    im = im.rotate(12, resample=Image.BICUBIC, fillcolor=255)  # SVG rotate(-12) = 12 deg counter-clockwise
    return im.crop(Image.eval(im, lambda p: 255 - p).getbbox())


def save(src, size, path, levels):
    side = int(max(src.size) * 1.08)  # small margin so marks don't touch the edge
    sq = Image.new("L", (side, side), 255)
    sq.paste(src, ((side - src.width) // 2, (side - src.height) // 2))
    small = sq.resize((size, size), Image.LANCZOS)
    if levels == 2:
        small = small.point(lambda p: 0 if p < 128 else 255)
    else:  # 16 grey levels (4bpp), like the boilerplate's 40 px icon
        small = small.point(lambda p: round(p / 17) * 17)
    small.convert("P").save(path)


logo = draw_logo()
save(logo, 40, "icons/tapcash_40px.gif", 16)  # Flex dashboard icon
save(logo, 32, "icons/tapcash_32px.gif", 2)   # Stax dashboard icon
save(draw_logo(marks=False), 64, "glyphs/tapcash_64px.gif", 2)  # in-app home + review: device only, fills the frame
