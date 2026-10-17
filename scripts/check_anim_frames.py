"""Read-only validation for 300x300 transparent animation frame directories."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def inspect_frame(path: Path) -> dict:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        bbox = alpha.getbbox()
        return {
            "size": rgba.size,
            "mode": image.mode,
            "alpha_bbox": bbox,
            "baseline": bbox[3] if bbox else None,
            "corner_alpha": alpha.getpixel((0, 0)),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    failed = False
    for state_dir in sorted(p for p in args.root.iterdir() if p.is_dir()):
        for path in sorted(state_dir.glob("*.png")):
            info = inspect_frame(path)
            valid = (
                info["size"] == (300, 300)
                and info["mode"] == "RGBA"
                and info["corner_alpha"] == 0
                and info["alpha_bbox"] is not None
            )
            if not valid:
                failed = True
            print(f"{path}: {info} valid={valid}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
