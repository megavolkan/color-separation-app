"""Uygulama simgesini (1024 px PNG) üretir: üst üste binen C, M, Y daireleri."""

import sys

from PIL import Image, ImageChops, ImageDraw

S = 1024
out = sys.argv[1] if len(sys.argv) > 1 else "icon.png"  # isteğe bağlı 2. argüman: .ico yolu

bg = Image.new("RGB", (S, S), "white")
img = bg.copy()
r = 260
for (cx, cy), color in [
    ((S // 2, 400), (0, 174, 239)),
    ((S // 2 - 150, 640), (236, 0, 140)),
    ((S // 2 + 150, 640), (255, 242, 0)),
]:
    layer = Image.new("RGB", (S, S), "white")
    ImageDraw.Draw(layer).ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    img = ImageChops.multiply(img, layer)

# macOS tarzı yuvarlatılmış kare maske
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=200, fill=255)
icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
icon.paste(img, (0, 0), mask)
icon.save(out)
if len(sys.argv) > 2:  # Windows simgesi
    icon.save(sys.argv[2], sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
