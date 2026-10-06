"""Simple part photos for the sample machining workbook."""

from __future__ import annotations

import base64
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
NAVY = (19, 41, 61)
BRASS = (196, 123, 43)
STEEL = (90, 107, 122)

PARTS = [
    {
        "number": "PN-1042",
        "file": "assets/parts/pn-1042.png",
        "shape": "shaft",
        "spec": "OD 25.00 ±0.01 mm, length 140 mm, Ra 0.8",
        "rm": "Ø32 × 180 mm bar",
        "process": "CNC Turning, Grinding",
        "tools": "Soft jaws, steady rest",
        "special": "CMM final inspection",
        "inserts": "DNMG 150608",
    },
    {
        "number": "PN-1188",
        "file": "assets/parts/pn-1188.png",
        "shape": "housing",
        "spec": "Bore 42 H7, face squareness 0.02 mm",
        "rm": "80 × 80 × 50 mm block",
        "process": "CNC Milling, Boring",
        "tools": "Machine vice, boring head",
        "special": "Bore gauge",
        "inserts": "CCMT 09T304",
    },
    {
        "number": "PN-2071",
        "file": "assets/parts/pn-2071.png",
        "shape": "bracket",
        "spec": "Hole pattern 2 × M8, thickness 12 mm",
        "rm": "100 × 60 × 16 mm plate",
        "process": "CNC Milling, Drilling & Tapping",
        "tools": "Hold-down clamps",
        "special": "NA",
        "inserts": "APMT 1135",
    },
    {
        "number": "PN-2210",
        "file": "assets/parts/pn-2210.png",
        "shape": "flange",
        "spec": "PCD 70 mm, 4 × Ø6.6 through, face Ra 1.6",
        "rm": "Ø90 × 22 mm blank",
        "process": "CNC Turning, CNC Milling",
        "tools": "Soft jaws, drill jig",
        "special": "Anodise after machining",
        "inserts": "WNMG 080408",
    },
    {
        "number": "PN-3055",
        "file": "assets/parts/pn-3055.png",
        "shape": "gear",
        "spec": "Module 1.5, 30 teeth, bore 20 H7",
        "rm": "Ø55 × 20 mm blank",
        "process": "CNC Turning, Gear hobbing",
        "tools": "Expanding mandrel",
        "special": "Gear profile check",
        "inserts": "VBMT 160404",
    },
    {
        "number": "PN-3180",
        "file": "assets/parts/pn-3180.png",
        "shape": "manifold",
        "spec": "4 ports 1/8 BSP, cross-hole burr free",
        "rm": "70 × 40 × 30 mm block",
        "process": "CNC Milling, Drilling",
        "tools": "Side clamps, spot drill",
        "special": "Pressure test 10 bar",
        "inserts": "APMT 1135",
    },
    {
        "number": "PN-4022",
        "file": "assets/parts/pn-4022.png",
        "shape": "bushing",
        "spec": "OD 18 h6, ID 12 H7, length 25 mm",
        "rm": "Ø22 × 40 mm bar",
        "process": "CNC Turning",
        "tools": "Collet chuck",
        "special": "NA",
        "inserts": "DCMT 11T304",
    },
    {
        "number": "PN-4156",
        "file": "assets/parts/pn-4156.png",
        "shape": "plate",
        "spec": "120 × 80 × 8 mm, 4 × Ø5.5 holes",
        "rm": "130 × 90 × 10 mm plate",
        "process": "CNC Milling, Deburr",
        "tools": "Vacuum fixture",
        "special": "NA",
        "inserts": "APKT 1604",
    },
    {
        "number": "PN-5008",
        "file": "assets/parts/pn-5008.png",
        "shape": "pin",
        "spec": "Ø8 m6 × 30 mm, both ends chamfered",
        "rm": "Ø10 × 45 mm bar",
        "process": "CNC Turning",
        "tools": "Guide bush",
        "special": "NA",
        "inserts": "DCGT 11T302",
    },
    {
        "number": "PN-5124",
        "file": "assets/parts/pn-5124.png",
        "shape": "valve",
        "spec": "Seat angle 30°, stem bore 6 H7",
        "rm": "Ø28 × 50 mm bar",
        "process": "CNC Turning, CNC Milling",
        "tools": "Live centre, small vice",
        "special": "Seat blue check",
        "inserts": "VBMT 160404",
    },
]


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_shape(draw: ImageDraw.ImageDraw, shape: str) -> None:
    if shape == "shaft":
        draw.rounded_rectangle((30, 68, 210, 92), radius=12, fill=STEEL)
        draw.rectangle((70, 60, 170, 100), fill=NAVY)
    elif shape == "housing":
        draw.rounded_rectangle((70, 36, 170, 124), radius=8, outline=NAVY, width=4)
        draw.ellipse((96, 56, 144, 104), outline=BRASS, width=4)
    elif shape == "bracket":
        draw.polygon([(48, 110), (48, 48), (78, 48), (78, 86), (188, 86), (188, 110)], fill=NAVY)
    elif shape == "flange":
        draw.ellipse((78, 34, 162, 118), outline=NAVY, width=6)
        for center in ((100, 56), (140, 56), (100, 96), (140, 96)):
            draw.ellipse((center[0] - 5, center[1] - 5, center[0] + 5, center[1] + 5), fill=BRASS)
    elif shape == "gear":
        draw.regular_polygon((120, 76, 36), 10, rotation=18, fill=BRASS)
        draw.ellipse((104, 60, 136, 92), fill=(255, 255, 255))
    elif shape == "manifold":
        draw.rounded_rectangle((58, 48, 182, 108), radius=6, fill=NAVY)
        for x in (78, 108, 138, 168):
            draw.ellipse((x - 6, 70, x + 6, 86), fill=BRASS)
    elif shape == "bushing":
        draw.ellipse((88, 40, 152, 112), outline=NAVY, width=10)
    elif shape == "plate":
        draw.rounded_rectangle((40, 50, 200, 108), radius=4, outline=NAVY, width=4)
        for center in ((60, 66), (180, 66), (60, 92), (180, 92)):
            draw.ellipse((center[0] - 4, center[1] - 4, center[0] + 4, center[1] + 4), fill=BRASS)
    elif shape == "pin":
        draw.rounded_rectangle((78, 72, 168, 84), radius=6, fill=STEEL)
    else:
        draw.polygon([(120, 36), (162, 70), (146, 118), (94, 118), (78, 70)], outline=NAVY, width=4)
        draw.rectangle((112, 70, 128, 108), fill=BRASS)


def ensure_part_photos() -> None:
    label_font = _font(14)
    for part in PARTS:
        path = ROOT / part["file"]
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (240, 160), "white")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((2, 2, 237, 157), radius=8, outline=NAVY, width=2)
        _draw_shape(draw, part["shape"])
        draw.text((12, 132), part["number"], fill=NAVY, font=label_font)
        image.save(path)


def png_bytes(relative: str, size: tuple[int, int] = (64, 42)) -> bytes:
    """Small PNG for an Excel cell. Empty when the picture file is missing."""
    if not relative:
        return b""
    path = ROOT / str(relative)
    if not path.is_file():
        return b""
    image = Image.open(path).convert("RGBA")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@lru_cache(maxsize=32)
def photo_data_uri(relative: str) -> str:
    if not relative:
        return ""
    path = ROOT / relative
    if not path.exists():
        return ""
    image = Image.open(path).convert("RGBA")
    image.thumbnail((110, 60), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
