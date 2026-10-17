# -*- coding: utf-8 -*-
"""从抽帧配置生成 Godot 用动画清单 godot/assets/anim_manifest.json。
重抽帧后重跑本脚本即可同步。

清单中的 balance 字段为跨动作颜色统一用的每通道增益(以 idle 白毛色为基准)，
由 Godot 端 pet_sprite.gd 的轻量 shader 在绘制时相乘，原始 PNG 不做任何改色。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_pipeline import LOOPS, ONESHOTS

OUT = r"P:\Deskpet\godot\assets\anim_manifest.json"
FPS_SRC = 24.0

# 白毛采样参数(与 tmp/measure_colors.py 一致)：不透明、高亮、低饱和像素。
BALANCE_SAMPLE_N = 5
BALANCE_THUMB = 200
BALANCE_ALPHA = 200
BALANCE_LUM = 165
BALANCE_SAT = 38
BALANCE_REF_FOLDER = "yayan-idle-loop"
BALANCE_MIN_GAIN = 0.90
BALANCE_MAX_GAIN = 1.12

# Godot 动画名 -> (文件夹, 类型, 循环固定fps或None)
MAP = [
    ("idle", "yayan-idle-loop", "loop", 8.0),
    ("walk", "yayan-walk-left-cycle", "loop", 12.0),
    ("sleep", "yayan-sleep-loop", "loop", 3.0),
    ("breathing", "yayan-breathing-loop", "loop", 4.0),
    ("blink", "yayan-blink", "oneshot", None),
    ("look_down", "yayan-look-down", "oneshot", None),
    ("look_left", "yayan-look-left", "oneshot", None),
    ("look_right", "yayan-look-right", "oneshot", None),
    ("look_up", "yayan-look-up", "oneshot", None),
    ("curious", "yayan-curious-reaction", "oneshot", None),
    ("happy", "yayan-happy-reaction", "oneshot", None),
    ("shy", "yayan-shy-reaction", "oneshot", None),
    ("gentle_concern", "yayan-gentle-concern", "oneshot", None),
    ("stretch", "yayan-stretch", "oneshot", None),
    ("jump", "yayan-jump", "oneshot", None),
    ("pickup", "yayan-pickup", "oneshot", None),
    ("turn_around", "yayan-turn-around", "oneshot", None),
    ("turn_right_to_left", "yayan-turn-right-to-left", "oneshot", None),
    ("walk_stop", "yayan-walk-stop", "oneshot", None),
    ("sit_down", "yayan-sit-down", "oneshot", None),
]


def measure_fur_mean(paths):
    """采样若干帧，返回白毛像素(不透明/高亮/低饱和)的 (R,G,B) 均值。
    不同视频生成时灯光/色偏不同，白毛色是最稳定的跨动作校色参照。"""
    from PIL import Image
    if not paths:
        return None
    idxs = sorted(set(round(i * (len(paths) - 1) / (BALANCE_SAMPLE_N - 1))
                      for i in range(BALANCE_SAMPLE_N)))
    total = [0, 0, 0]
    count = 0
    for idx in idxs:
        im = Image.open(paths[idx]).convert("RGBA")
        im.thumbnail((BALANCE_THUMB, BALANCE_THUMB))
        px = im.load()
        w, h = im.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a < BALANCE_ALPHA:
                    continue
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                if lum > BALANCE_LUM and max(r, g, b) - min(r, g, b) < BALANCE_SAT:
                    total[0] += r
                    total[1] += g
                    total[2] += b
                    count += 1
    if count == 0:
        return None
    return (total[0] / count, total[1] / count, total[2] / count)


def main():
    import glob
    from PIL import Image
    anims = {}
    fur_means = {}
    for godot_name, folder, kind, fps in MAP:
        frame_dir = os.path.join(r"P:\Deskpet\assets", folder)
        paths = sorted(glob.glob(os.path.join(frame_dir, "frame-*.png")))
        n_frames = len(paths)
        # 全动画 alpha 包络并集: 保证跳跃/悬空等位移帧按同一比例与基准对齐
        x0, y0, x1, y1 = 10**9, 10**9, -1, -1
        for p in paths:
            a = Image.open(p).split()[3].point(lambda v: 255 if v > 40 else 0)
            bb = a.getbbox()
            if bb:
                x0 = min(x0, bb[0]); y0 = min(y0, bb[1])
                x1 = max(x1, bb[2]); y1 = max(y1, bb[3])
        entry = {
            "dir": folder,
            "frame_count": n_frames,
            "loop": kind == "loop",
            "union": [x0, y0, x1 - x0, y1 - y0],
        }
        if kind == "loop":
            entry["fps"] = fps
        else:
            src = ONESHOTS[folder]
            gaps = [src[i + 1] - src[i] for i in range(len(src) - 1)]
            # 每帧持续到下一帧; 末帧沿用最后一个间隔
            durs = [g / FPS_SRC for g in gaps] + [gaps[-1] / FPS_SRC]
            entry["durations"] = [round(d, 4) for d in durs]
        fur_means[folder] = measure_fur_mean(paths)
        anims[godot_name] = entry
    # 以 idle 白毛色为基准计算每通道增益；只做乘法校色，clamp 防止极端值。
    ref = fur_means.get(BALANCE_REF_FOLDER)
    if ref is None:
        print("warn: 缺少基准 %s 白毛统计，跳过 balance" % BALANCE_REF_FOLDER)
    else:
        for godot_name, folder, _kind, _fps in MAP:
            mean = fur_means.get(folder)
            if mean is None:
                continue
            gains = [min(BALANCE_MAX_GAIN, max(BALANCE_MIN_GAIN, ref[c] / mean[c]))
                     for c in range(3)]
            anims[godot_name]["balance"] = [round(g, 4) for g in gains]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"anims": anims}, f, ensure_ascii=False, indent=2)
    print("wrote", OUT, len(anims), "anims")


if __name__ == "__main__":
    main()
