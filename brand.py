"""Company identity for the local machining app."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

COMPANY_NAME = "Helix Precision"
TAGLINE = "Part manufacturing"

ROOT = Path(__file__).resolve().parent
LOGO_PATH = ROOT / "assets" / "logo.png"

NAVY = (19, 41, 61, 255)
BRASS = (196, 123, 43, 255)
STEEL = (232, 236, 240, 255)


def _gear_points(
    cx: float,
    cy: float,
    teeth: int,
    outer_r: float,
    root_r: float,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for tooth in range(teeth):
        start = -math.pi / 2 + (2 * math.pi * tooth / teeth)
        step = 2 * math.pi / teeth
        edges = (0.18, 0.38, 0.62, 0.82)
        radii = (root_r, outer_r, outer_r, root_r)
        for edge, radius in zip(edges, radii):
            angle = start + step * edge
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def ensure_logo(path: Path = LOGO_PATH) -> Path:
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, size - 9, size - 9), radius=52, fill=NAVY)
    center = size / 2
    draw.polygon(_gear_points(center, center, 8, 92, 68), fill=BRASS)
    draw.ellipse((center - 42, center - 42, center + 42, center + 42), fill=STEEL)
    draw.ellipse((center - 22, center - 22, center + 22, center + 22), fill=NAVY)
    image.save(path)
    return path
