# -*- coding: utf-8 -*-
"""选帧规划器:
  loop    —— walk v3 法: 全(s,P)扫描同相帧对 + 步长q接缝均匀性优化
  oneshot —— 自适应采样: 运动量累积驱动, max_gap 压缩静止保持段
输入 tmp/small/<name>/f_###.png (1基帧号)。
用法:
  python plan_selections.py loop <name> [pmin] [pmax]
  python plan_selections.py oneshot <name> <a> <b> <m_thresh> <max_gap> [min_gap]
"""
import os
import sys
from statistics import median

from PIL import Image, ImageChops, ImageFilter

SMALL = r"P:\Deskpet\tmp\small"


def frames(name):
    d = os.path.join(SMALL, name)
    fs = sorted(f for f in os.listdir(d) if f.endswith(".png"))
    return [Image.open(os.path.join(d, f)).convert("L").resize((140, 131))
            .filter(ImageFilter.GaussianBlur(2.5)) for f in fs]


def D(a, b):
    h = ImageChops.difference(a, b).histogram()
    return sum(i * c for i, c in enumerate(h)) / sum(h) / 255


def plan_loop(name, pmin=30, pmax=96):
    ims = frames(name)
    N = len(ims)
    cands = []
    for s in range(0, N - pmin):
        for P in range(pmin, min(pmax, N - 1 - s) + 1):
            cands.append((D(ims[s], ims[s + P]), s, P))
    cands.sort()
    print("== 最佳同相帧对 (score, start1基, period) ==")
    seen = set()
    shown = 0
    for sp, s, P in cands:
        key = (s // 4, P // 4)
        if key in seen:
            continue
        seen.add(key)
        # 对该(s,P)枚举步长
        for q in (2, 3, 4, 6, 8):
            sel = list(range(s, s + P, q))
            Nf = len(sel)
            if not (8 <= Nf <= 24):
                continue
            steps = [D(ims[sel[i]], ims[sel[i + 1]])
                     for i in range(Nf - 1)]
            seam = D(ims[sel[-1]], ims[sel[0]])
            med = median(steps)
            ratio = seam / med if med > 1e-6 else 99
            if shown < 14 and 0.4 < ratio < 2.2:
                print("s=%3d P=%2d q=%d n=%2d same=%.4f seam=%.4f med=%.4f ratio=%.2f"
                      % (s + 1, P, q, Nf, sp, seam, med, ratio))
        shown += 1
        if shown >= 14:
            break


def plan_oneshot(name, a, b, mth, maxgap, mingap=2):
    ims = frames(name)
    a -= 1
    b -= 1  # 转0基且含端点
    keep = [a]
    for i in range(a + 1, b + 1):
        gap = i - keep[-1]
        moved = D(ims[keep[-1]], ims[i]) >= mth
        if i == b:
            # 尾帧强制: 与上一取帧几乎同姿则替换而非追加
            if gap < mingap and D(ims[keep[-1]], ims[i]) < mth * 0.5:
                keep[-1] = i
            else:
                keep.append(i)
        elif (moved and gap >= mingap) or gap >= maxgap:
            keep.append(i)
    sel = [k + 1 for k in keep]
    print("%s: %d 帧" % (name, len(sel)))
    print(sel)
    gaps = [sel[i + 1] - sel[i] for i in range(len(sel) - 1)]
    print("源帧间隔:", gaps)


if __name__ == "__main__":
    mode = sys.argv[1]
    name = sys.argv[2]
    if mode == "loop":
        pmin = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        pmax = int(sys.argv[4]) if len(sys.argv) > 4 else 96
        plan_loop(name, pmin, pmax)
    else:
        plan_oneshot(name, int(sys.argv[3]), int(sys.argv[4]),
                     float(sys.argv[5]), int(sys.argv[6]),
                     int(sys.argv[7]) if len(sys.argv) > 7 else 2)
