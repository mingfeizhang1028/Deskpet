"""Convert one generated sprite into a checked 300x300 RGBA candidate."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter


def is_background(pixel: tuple[int, int, int]) -> bool:
    return min(pixel) >= 247 and max(pixel) - min(pixel) <= 5


def remove_edge_background(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    background = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        for y in (0, height - 1):
            if is_background(pixels[x, y]) and not background[y * width + x]:
                background[y * width + x] = 1
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if is_background(pixels[x, y]) and not background[y * width + x]:
                background[y * width + x] = 1
                queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                index = ny * width + nx
                if not background[index] and is_background(pixels[nx, ny]):
                    background[index] = 1
                    queue.append((nx, ny))

    alpha = Image.new("L", (width, height), 255)
    alpha.putdata([0 if value else 255 for value in background])
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))
    rgba = rgb.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def normalize(source: Path, destination: Path) -> dict:
    image = Image.open(source).convert("RGBA")
    alpha = image.getchannel("A")
    if alpha.getpixel((0, 0)) != 0:
        image = remove_edge_background(image)
        alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("no foreground after background removal")
    region = image.crop(bbox)
    width, height = region.size
    scale = min(240 / width, 270 / height)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    region = region.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    canvas.alpha_composite(region, ((300 - size[0]) // 2, 282 - size[1]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)
    return {"source": image.size, "source_bbox": bbox, "output": canvas.size,
            "output_bbox": canvas.getchannel("A").getbbox()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(normalize(args.source, args.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
