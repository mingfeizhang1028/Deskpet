import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
from skimage import measure, morphology


def ellipse_mask(height, width, center_x, center_y, radius_x, radius_y):
    y, x = np.ogrid[:height, :width]
    return ((x - center_x) / radius_x) ** 2 + ((y - center_y) / radius_y) ** 2 <= 1


def polygon_mask(height, width, points):
    from PIL import ImageDraw

    image = Image.new("1", (width, height), 0)
    ImageDraw.Draw(image).polygon(points, fill=1)
    return np.asarray(image, dtype=bool)


def keep_main_component(mask):
    labels = measure.label(mask, connectivity=2)
    regions = measure.regionprops(labels)
    if not regions:
        raise RuntimeError("No foreground component was detected")
    largest = max(regions, key=lambda region: region.area)
    return labels == largest.label


def build_mask(rgb):
    height, width = rgb.shape[:2]
    scale_x = width / 2048
    scale_y = height / 2048

    def sx(value):
        return int(round(value * scale_x))

    def sy(value):
        return int(round(value * scale_y))

    rough = np.zeros((height, width), dtype=bool)
    rough |= ellipse_mask(height, width, sx(950), sy(690), sx(525), sy(390))
    rough |= ellipse_mask(height, width, sx(980), sy(1250), sx(430), sy(610))
    rough |= ellipse_mask(height, width, sx(1390), sy(1515), sx(520), sy(330))
    rough |= polygon_mask(
        height,
        width,
        [(sx(475), sy(690)), (sx(500), sy(250)), (sx(800), sy(520))],
    )
    rough |= polygon_mask(
        height,
        width,
        [(sx(1060), sy(515)), (sx(1325), sy(230)), (sx(1390), sy(700))],
    )

    luminance = (
        rgb[..., 0].astype(np.float32) * 0.2126
        + rgb[..., 1].astype(np.float32) * 0.7152
        + rgb[..., 2].astype(np.float32) * 0.0722
    )
    ink = (luminance < 220) & rough
    ink = morphology.remove_small_objects(ink, min_size=max(8, sx(18)))
    connected = morphology.binary_dilation(ink, morphology.disk(max(2, sx(5))))
    connected = morphology.binary_closing(connected, morphology.disk(max(5, sx(18))))
    connected = keep_main_component(connected)
    silhouette = ndimage.binary_fill_holes(connected)
    silhouette = morphology.binary_erosion(silhouette, morphology.disk(max(2, sx(4))))

    # Preserve fine ink strokes such as whiskers when they touch the main silhouette.
    nearby = morphology.binary_dilation(silhouette, morphology.disk(max(8, sx(44))))
    fine_ink = (luminance < 188) & nearby
    silhouette |= morphology.binary_dilation(fine_ink, morphology.disk(max(1, sx(1))))
    silhouette = morphology.remove_small_holes(silhouette, area_threshold=max(64, sx(600)))
    return silhouette


def prepare(source, destination):
    image = Image.open(source).convert("RGB")
    rgb = np.asarray(image)
    mask = build_mask(rgb)

    y, x = np.nonzero(mask)
    padding = max(24, round(max(image.size) * 0.018))
    left = max(0, int(x.min()) - padding)
    top = max(0, int(y.min()) - padding)
    right = min(image.width, int(x.max()) + padding + 1)
    bottom = min(image.height, int(y.max()) + padding + 1)

    cropped = image.crop((left, top, right, bottom)).convert("RGBA")
    alpha = Image.fromarray((mask[top:bottom, left:right] * 255).astype(np.uint8), "L")
    alpha = alpha.filter(ImageFilter.GaussianBlur(radius=1.2))
    cropped.putalpha(alpha)

    destination.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(destination, optimize=True)
    return cropped.size, alpha.getbbox()


def main():
    parser = argparse.ArgumentParser(description="Extract the approved watercolor pet from its baked checkerboard.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    size, content_bbox = prepare(args.source, args.destination)
    print(f"saved={args.destination} size={size} content_bbox={content_bbox}")


if __name__ == "__main__":
    main()
