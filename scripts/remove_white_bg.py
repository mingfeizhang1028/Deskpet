#!/usr/bin/env python3
"""把 AI 生成的白底动画帧抠成透明底（RGBA）并裁剪归一化。
  输入 = 备份的原图(tmp/anim_bg_originals)，输出 = godot/assets/anim。不修改备份。

流程（两遍）：
  1) 每帧：缩到 512 → 保守纯白抠除(只抠近纯白，保住奶油/白毛身) → 最大连通主体
     → 得到 512 RGBA + 不透明边界 bbox。
  2) 每个状态：取所有帧 bbox 的【并集】，把每帧裁剪到并集区域，
     → 缩放至放进 TARGET(300) 画布(保持比例) → 居中放在 300x300 透明画布。
  效果：同状态各帧画布统一、猫大小一致、去掉透明边距（猫占满画布），
        Godot 里按显示尺寸设置漫游边界后猫永远完整可见。
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

SRC_IN = Path(r"P:\Deskpet\tmp\anim_bg_originals")
SRC_OUT = Path(r"P:\Deskpet\godot\assets\anim")
PRE_SIZE = 512           # 中间处理尺寸
TARGET = 300             # 最终画布边长
BG_MIN = 247             # 背景最暗通道下限（保守：只抠近纯白）
SPREAD = 5               # 背景明度差上限
# 已知坏帧：背景被 AI 染成奶油色、与猫身无法分离，直接跳过（不动备份）。
SKIP = {"walk/walk-02.png", "walk/walk-06.png"}


def _is_bg(r: int, g: int, b: int) -> bool:
    m = min(r, g, b)
    if m < BG_MIN:
        return False
    return max(r, g, b) - m <= SPREAD


def _cutout(in_path: Path) -> tuple[Image.Image, tuple[int, int, int, int]]:
    src = Image.open(in_path).convert("RGB").resize((PRE_SIZE, PRE_SIZE), Image.LANCZOS)
    im = src.convert("RGBA")
    w = h = PRE_SIZE
    data = im.load()
    n = w * h

    state = bytearray(n)
    for i in range(n):
        px = data[i % w, i // w]
        if not _is_bg(px[0], px[1], px[2]):
            state[i] = 2

    # 从边缘漫延，标记连边的背景
    dq: deque = deque()
    for x in range(w):
        for y in (0, h - 1):
            i = y * w + x
            if state[i] == 0:
                state[i] = 1
                dq.append(i)
    for y in range(h):
        for x in (0, w - 1):
            i = y * w + x
            if state[i] == 0:
                state[i] = 1
                dq.append(i)
    while dq:
        i = dq.popleft()
        x, y = i % w, i // w
        for j in (i - 1 if x > 0 else -1,
                  i + 1 if x < w - 1 else -1,
                  i - w if y > 0 else -1,
                  i + w if y < h - 1 else -1):
            if j >= 0 and state[j] == 0:
                state[j] = 1
                dq.append(j)

    # 只保留最大连通主体
    visited = bytearray(n)
    dq2: deque = deque()
    best: list[int] = []
    best_size = 0
    for start in range(n):
        if state[start] == 1 or visited[start]:
            continue
        visited[start] = 1
        dq2.append(start)
        comp: list[int] = []
        while dq2:
            i = dq2.popleft()
            comp.append(i)
            x, y = i % w, i // w
            x0, x1 = max(0, x - 1), min(w - 1, x + 1)
            y0, y1 = max(0, y - 1), min(h - 1, y + 1)
            for ny in range(y0, y1 + 1):
                base = ny * w
                for nx in range(x0, x1 + 1):
                    j = base + nx
                    if state[j] != 1 and not visited[j]:
                        visited[j] = 1
                        dq2.append(j)
        if len(comp) > best_size:
            best_size = len(comp)
            best = comp

    alpha = bytearray(n)
    for i in best:
        alpha[i] = 255
    a_img = Image.new("L", (w, h))
    a_img.putdata(alpha)
    a_img = a_img.filter(ImageFilter.GaussianBlur(0.8))

    tmp = Image.new("RGBA", (w, h))
    tmp.paste(im.convert("RGB"), (0, 0))
    tmp.putalpha(a_img)

    # 不透明边界
    xs = [i % w for i in best]
    ys = [i // w for i in best]
    bbox = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    return tmp, bbox


def _normalize(frame: Image.Image, bbox: tuple[int, int, int, int]) -> Image.Image:
    x0, y0, x1, y1 = bbox
    bw, bh = x1 - x0, y1 - y0
    region = frame.crop((x0, y0, x1, y1))
    # 缩放到放进 TARGET，保持比例
    scale = min(TARGET / bw, TARGET / bh, 1.0)
    nw, nh = max(1, round(bw * scale)), max(1, round(bh * scale))
    region = region.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (TARGET, TARGET), (0, 0, 0, 0))
    canvas.alpha_composite(region, ((TARGET - nw) // 2, (TARGET - nh) // 2))
    return canvas


def main() -> None:
    files = [f for f in sorted(SRC_IN.rglob("*.png"))
             if f.relative_to(SRC_IN).as_posix() not in SKIP]
    if not files:
        print("no source under", SRC_IN)
        return

    # pass 1：每帧裁切 + bbox；按状态分组
    frames: dict[str, list[tuple[Path, str, Image.Image, tuple]]] = {}
    for f in files:
        rel = f.relative_to(SRC_IN)
        state = rel.parts[0]
        frame, bbox = _cutout(f)
        frames.setdefault(state, []).append((f, rel.as_posix(), frame, bbox))
        print("cut:", rel)

    # pass 2：每状态并集 bbox → 裁剪归一化 → 按连续编号保存
    for state, items in frames.items():
        items.sort(key=lambda it: it[1])
        u = (min(i[3][0] for i in items),
             min(i[3][1] for i in items),
             max(i[3][2] for i in items),
             max(i[3][3] for i in items))
        for idx, (_, _rel, frame, _bbox) in enumerate(items, start=1):
            out = _normalize(frame, u)
            rel = "%s/%s-%02d.png" % (state, state, idx)
            out_path = SRC_OUT / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out.save(out_path)
            print("norm:", rel, "->", out.size)
    print("done, %d states -> %s (%dpx)" % (len(frames), SRC_OUT, TARGET))


if __name__ == "__main__":
    main()