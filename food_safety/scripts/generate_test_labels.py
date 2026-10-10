"""Generate OCR-friendly synthetic ingredient labels for system testing."""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[3] / "media" / "test_labels"
# When run as manage.py command, path differs — use cwd fallback
if not (Path.cwd() / "manage.py").exists():
    OUT = Path("media/test_labels")
else:
    OUT = Path.cwd() / "media" / "test_labels"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


LABELS = [
    {
        "file": "01_candy_unsafe_E171_E120.png",
        "title": "Rainbow Candy / Helwa Mulawwana",
        "barcode": "6223000000002",
        "expect": "UNSAFE",
        "lines": [
            "INGREDIENTS:",
            "Sugar, Glucose Syrup,",
            "Titanium Dioxide (E171),",
            "Carmines (E120),",
            "Citric Acid (E330), Flavor.",
            "",
            "Arabic names also match:",
            "Titanium Dioxide E171",
            "Carmines E120",
        ],
    },
    {
        "file": "02_biscuit_warning_E471.png",
        "title": "Crispy Biscuit",
        "barcode": "6223000000001",
        "expect": "WARNING",
        "lines": [
            "INGREDIENTS:",
            "Wheat Flour, Sugar, Palm Oil,",
            "Mono- and Diglycerides (E471),",
            "Lecithin (E322), Salt.",
        ],
    },
    {
        "file": "03_lemon_drink_safe_E330.png",
        "title": "Lemon Drink",
        "barcode": "6223000000003",
        "expect": "SAFE",
        "lines": [
            "INGREDIENTS:",
            "Water, Sugar, Lemon Juice,",
            "Citric Acid (E330), Natural Flavor.",
        ],
    },
    {
        "file": "04_jelly_unsafe_E131.png",
        "title": "Blue Jelly",
        "barcode": "6223000000099",
        "expect": "UNSAFE",
        "lines": [
            "INGREDIENTS:",
            "Sugar, Gelatin, Water,",
            "Patent Blue V (E131),",
            "Citric Acid (E330).",
        ],
    },
    {
        "file": "05_snack_unsafe_E173_E175.png",
        "title": "Sparkle Snack",
        "barcode": "6223000000088",
        "expect": "UNSAFE",
        "lines": [
            "Contains: Aluminium (E173),",
            "Gold metallic (E175),",
            "Sugar, Palm Oil, Salt.",
        ],
    },
    {
        "file": "06_ocr_hard_mixed_case.png",
        "title": "Kids Gummy Mix",
        "barcode": "6223000000077",
        "expect": "UNSAFE",
        "lines": [
            "Ingredients: glucose, sugar,",
            "colour: e171 / titanium dioxide,",
            "colour: e120, acid: e330,",
            "flavouring.",
        ],
    },
]


def render_label(lab: dict) -> Path:
    w, h = 900, 1200
    img = Image.new("RGB", (w, h), "#FFFDF8")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, 110], fill="#1B3A4B")
    draw.text((40, 28), lab["title"], fill="white", font=_font(28))
    draw.text(
        (40, 70),
        f"Barcode {lab['barcode']}  |  Expected {lab['expect']}",
        fill="#B8D4C8",
        font=_font(18),
    )
    y = 150
    draw.text((40, y), "Ingredient List", fill="#1B3A4B", font=_font(26))
    y += 55
    draw.rectangle([40, y, w - 40, y + 2], fill="#2E7D32")
    y += 30
    for line in lab["lines"]:
        draw.text((50, y), line, fill="#222222", font=_font(28))
        y += 42
    draw.rectangle([0, h - 90, w, h], fill="#F4F7F6")
    draw.text(
        (40, h - 60),
        "Food Safety Test Label — OCR sample (not a real product)",
        fill="#607D8B",
        font=_font(16),
    )
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / lab["file"]
    img.save(path, "PNG")
    return path


def render_phone_crop() -> Path:
    w, h = 720, 960
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, w - 20, h - 20], outline="#333", width=3)
    y = 50
    draw.text((40, y), "Rainbow Candy", fill="black", font=_font(32))
    y += 50
    draw.text((40, y), "Net wt 100g", fill="#555", font=_font(20))
    y += 50
    for line in [
        "Ingredients:",
        "Sugar, Glucose Syrup,",
        "E171 Titanium Dioxide,",
        "E120 Carmines,",
        "E330 Citric Acid.",
    ]:
        draw.text((40, y), line, fill="black", font=_font(26))
        y += 40
    path = OUT / "07_phone_crop_E171_E120.png"
    img.save(path, "PNG")
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for lab in LABELS:
        p = render_label(lab)
        print("wrote", p)
    print("wrote", render_phone_crop())
    (OUT / "README.txt").write_text(
        """Test product labels for Food Safety OCR / Rules Engine

How to use:
1. Open /scan/ (image OCR or manual verify)
2. Upload a PNG from this folder
3. Compare result with Expected status

Files:
01_candy_unsafe_E171_E120.png     -> UNSAFE (E171, E120)  barcode 6223000000002
02_biscuit_warning_E471.png       -> WARNING (E471)       barcode 6223000000001
03_lemon_drink_safe_E330.png      -> SAFE (E330)          barcode 6223000000003
04_jelly_unsafe_E131.png          -> UNSAFE (E131)
05_snack_unsafe_E173_E175.png     -> UNSAFE (E173, E175)
06_ocr_hard_mixed_case.png        -> UNSAFE (lowercase e171/e120)
07_phone_crop_E171_E120.png       -> UNSAFE compact crop

Synthetic labels for testing only.
""",
        encoding="utf-8",
    )
    print("OUT", OUT.resolve())


if __name__ == "__main__":
    main()
