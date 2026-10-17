# -*- coding: utf-8 -*-
"""在已抠图的连续源帧中寻找最佳循环闭合点。

对参考帧（默认第 1 帧）与序列中每一帧计算姿势差异：
  - 角色区域 RGB 差（两帧 alpha 并集内统计，透明区不参与）
  - Alpha 差（轮廓/腿部位置变化）
  - 下半区（腿部）单独评分，行走类动画接缝跳步主要来自腿

输出差异分数表 + ASCII 曲线，并打印:
  1. 末尾 N 帧中最接近参考帧的候选闭合点
  2. 全序列最接近的 N 帧（用于发现更短/更优循环周期）

用法:
  python analyze_loop_seam.py <frames_dir> [--ref 1] [--tail 12] [--top 8]
"""
import os
import sys
import argparse
from PIL import Image

ANALYZE_W = 240


def load_small(path, w=ANALYZE_W):
    im = Image.open(path).convert("RGBA")
    scale = w / im.width
    im = im.resize((w, int(im.height * scale)), Image.LANCZOS)
    return im, im.size[1]


def frame_diff(ref, cur, h):
    """返回 (总分, rgb差, alpha差, 腿部alpha差)，0-255 量纲。"""
    rp = ref.load()
    cp = cur.load()
    w = ref.width
    leg_y = int(h * 0.55)
    n = nr = na = nleg = 0
    sr = sa = sleg = 0
    for y in range(h):
        for x in range(w):
            r = rp[x, y]
            c = cp[x, y]
            if r[3] <= 25 and c[3] <= 25:
                continue
            n += 1
            sr += abs(r[0] - c[0]) + abs(r[1] - c[1]) + abs(r[2] - c[2])
            nr += 3
            da = abs(r[3] - c[3])
            sa += da
            na += 1
            if y >= leg_y:
                sleg += da
                nleg += 1
    rgb_diff = sr / max(nr, 1)
    a_diff = sa / max(na, 1)
    leg_diff = sleg / max(nleg, 1)
    return rgb_diff + a_diff * 0.5, rgb_diff, a_diff, leg_diff


def ascii_curve(scores, width=72):
    if not scores:
        return ""
    lo, hi = min(scores), max(scores)
    rng = max(hi - lo, 1e-6)
    lines = []
    for i, s in enumerate(scores):
        bar = int((s - lo) / rng * (width - 1))
        mark = "#%d" % (i + 1)
        lines.append("%-5s |%s%s %.1f" % (mark, " " * bar, "*", s))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("--ref", type=int, default=1, help="参考帧序号(从1)")
    ap.add_argument("--tail", type=int, default=12, help="末尾候选帧数")
    ap.add_argument("--top", type=int, default=8, help="列出全序列最接近的N帧")
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(args.frames_dir)
                   if f.lower().endswith(".png") and not f.startswith("_"))
    if len(files) < 2:
        raise SystemExit("帧不足: %s" % args.frames_dir)

    ref_path = os.path.join(args.frames_dir, files[args.ref - 1])
    ref, h = load_small(ref_path)

    results = []
    for i, fname in enumerate(files):
        cur, _ = load_small(os.path.join(args.frames_dir, fname))
        score, rgb_d, a_d, leg_d = frame_diff(ref, cur, h)
        results.append((i + 1, score, rgb_d, a_d, leg_d))

    print("参考帧: #%d (%s)  分析尺寸: %dx%d" % (
        args.ref, files[args.ref - 1], ANALYZE_W, h))
    print("列名: score = rgb差 + 0.5*alpha差 (越低越接近)\n")

    print("== 末尾 %d 帧对参考帧的差异 ==" % args.tail)
    print("帧号   score   rgb差   alpha差  腿部alpha差")
    for n, s, r, a, leg in results[-args.tail:]:
        print("#%-4d %6.1f %6.1f %8.1f %10.1f" % (n, s, r, a, leg))

    tail_best = min(results[-args.tail:], key=lambda t: t[1])
    print("\n>> 末尾区间最佳闭合帧: #%d  score=%.1f (腿=%.1f)" % (
        tail_best[0], tail_best[1], tail_best[4]))

    ranked = sorted(results[1:], key=lambda t: t[1])[:args.top]
    print("\n== 全序列最接近参考帧的 %d 帧 ==" % args.top)
    for n, s, r, a, leg in ranked:
        print("#%-4d score=%6.1f  rgb=%5.1f alpha=%5.1f 腿=%5.1f" % (
            n, s, r, a, leg))

    scores = [t[1] for t in results]
    print("\n== 差异曲线（每10帧打印一个标记，*=帧位置） ==")
    step = max(1, len(scores) // 36)
    sampled = ["#%d:%.0f" % (i + 1, scores[i])
               for i in range(0, len(scores), step)]
    print("  ".join(sampled))


if __name__ == "__main__":
    main()
