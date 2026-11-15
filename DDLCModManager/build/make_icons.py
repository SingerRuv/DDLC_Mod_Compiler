"""Generate the monochrome line icons used by the GUI.

Run from the repository root:
    python build/make_icons.py

Pillow is only a development/build-time dependency.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SIZE = 20
SCALE = 4
WIDTH = 2


def _canvas(color):
    return Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), (0, 0, 0, 0))


def _line(draw, points, color, width=WIDTH):
    scaled = [(x * SCALE, y * SCALE) for x, y in points]
    draw.line(scaled, fill=color, width=width * SCALE, joint="curve")


def _rect(draw, box, color, width=WIDTH, radius=0):
    x1, y1, x2, y2 = [v * SCALE for v in box]
    draw.rounded_rectangle((x1, y1, x2, y2), radius=radius * SCALE,
                           outline=color, width=width * SCALE)


def _ellipse(draw, box, color, width=WIDTH):
    x1, y1, x2, y2 = [v * SCALE for v in box]
    draw.ellipse((x1, y1, x2, y2), outline=color, width=width * SCALE)


def _folder(draw, color):
    _line(draw, [(2, 7), (2, 17), (18, 17), (18, 7), (10, 7),
                 (8, 4), (2, 4), (2, 7)], color)


def _icon(name, color):
    image = _canvas(color)
    draw = ImageDraw.Draw(image)
    if name == "launcher":
        for x, y in ((3, 3), (11, 3), (3, 11), (11, 11)):
            _rect(draw, (x, y, x + 6, y + 6), color, radius=1)
    elif name == "compiler":
        _ellipse(draw, (6, 6, 14, 14), color)
        _ellipse(draw, (9, 9, 11, 11), color)
        for p in ((10, 2, 10, 6), (10, 14, 10, 18),
                  (2, 10, 6, 10), (14, 10, 18, 10),
                  (4.3, 4.3, 6.8, 6.8), (13.2, 13.2, 15.7, 15.7),
                  (15.7, 4.3, 13.2, 6.8), (6.8, 13.2, 4.3, 15.7)):
            draw.line([(p[0] * SCALE, p[1] * SCALE),
                       (p[2] * SCALE, p[3] * SCALE)],
                      fill=color, width=2 * SCALE)
    elif name == "folder":
        _folder(draw, color)
    elif name == "archive":
        _rect(draw, (3, 4, 17, 17), color, radius=1)
        _line(draw, [(3, 8), (17, 8), (17, 13), (3, 13)], color, 1)
        _line(draw, [(8, 5), (12, 5)], color, 2)
    elif name == "refresh":
        draw.arc((3 * SCALE, 3 * SCALE, 17 * SCALE, 17 * SCALE),
                 start=35, end=310, fill=color, width=WIDTH * SCALE)
        _line(draw, [(14, 3), (17, 3), (17, 6)], color)
    elif name == "add-folder":
        _folder(draw, color)
        _line(draw, [(12, 11), (12, 16)], color, 1)
        _line(draw, [(9.5, 13.5), (14.5, 13.5)], color, 1)
    elif name == "import":
        _line(draw, [(10, 3), (10, 13), (6, 9), (10, 13), (14, 9)], color)
        _line(draw, [(3, 15), (3, 17), (17, 17), (17, 15)], color)
    elif name == "build":
        _line(draw, [(4, 15), (11, 8), (13, 10), (6, 17)], color)
        _line(draw, [(11, 6), (14, 3), (17, 6), (14, 9)], color)
    elif name == "cancel":
        _line(draw, [(5, 5), (15, 15)], color)
        _line(draw, [(15, 5), (5, 15)], color)
    elif name == "play":
        draw.polygon([(6 * SCALE, 4 * SCALE), (16 * SCALE, 10 * SCALE),
                      (6 * SCALE, 16 * SCALE)], outline=color)
        draw.line([(6 * SCALE, 4 * SCALE), (6 * SCALE, 16 * SCALE)],
                  fill=color, width=WIDTH * SCALE)
    elif name == "open-folder":
        _folder(draw, color)
        _line(draw, [(9, 12), (14, 12), (12, 10)], color, 1)
        _line(draw, [(14, 12), (12, 14)], color, 1)
    elif name == "output-folder":
        _folder(draw, color)
        _line(draw, [(6, 13), (14, 13), (12, 11)], color, 1)
        _line(draw, [(14, 13), (12, 15)], color, 1)
    elif name == "sun":
        _ellipse(draw, (7, 7, 13, 13), color)
        for p in ((10, 2, 10, 5), (10, 15, 10, 18),
                  (2, 10, 5, 10), (15, 10, 18, 10),
                  (4, 4, 6, 6), (14, 14, 16, 16),
                  (16, 4, 14, 6), (6, 14, 4, 16)):
            _line(draw, [p[:2], p[2:]], color, 1)
    elif name == "moon":
        draw.arc((3 * SCALE, 2 * SCALE, 18 * SCALE, 18 * SCALE),
                 start=55, end=305, fill=color, width=WIDTH * SCALE)
        _line(draw, [(12, 3), (16, 3), (16, 7)], color, 1)
    else:
        raise SystemExit("Unknown icon: %s" % name)
    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


ICONS = ("launcher", "compiler", "folder", "archive", "refresh",
         "add-folder", "import", "build", "cancel", "play",
         "open-folder", "output-folder", "sun", "moon")
COLORS = {"light": (59, 70, 84, 255), "dark": (230, 233, 239, 255)}


def main():
    for variant, color in COLORS.items():
        target = ROOT / "icons" / variant
        target.mkdir(parents=True, exist_ok=True)
        for name in ICONS:
            _icon(name, color).save(target / (name + ".png"))
    print("Generated %d icons for light/dark." % len(ICONS))


if __name__ == "__main__":
    main()
