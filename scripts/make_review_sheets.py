# -*- coding: utf-8 -*-
"""为透明 PNG 帧序列生成验收图。

输出文件到帧目录:
  _CONTACT_SHEET.png  棋盘格底的全部帧缩略图联系表
  _LOOP_CHECK.png     首帧/末帧并排 + 差异放大图（用于判断循环接缝）
  _PREVIEW.gif        棋盘格底循环播放预览（判断动态流畅度）

用法:
  python make_review_sheets.py <frames_dir> [--cols 8] [--thumb 240] [--loop] [--gif] [--fps 8]

仅依赖 Pillow（项目 venv 已安装）。
"""
import os
import sys
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageChops

CHECK_SIZE = 20
CHECK_LIGHT = (255, 255, 255)
CHECK_DARK = (204, 204, 204)
LABEL_H = 22
MARGIN = 16
GAP = 8
TITLE_H = 36


def load_font(size):
    for path in (r"C:\Windows\Fonts\msyh.ttc",
                 r"C:\Windows\Fonts\simhei.ttf",
                 r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def make_checker(w, h):
    """生成 w x h 的棋盘格背景。"""
    img = Image.new("RGB", (w, h), CHECK_LIGHT)
    draw = ImageDraw.Draw(img)
    cols = w // CHECK_SIZE + 1
    rows = h // CHECK_SIZE + 1
    for r in range(rows):
        for c in range(cols):
            if (r + c) % 2 == 1:
                x0 = c * CHECK_SIZE
                y0 = r * CHECK_SIZE
                draw.rectangle([x0, y0, x0 + CHECK_SIZE - 1, y0 + CHECK_SIZE - 1],
                               fill=CHECK_DARK)
    return img


def composite_on_checker(frame):
    """把 RGBA 帧合成到棋盘格上，返回 RGB。"""
    checker = make_checker(frame.width, frame.height)
    checker.paste(frame, (0, 0), frame)
    return checker


def list_frames(frames_dir):
    files = sorted(f for f in os.listdir(frames_dir)
                   if f.lower().endswith(".png")
                   and not f.startswith("_")
                   and f.startswith("frame-"))
    if not files:
        raise SystemExit("目录中没有 frame-XXXX.png: %s" % frames_dir)
    return files


def build_contact_sheet(frames_dir, files, cols, thumb_w, out_path):
    name = os.path.basename(os.path.normpath(frames_dir))
    first = Image.open(os.path.join(frames_dir, files[0]))
    scale = thumb_w / first.width
    thumb_h = int(first.height * scale)

    rows = (len(files) + cols - 1) // cols
    cell_w = thumb_w
    cell_h = thumb_h + LABEL_H
    sheet_w = MARGIN * 2 + cols * cell_w + (cols - 1) * GAP
    sheet_h = TITLE_H + MARGIN + rows * cell_h + (rows - 1) * GAP + MARGIN

    sheet = make_checker(sheet_w, sheet_h)
    draw = ImageDraw.Draw(sheet)
    font_title = load_font(20)
    font_label = load_font(13)

    title = "%s   %d frames   %dx%d RGBA" % (
        name, len(files), first.width, first.height)
    draw.text((MARGIN, 8), title, fill=(40, 40, 40), font=font_title)

    top0 = TITLE_H + MARGIN
    for i, fname in enumerate(files):
        r, c = divmod(i, cols)
        x = MARGIN + c * (cell_w + GAP)
        y = top0 + r * (cell_h + GAP)
        frame = Image.open(os.path.join(frames_dir, fname)).convert("RGBA")
        thumb = frame.resize((cell_w, thumb_h), Image.LANCZOS)
        sheet.paste(thumb, (x, y), thumb)
        draw.rectangle([x, y, x + cell_w - 1, y + thumb_h - 1],
                       outline=(150, 150, 150))
        draw.text((x + 3, y + thumb_h + 3), "#%d" % (i + 1),
                  fill=(30, 30, 30), font=font_label)

    sheet.save(out_path)
    return out_path


def build_loop_check(frames_dir, files, out_path):
    first = Image.open(os.path.join(frames_dir, files[0])).convert("RGBA")
    last = Image.open(os.path.join(frames_dir, files[-1])).convert("RGBA")

    scale = 384 / first.width
    tw, th = 384, int(first.height * scale)

    panels = []
    labels = []
    for frame, label in ((first, "#1  loop start"),
                         (last, "#%d  loop end" % len(files))):
        panel = make_checker(tw, th)
        thumb = frame.resize((tw, th), Image.LANCZOS)
        panel.paste(thumb, (0, 0), thumb)
        panels.append(panel)
        labels.append(label)

    # 差异图：两帧分别合成到棋盘后做差，放大 4 倍让微小位移可见
    c1 = composite_on_checker(first)
    c2 = composite_on_checker(last)
    if c2.size != c1.size:
        c2 = c2.resize(c1.size, Image.LANCZOS)
    diff = ImageChops.difference(c1, c2)
    diff = diff.point(lambda v: min(255, v * 4))
    diff = diff.resize((tw, th), Image.LANCZOS)
    panels.append(diff)
    labels.append("difference x4  (越暗=接缝越近)")

    label_h = 24
    sheet_w = MARGIN + len(panels) * tw + (len(panels) - 1) * GAP + MARGIN
    sheet_h = TITLE_H + MARGIN + th + label_h + MARGIN
    sheet = make_checker(sheet_w, sheet_h)
    draw = ImageDraw.Draw(sheet)
    font_title = load_font(20)
    font_label = load_font(14)
    draw.text((MARGIN, 8), "loop seam check", fill=(40, 40, 40),
              font=font_title)

    y = TITLE_H + MARGIN
    for i, (panel, label) in enumerate(zip(panels, labels)):
        x = MARGIN + i * (tw + GAP)
        sheet.paste(panel, (x, y))
        draw.rectangle([x, y, x + tw - 1, y + th - 1],
                       outline=(150, 150, 150))
        draw.text((x + 3, y + th + 4), label, fill=(30, 30, 30),
                  font=font_label)

    sheet.save(out_path)
    return out_path


def build_gif(frames_dir, files, fps, width, out_path, bg_kind="checker"):
    duration = int(round(1000 / fps))
    frames = []
    for fname in files:
        frame = Image.open(os.path.join(frames_dir, fname)).convert("RGBA")
        scale = width / frame.width
        frame = frame.resize((width, int(frame.height * scale)), Image.LANCZOS)
        if bg_kind == "checker":
            bg = make_checker(frame.width, frame.height)
        else:
            rgb = tuple(int(bg_kind[i:i + 2], 16) for i in (1, 3, 5))
            bg = Image.new("RGB", frame.size, rgb)
        bg.paste(frame, (0, 0), frame)
        frames.append(bg.convert("P", palette=Image.ADAPTIVE, colors=255))
    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=duration, loop=0, optimize=True, disposal=1)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("--cols", type=int, default=8)
    ap.add_argument("--thumb", type=int, default=240)
    ap.add_argument("--loop", action="store_true",
                    help="额外生成首末帧循环接缝对比图")
    ap.add_argument("--gif", action="store_true",
                    help="额外生成循环播放 GIF 预览")
    ap.add_argument("--fps", type=int, default=8,
                    help="GIF 预览帧率（默认 8，保持抽帧后原速）")
    ap.add_argument("--gif-width", type=int, default=384)
    ap.add_argument("--gif-bg", default="checker",
                    help="GIF 背景: checker 或 #RRGGBB（如 #2b2d33 深色桌面）")
    args = ap.parse_args()

    files = list_frames(args.frames_dir)
    contact = os.path.join(args.frames_dir, "_CONTACT_SHEET.png")
    build_contact_sheet(args.frames_dir, files, args.cols, args.thumb, contact)
    print(contact)

    if args.loop:
        loop = os.path.join(args.frames_dir, "_LOOP_CHECK.png")
        build_loop_check(args.frames_dir, files, loop)
        print(loop)

    if args.gif:
        if args.gif_bg == "checker":
            preview = os.path.join(args.frames_dir, "_PREVIEW.gif")
            build_gif(args.frames_dir, files, args.fps, args.gif_width,
                      preview, "checker")
            print(preview)
        else:
            tag = args.gif_bg.replace("#", "")
            preview = os.path.join(args.frames_dir,
                                   "_PREVIEW_%s.gif" % tag)
            build_gif(args.frames_dir, files, args.fps, args.gif_width,
                      preview, args.gif_bg)
            print(preview)


if __name__ == "__main__":
    main()
