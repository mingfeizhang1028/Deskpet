# -*- coding: utf-8 -*-
"""批量抽取缩小全帧（已裁底），用于周期分析与选帧目检。"""
import os
import subprocess
import sys

FF = (r"c:\Users\Rosem\.trae-cn\work\6ac5fbbfca151cf90629b14c"
      r"\ffmpeg-full\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe")
ASSETS = r"P:\Deskpet\assets"
OUT = r"P:\Deskpet\tmp\small"

# 裁底量: 960x960 统一 60，jump(1280x720) 40
CROP = {True: "crop=1280:680:0:0,scale=480:-1",
        False: "crop=960:900:0:0,scale=360:-1"}


def main():
    only = sys.argv[1:]
    names = sorted(f[:-4] for f in os.listdir(ASSETS)
                   if f.startswith("yayan-") and f.endswith(".mp4"))
    for name in names:
        if only and name not in only:
            continue
        src = os.path.join(ASSETS, name + ".mp4")
        with Image_size(src) as (w, h):
            vf = CROP[w == 1280]
        od = os.path.join(OUT, name)
        os.makedirs(od, exist_ok=True)
        if os.listdir(od):
            print("skip", name)
            continue
        p = subprocess.run([FF, "-i", src, "-vf", vf, "-y",
                            os.path.join(od, "f_%03d.png")],
                           capture_output=True, text=True, errors="replace")
        n = len(os.listdir(od))
        print(name, n, "frames", "ERR" if p.returncode else "ok")


class Image_size:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        p = subprocess.run([FF, "-i", self.path, "-hide_banner"],
                           capture_output=True, text=True, errors="replace")
        import re
        m = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", p.stderr)
        self.v = (int(m.group(1)), int(m.group(2)))
        return self.v

    def __exit__(self, *a):
        pass


if __name__ == "__main__":
    main()
