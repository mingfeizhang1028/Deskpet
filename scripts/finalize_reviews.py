# -*- coding: utf-8 -*-
"""批量收尾: 黑底目检联系表 + 逐帧时长GIF(单次类) + QC统计。
循环GIF用固定帧率; 单次类每帧时长=源帧间隔/24秒。"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_pipeline import LOOPS, ONESHOTS

ASSETS = r"P:\Deskpet\assets"
FONT = r"C:\Windows\Fonts\msyh.ttc"


def list_frames(d):
    return sorted(f for f in os.listdir(d)
                  if f.startswith("frame-") and f.endswith(".png"))


def checker(size, cs=16):
    img = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(img)
    for r in range(size[1] // cs + 1):
        for c in range(size[0] // cs + 1):
            if (r + c) % 2:
                d.rectangle([c * cs, r * cs, c * cs + cs - 1, r * cs + cs - 1],
                            fill=(205, 205, 205))
    return img


def make_gif(name, bgc, tag, durations, width=384):
    d = os.path.join(ASSETS, name)
    fs = list_frames(d)
    frames = []
    for f in fs:
        im = Image.open(os.path.join(d, f)).convert("RGBA")
        r = width / im.width
        im = im.resize((width, int(im.height * r)), Image.LANCZOS)
        if bgc == "CHK":
            bg = checker(im.size)
        else:
            bg = Image.new("RGB", im.size, bgc)
        bg.paste(im, (0, 0), im)
        frames.append(bg.convert("P", palette=Image.ADAPTIVE))
    out = "_PREVIEW.gif" if tag == "chk" else "_PREVIEW_%s.gif" % tag
    frames[0].save(os.path.join(d, out), save_all=True,
                   append_images=frames[1:], duration=durations[:len(fs)],
                   loop=0, disposal=1, optimize=True)


def qc_stats(name):
    d = os.path.join(ASSETS, name)
    fs = list_frames(d)
    ops = []
    for f in fs:
        a = Image.open(os.path.join(d, f)).split()[3]
        ops.append(sum(1 for v in a.getdata() if v > 250))
    rng = (max(ops) - min(ops)) / (sum(ops) / len(ops))
    return len(fs), min(ops), max(ops), rng


def main():
    report = {}
    jobs = {n: ("loop", LOOPS[n]) for n in LOOPS}
    jobs.update({n: ("oneshot", fr) for n, fr in ONESHOTS.items()})
    only = sys.argv[1:]
    for name, (kind, src) in jobs.items():
        if only and name not in only:
            continue
        nf, mn, mx, rr = qc_stats(name)
        report[name] = [nf, mn, mx, round(rr * 100, 1)]
        gaps = [src[i + 1] - src[i] for i in range(len(src) - 1)]
        if kind == "loop":
            q = gaps[0]
            fps = 24.0 / q
            durs = [int(round(1000 / fps))] * nf
        else:
            durs = [int(round(g * 1000 / 24)) for g in gaps]
            durs.append(durs[-1])  # 末帧展示约一个常规间隔
        make_gif(name, "CHK", "chk", durs)
        make_gif(name, (43, 45, 51), "2b2d33", durs)
        make_gif(name, (15, 15, 18), "0f0f12", durs)
        print("GIF %-25s %d帧 %s" % (name, nf,
              "固定%dms" % durs[0] if kind == "loop" else "逐帧时长"))
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
