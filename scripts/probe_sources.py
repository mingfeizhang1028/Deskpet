# -*- coding: utf-8 -*-
"""批量探测源视频：元数据 + 背景色 + 底部水印条高度。
抽取每个视频首/中/尾三帧到 tmp/probe/<name>/ 供目检。"""
import os
import re
import subprocess
import sys

from PIL import Image

FF = (r"c:\Users\Rosem\.trae-cn\work\6ac5fbbfca151cf90629b14c"
      r"\ffmpeg-full\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")
ASSETS = r"P:\Deskpet\assets"
PROBE = r"P:\Deskpet\tmp\probe"


def probe_meta(path):
    p = subprocess.run([FF, "-i", path, "-hide_banner"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    txt = p.stderr
    dur = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", txt)
    dur_s = (int(dur.group(1)) * 3600 + int(dur.group(2)) * 60
             + float(dur.group(3))) if dur else 0
    m = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5}).*?([\d.]+)\s*fps", txt)
    w, h, fps = int(m.group(1)), int(m.group(2)), float(m.group(3))
    nframes = re.search(r"(\d+)\s+frames", txt)
    return w, h, fps, dur_s, (int(nframes.group(1)) if nframes else None)


def grab_frame(path, ts, out):
    subprocess.run([FF, "-ss", str(ts), "-i", path, "-frames:v", "1",
                    "-y", out], capture_output=True)


def bg_corner(im):
    """取四角 30x30 区域的中位色。"""
    w, h = im.size
    pts = []
    for box in [(0, 0), (w - 30, 0), (0, h - 30), (w - 30, h - 30)]:
        c = im.crop((box[0], box[1], box[0] + 30, box[1] + 30))
        pts.extend(list(c.getdata())[::13])
    pts.sort(key=lambda p: sum(p))
    return pts[len(pts) // 2]


def detect_bottom_band(im, bg, tol=28):
    """从底边向上扫描：连续'非背景'行数即为底部水印/黑边高度。"""
    w, h = im.size
    px = im.load()
    band = 0
    for y in range(h - 1, -1, -1):
        diff_rows = 0
        for x in range(0, w, 24):
            p = px[x, y]
            if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > tol:
                diff_rows += 1
        if diff_rows > w / 24 * 0.5:
            band += 1
        else:
            break
    return band


def main():
    names = sorted(f[:-4] for f in os.listdir(ASSETS)
                   if f.startswith("yayan-") and f.endswith(".mp4"))
    print("%-24s %9s %5s %5s %7s %6s | %s" %
          ("name", "size", "fps", "frms", "dur_s", "band", "bg_rgb"))
    for name in names:
        path = os.path.join(ASSETS, name + ".mp4")
        w, h, fps, dur, nf = probe_meta(path)
        nf = nf if nf else round(dur * fps)
        od = os.path.join(PROBE, name)
        os.makedirs(od, exist_ok=True)
        for tag, ts in [("a", 0.05), ("m", dur * 0.5), ("z", dur - 0.05)]:
            grab_frame(path, ts, os.path.join(od, tag + ".png"))
        im0 = Image.open(os.path.join(od, "a.png")).convert("RGB")
        bg = bg_corner(im0)
        band = detect_bottom_band(im0, bg)
        print("%-24s %5dx%-4d %5.1f %5d %7.2f %6d | %s" %
              (name, w, h, fps, nf, dur, band, bg))


if __name__ == "__main__":
    main()
