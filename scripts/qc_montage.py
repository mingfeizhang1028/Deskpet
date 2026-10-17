# -*- coding: utf-8 -*-
"""生成全视频黑底 QC 总表: 每个动画一行, 均匀抽 7 帧。"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ASSETS = r"P:\Deskpet\assets"
OUT = r"P:\Deskpet\tmp\probe\_qc_all.png"
ORDER = [
    "yayan-idle-loop", "yayan-sleep-loop", "yayan-breathing-loop",
    "yayan-blink", "yayan-look-up", "yayan-look-down",
    "yayan-look-left", "yayan-look-right",
    "yayan-curious-reaction", "yayan-happy-reaction",
    "yayan-shy-reaction", "yayan-gentle-concern",
    "yayan-stretch", "yayan-jump", "yayan-pickup",
    "yayan-turn-around", "yayan-turn-right-to-left",
    "yayan-walk-stop", "yayan-sit-down",
]


def main():
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 13)
    K = 7
    T, LW, PAD = 172, 132, 4
    sheet = Image.new("RGB",
                      (LW + K * T + PAD * 2,
                       PAD + (T + PAD) * len(ORDER)), (90, 90, 95))
    d = ImageDraw.Draw(sheet)
    for r, name in enumerate(ORDER):
        y = PAD + r * (T + PAD)
        d.text((5, y + T // 2 - 7), name.replace("yayan-", ""),
               fill=(255, 255, 255), font=font)
        dd = os.path.join(ASSETS, name)
        fs = sorted(f for f in os.listdir(dd)
                    if f.startswith("frame-") and f.endswith(".png"))
        if not fs:
            continue
        idxs = [round(i * (len(fs) - 1) / (K - 1)) for i in range(K)]
        for c, i in enumerate(idxs):
            im = Image.open(os.path.join(dd, fs[i])).convert("RGBA")
            im.thumbnail((T, T), Image.LANCZOS)
            cell = Image.new("RGB", (T, T), (15, 15, 18))
            cell.paste(im, ((T - im.width) // 2, (T - im.height) // 2), im)
            sheet.paste(cell, (LW + PAD + c * T, y))
    sheet.save(OUT)
    print(OUT, sheet.size)


if __name__ == "__main__":
    main()
