# -*- coding: utf-8 -*-
"""帧内窄入口检测: 当前硬蒙版 vs r=4 封闭填洞蒙版之差。
真漏洞(白毛决堤形成的窄入口)在此现出大面积; 腿间大间隙不受影响。"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

ASSETS = r"P:\Deskpet\assets"
SCALE = 0.5
FLAG = 2500  # 缩小坐标下的像素数


def close_fill(hard, r):
    k = r * 2 + 1
    c = hard.filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.MinFilter(k))
    w, h = c.size
    mark = c.copy()
    for x in range(0, w, 40):
        for y in (0, h - 1):
            if mark.getpixel((x, y)) == 0:
                ImageDraw.floodfill(mark, (x, y), 128, thresh=0)
    for y in range(0, h, 40):
        for x in (0, w - 1):
            if mark.getpixel((x, y)) == 0:
                ImageDraw.floodfill(mark, (x, y), 128, thresh=0)
    return mark.point(lambda v: 255 if v == 0 else (0 if v == 128 else v))


def main():
    r = int(sys.argv[1]) if sys.argv and sys.argv[1].isdigit() else 4
    names = [a for a in sys.argv[1:] if not a.isdigit()] or os.listdir(ASSETS)
    hot = []
    for name in names:
        d = os.path.join(ASSETS, name)
        fs = sorted(f for f in os.listdir(d)
                    if f.startswith("frame-") and f.endswith(".png"))
        for i, f in enumerate(fs, 1):
            a = Image.open(os.path.join(d, f)).split()[3]
            w, h = a.size
            a = a.resize((int(w * SCALE), int(h * SCALE)))
            hard = a.point(lambda v: 255 if v > 200 else 0)
            sealed = close_fill(hard, r)
            hp = hard.load()
            sp = sealed.load()
            miss = 0
            for y in range(sealed.size[1]):
                for x in range(sealed.size[0]):
                    if sp[x, y] > 0 and hp[x, y] == 0:
                        miss += 1
            if miss > FLAG:
                hot.append((name, i, miss))
                print("!! %-25s #%02d 窄入口缺失 %d px" % (name, i, miss))
    if not hot:
        print("全部通过, 无窄入口漏洞")


if __name__ == "__main__":
    main()
