# -*- coding: utf-8 -*-
"""19 视频批量流水线: 选定源帧 -> 全分辨率裁剪抽帧 -> 亮度键抠图 -> assets。
选帧表 SELECTIONS 为 1 基源帧号(ffmpeg 内部转 0 基)。"""
import os
import subprocess
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matting_floodfill import matting_key

FF = (r"c:\Users\Rosem\.trae-cn\work\6ac5fbbfca151cf90629b14c"
      r"\ffmpeg-full\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")
ASSETS = r"P:\Deskpet\assets"
TMP = r"P:\Deskpet\tmp\full"


def rng(a, b, q):
    return list(range(a, b + 1, q))


# 循环类: walk v3 优化法结果
LOOPS = {
    "yayan-idle-loop": rng(44, 91, 3),          # 16, P=48
    "yayan-sleep-loop": rng(6, 86, 8),          # 11, P=88
    "yayan-breathing-loop": rng(4, 94, 6),      # 16, P=91
}

# 单次类: 自适应采样结果
ONESHOTS = {
    "yayan-blink": [1, 3, 11, 19, 27, 35, 43, 51, 59, 67, 75, 83, 91, 97],
    "yayan-look-down": [1, 9, 17, 19, 21, 23, 25, 27, 29, 31, 34, 38, 46,
                        54, 62, 68, 71, 74, 76, 78, 80, 82, 84, 88, 93],
    "yayan-look-left": [1, 9, 17, 22, 26, 31, 39, 47, 55, 63, 68, 72, 75,
                        78, 84, 92],
    "yayan-look-up": [1, 9, 17, 25, 33, 39, 44, 50, 58, 66, 74, 82, 90, 95,
                      98, 101, 105, 113, 121],
    "yayan-look-right": [1, 9, 17, 25, 33, 39, 47, 55, 63, 71, 79, 87, 94,
                         102, 110, 117],
    "yayan-curious-reaction": [1, 9, 17, 22, 29, 34, 37, 41, 47, 55, 61, 69,
                               77, 85, 90, 93, 97, 99, 101, 103, 106, 110, 116],
    "yayan-happy-reaction": [1, 9, 17, 25, 33, 39, 45, 47, 51, 54, 56, 58,
                             60, 62, 65, 69, 71, 75, 81, 83, 86, 88, 90, 92,
                             94, 96, 99, 105, 111, 119, 121],
    "yayan-shy-reaction": [1, 9, 17, 25, 31, 35, 39, 45, 53, 61, 67, 71, 75,
                           79, 83, 91, 95],
    "yayan-gentle-concern": [1, 5, 10, 17, 20, 25, 34, 43, 52, 58, 62, 71, 75,
                             79, 86, 95, 104, 113, 121],
    "yayan-stretch": [1, 10, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35,
                      37, 39, 41, 43, 45, 47, 49, 51, 54, 56, 59, 63, 71, 80,
                      84, 87, 89, 91, 93, 95, 97, 99, 101, 103, 105, 107, 109,
                      111, 113],
    "yayan-jump": [1, 8, 15, 22, 27, 34, 37, 39, 41, 43, 45, 47, 49, 51, 55,
                   57, 59, 61, 63, 65, 67, 69, 71, 75, 79, 83, 89, 97],
    "yayan-pickup": [1, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 35,
                     37, 39, 41, 43, 46, 49, 51, 54, 57, 60, 63, 65, 67, 69,
                     71, 73, 75, 77, 79, 82, 84, 86, 88, 90, 93, 97],
    "yayan-turn-around": [1, 9, 17, 25, 33, 39, 43, 47, 51, 55, 58, 61, 63,
                          66, 68, 70, 73, 75, 79, 82, 85, 87, 91, 95, 99,
                          103, 111, 119, 121],
    "yayan-turn-right-to-left": [1, 9, 17, 23, 27, 30, 32, 34, 37, 39, 43, 46,
                                 49, 51, 54, 56, 58, 62, 65, 68, 71, 77, 82,
                                 87, 92, 95, 101, 107, 115, 121],
    "yayan-walk-stop": [1, 7, 11, 15, 18, 21, 24, 28, 31, 34, 38, 42, 46, 49,
                        51, 54, 56, 59, 62, 64, 66, 68, 71, 74, 77, 79, 82,
                        86, 90, 98, 106, 114, 121],
    "yayan-sit-down": [1, 10, 18, 23, 31, 35, 39, 43, 51, 57, 62, 67, 71, 75,
                       79, 85, 87, 91, 95, 99, 105, 110, 119, 128, 137, 146,
                       155, 164, 169],
}

# 背景色由脚本从多帧角部自动估计; 兜底值(探测中位数)
BG_FALLBACK = {
    "yayan-sleep-loop": (203, 203, 203),
    "yayan-curious-reaction": (224, 224, 224),
    "yayan-happy-reaction": (217, 217, 217),
    "yayan-idle-loop": (239, 240, 243),
    "yayan-walk-stop": (236, 230, 221),
}

CROP = {True: "crop=1280:680:0:0", False: "crop=960:900:0:0"}


def estimate_bg(paths):
    pts = []
    for p in paths[::max(1, len(paths) // 4)]:
        im = Image.open(p).convert("RGB")
        w, h = im.size
        for cx, cy in [(0, 0), (w - 26, 0), (0, h - 26), (w - 26, h - 26)]:
            pts.extend(list(im.crop((cx, cy, cx + 26, cy + 26)).getdata()))
    pts.sort(key=sum)
    return pts[len(pts) // 2]


def run(name, frames):
    src = os.path.join(ASSETS, name + ".mp4")
    od = os.path.join(TMP, name)
    os.makedirs(od, exist_ok=True)
    for f in os.listdir(od):
        os.remove(os.path.join(od, f))
    sel = "+".join("eq(n\\,%d)" % (f - 1) for f in frames)
    p = subprocess.run(
        [FF, "-i", src, "-vf", "select='%s',%s" % (sel, CROP[name == "yayan-jump"]),
         "-vsync", "0", "-y", os.path.join(od, "f_%03d.png")],
        capture_output=True, text=True, errors="replace")
    got = sorted(f for f in os.listdir(od) if f.endswith(".png"))
    if len(got) != len(frames):
        print("!! %s 抽帧数不符: 期望%d 得到%d" % (name, len(frames), len(got)))
        print(p.stderr[-500:])
        return False
    paths = [os.path.join(od, f) for f in got]
    bg = estimate_bg(paths)
    if name in BG_FALLBACK:
        # 灰底/暖底视频信任探测兜底, 仅在偏差过大时报警
        fb = BG_FALLBACK[name]
        if sum(abs(a - b) for a, b in zip(bg, fb)) > 12:
            print("?? %s 自动背景%s 与兜底%s 偏差大, 用自动值" % (name, bg, fb))
    outd = os.path.join(ASSETS, name)
    os.makedirs(outd, exist_ok=True)
    for i, p in enumerate(paths, 1):
        raw = Image.open(p)
        out = matting_key(raw, bg, 14, 2, 1.2, 0.55, 6, 3000)
        out.save(os.path.join(outd, "frame-%04d.png" % i))
    print("OK %-25s %2d帧 bg=%s" % (name, len(paths), bg))
    return True


def main():
    only = sys.argv[1:]
    jobs = [(n, LOOPS[n]) for n in sorted(LOOPS)] + \
           [(n, ONESHOTS[n]) for n in sorted(ONESHOTS)]
    for name, frames in jobs:
        if only and name not in only:
            continue
        run(name, frames)


if __name__ == "__main__":
    main()
