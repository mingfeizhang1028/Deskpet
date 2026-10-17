"""Precompute the same sprite calibration used by Godot's PetSprite."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


CANVAS_SIZE = 300
TARGET_CONTENT_HEIGHT = 240
TARGET_CONTENT_WIDTH = 270
BASELINE_Y = 282


def calibrate(source: Path, destination: Path) -> dict:
    image = Image.open(source).convert("RGBA")
    alpha = image.getchannel("A")
    used = alpha.getbbox()
    if used is None:
        raise ValueError(f"empty alpha: {source}")
    region = image.crop(used)
    width, height = region.size
    scale = min(TARGET_CONTENT_HEIGHT / height, TARGET_CONTENT_WIDTH / width)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    region = region.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(region, ((CANVAS_SIZE - size[0]) // 2, BASELINE_Y - size[1]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)
    return {"source_bbox": used, "output_bbox": canvas.getchannel("A").getbbox()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path)
    parser.add_argument("destination_root", type=Path)
    args = parser.parse_args()
    for state_dir in sorted(p for p in args.source_root.iterdir() if p.is_dir()):
        for source in sorted(state_dir.glob("*.png")):
            destination = args.destination_root / state_dir.name / source.name
            print(source, "->", destination, calibrate(source, destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
