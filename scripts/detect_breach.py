# -*- coding: utf-8 -*-
"""决堤检测: 时间核心蒙版 = >=ratio 帧不透明的像素;
逐帧统计核心区中缺失(透明)像素占比, 超阈值标记。
循环类姿态稳定应接近0; 单次类中段大姿态变化可能误报需目检。"""
import os
import sys

from PIL import Image

ASSETS = r"P:\Deskpet\assets"
NAMES = sys.argv[1:] or [
    "yayan-idle-loop", "yayan-sleep-loop", "yayan-breathing-loop",
    "yayan-walk-left-cycle",
]
RATIO = 0.6
FLAG = 0.025
S = (320, 300)


def main():
    for name in NAMES:
        d = os.path.join(ASSETS, name)
        fs = sorted(f for f in os.listdir(d)
                    if f.startswith("frame-") and f.endswith(".png"))
        masks = []
        for f in fs:
            a = Image.open(os.path.join(d, f)).split()[3].resize(S)
            masks.append([1 if v > 128 else 0 for v in a.getdata()])
        n = len(masks)
        core_n = max(1, int(n * RATIO))
        npix = S[0] * S[1]
        core = [0] * npix
        for m in masks:
            for i, v in enumerate(m):
                core[i] += v
        core = [1 if c >= core_n else 0 for c in core]
        core_area = sum(core)
        flags = []
        for i, m in enumerate(masks):
            miss = sum(1 for j in range(npix) if core[j] and not m[j])
            r = miss / core_area
            if r > FLAG:
                flags.append((i + 1, round(r * 100, 1)))
        print("%-25s 核心区%d 缺失帧: %s"
              % (name, core_area, flags if flags else "无"))


if __name__ == "__main__":
    main()
