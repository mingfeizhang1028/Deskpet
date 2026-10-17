# -*- coding: utf-8 -*-
"""水彩角色去背景：大阈值色度键粗抠 + 边缘泛洪连通域填洞。

原理:
  1. ffmpeg colorkey 用较大 similarity 把外围背景（含水彩晕染灰雾）
     狠抠干净，代价是角色内部白毛也会被抠穿成孔洞
  2. 在二值 alpha 上从画面边缘泛洪，只标记“与外部连通”的透明区
  3. 角色内部的透明孔洞不与外部连通，从原始帧取回 RGB 并填实，
     白毛完整保留
  4. alpha 边缘轻微高斯羽化；半透明带向内收，避免背景灰边

也支持纯泛洪模式（不给 --coarse 时直接在原图 RGB 上容差泛洪）。

用法（单帧或目录）:
  python matting_floodfill.py <raw.png 或 raw目录> --coarse <粗抠目录> ^
      --out <输出目录> [--blur 0.8] [--shrink 0.35] [--thresh 55]

仅依赖 Pillow。
"""
import os
import sys
import argparse
from PIL import Image, ImageDraw, ImageFilter, ImageChops

MARK = 128  # 泛洪标记值


def list_png(path):
    if os.path.isfile(path):
        return [path]
    return sorted(os.path.join(path, f) for f in os.listdir(path)
                  if f.lower().endswith(".png"))


def edge_seeds(w, h, step=60):
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    for x in range(step, w - 1, step):
        seeds += [(x, 0), (x, h - 1)]
    for y in range(step, h - 1, step):
        seeds += [(0, y), (w - 1, y)]
    return seeds


def matting_combo(raw_im, coarse_im, blur, shrink):
    """粗抠 alpha + 原图 RGB，外部透明 / 内部洞填实。"""
    raw = raw_im.convert("RGBA")
    w, h = raw.size
    alpha_coarse = coarse_im.convert("RGBA").getchannel("A")
    # 二值候选透明区: alpha < 128
    hole = alpha_coarse.point(lambda v: 0 if v < 128 else 255)
    flooded = hole.copy()
    for s in edge_seeds(w, h):
        if flooded.getpixel(s) == 0:
            ImageDraw.floodfill(flooded, s, MARK, thresh=0)
    # 外部(MARK)=透明; 内部洞(0)与本体(255)=不透明, RGB 一律取原图
    final_a = flooded.point(lambda v: 0 if v == MARK else 255)
    if blur > 0:
        final_a = final_a.filter(ImageFilter.GaussianBlur(blur))
        # 向内收: 把落在背景侧的半透明压掉, 灰边变透明
        cut = int(255 * shrink)
        final_a = final_a.point(lambda v: 0 if v < cut else
                                min(255, int((v - cut) / (255 - cut) * 255)))
    raw.putalpha(final_a)
    return raw


def dilate_outside(alpha, px):
    """把外部透明区向角色方向膨胀 px 像素，吃掉贴身水彩灰雾。"""
    if px <= 0:
        return alpha
    outside = ImageChops.invert(alpha)
    k = px * 2 + 1
    outside = outside.filter(ImageFilter.MaxFilter(k))
    return ImageChops.invert(outside)


def decontaminate(raw, hard, soft, band=5):
    """边缘颜色去污: 边缘半透明像素的 RGB 改为向内最近的本体毛发色，
    去掉原画轮廓外浅色水彩晕染在深色桌面上形成的白 halo。"""
    w, h = raw.size
    hp = hard.load()
    sp = soft.load()
    rp = raw.convert("RGB").load()
    out = raw.convert("RGB")
    op = out.load()
    near = hard.filter(ImageFilter.MaxFilter(band * 2 + 1)).load()
    for y in range(h):
        for x in range(w):
            if sp[x, y] >= 254 or near[x, y] == 0:
                continue
            best = None
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                step = 1
                while 0 <= nx < w and 0 <= ny < h and step <= band:
                    if hp[nx, ny] >= 250:
                        if best is None or step < best[0]:
                            best = (step, rp[nx, ny])
                        break
                    nx += dx
                    ny += dy
                    step += 1
            if best is not None:
                op[x, y] = best[1]
    out.putalpha(soft)
    return out


def open_enclosed_pockets(hard, grow=2):
    """碎发围成的背景小口袋不与画面边缘连通，羽化时会被填成暗斑。
    从边缘泛洪标记外部后，剩余的透明像素即封闭口袋，向外胀掉
    围成口袋的细发丝，让其与外部连通。"""
    if grow <= 0:
        return hard
    mark = hard.copy()
    w, h = mark.size
    for s in edge_seeds(w, h):
        if mark.getpixel(s) == 0:
            ImageDraw.floodfill(mark, s, MARK, thresh=0)
    pocket = mark.point(lambda v: 255 if v == 0 else 0)
    if pocket.getextrema() == (0, 0):
        return hard
    pocket = pocket.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    out = hard.copy()
    out.paste(0, mask=pocket)
    return out


def remove_small_components(hard, raw, min_area, light_cut=150):
    """删除不与角色主体相连的小型浅色不透明块（背景水彩泼溅、压缩噪点）。
    8 连通；主体通常 >30 万像素，泼溅 <1500，阈值间有 200 倍余量。
    只删平均亮度高于 light_cut 的浅色块，保留深色胡须等线条。"""
    w, h = hard.size
    px = hard.load()
    rgb = raw.convert("RGB").load()
    seen = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if seen[i] or px[x, y] < 128:
                continue
            stack = [i]
            seen[i] = 1
            members = []
            light_sum = 0
            while stack:
                j = stack.pop()
                members.append(j)
                cy, cx = divmod(j, w)
                r, g, b = rgb[cx, cy]
                light_sum += r + g + b
                for dy in (-1, 0, 1):
                    ny = cy + dy
                    if ny < 0 or ny >= h:
                        continue
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx = cx + dx
                        if nx < 0 or nx >= w:
                            continue
                        k = ny * w + nx
                        if not seen[k] and px[nx, ny] >= 128:
                            seen[k] = 1
                            stack.append(k)
            mean_light = light_sum / max(len(members) * 3, 1)
            if len(members) < min_area and mean_light > light_cut:
                for j in members:
                    cy, cx = divmod(j, w)
                    px[cx, cy] = 0
    return hard


def fill_enclosed_holes(hard):
    """把不与画面边缘连通的透明区（角色内部孔洞）填实为不透明。"""
    w, h = hard.size
    mark = hard.copy()
    for s in edge_seeds(w, h):
        if mark.getpixel(s) == 0:
            ImageDraw.floodfill(mark, s, MARK, thresh=0)
    return mark.point(lambda v: 255 if v == 0 else
                      (0 if v == MARK else v))


INV_TABLE = bytes(255 - i for i in range(256))


def _erode_column(col, k):
    """单列纵向 erode: k 窗口内全 255 才输出 255，滑动零计数线性扫描。"""
    h = len(col)
    r = k // 2
    out = bytearray(h)
    zeros = 0
    for i in range(min(r + 1, h)):
        if col[i] == 0:
            zeros += 1
    for y in range(h):
        out[y] = 255 if zeros == 0 else 0
        lo = y - r
        if lo >= 0 and col[lo] == 0:
            zeros -= 1
        hi = y + r + 1
        if hi < h and col[hi] == 0:
            zeros += 1
    return out


def vertical_open(alpha, k):
    """1×k 纵向开运算（erode→dilate），只保留纵向厚度 ≥ k 的结构
    （躯干/腿/脚掌），删除脚下横向扁平的薄带。"""
    w, h = alpha.size
    data = alpha.tobytes()
    er = bytearray(w * h)
    for x in range(w):
        er[x::w] = bytes(_erode_column(data[x::w], k))
    # dilate = 反相 → erode → 反相
    inv = Image.frombytes("L", (w, h), bytes(er)).point(INV_TABLE)
    idata = inv.tobytes()
    dl = bytearray(w * h)
    for x in range(w):
        dl[x::w] = bytes(_erode_column(idata[x::w], k))
    return Image.frombytes("L", (w, h), bytes(dl)).point(INV_TABLE)


def separate_contact_shadow(raw, hard, bg, k=13, dilate=2, diff_keep=34,
                            y_start=0.52):
    """分离原画脚下的水彩接触阴影（贴地横向扁平、背景色调灰带）。
      body  : hard 的纵向开运算 = 厚实本体（躯干/腿/脚掌/尾巴）
      cut   : hard 中 body 没有的薄结构
    双重保护: 色差 ≥ diff_keep 的深色像素（脚尖/墨线）与
      y_start 以上的区域一律不删，胡须与躯干毛不受影响。"""
    w, h = hard.size
    body = vertical_open(hard, k)
    if dilate > 0:
        body = body.filter(ImageFilter.MaxFilter(dilate * 2 + 1))
    dist = ImageChops.difference(raw.convert("RGB"),
                                 Image.new("RGB", (w, h), bg)).convert("L")
    protected = dist.point(lambda v: 255 if v >= diff_keep else 0)
    region = Image.new("L", (w, h), 0)
    region.paste(255, (0, int(h * y_start), w, h))
    cut = ImageChops.subtract(hard, body)
    cut = ImageChops.multiply(cut, region)
    cut = ImageChops.subtract(cut, protected)
    return ImageChops.subtract(hard, cut)


def sample_bg_from_alpha(rgba_im):
    """从已有 alpha 帧的透明像素 RGB 采中位数作为背景色（自包含，
    无需重抽视频）；无透明像素时返回 None。"""
    rgba = rgba_im.convert("RGBA")
    w, h = rgba.size
    hp = rgba.getchannel("A").load()
    rp = rgba.convert("RGB").load()
    trans = []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if hp[x, y] < 128:
                trans.append(rp[x, y])
    if not trans:
        return None
    trans.sort(key=sum)
    return trans[len(trans) // 2]


def version_b(im):
    """删除脚底固定带内的浅色接触阴影，保留角色本体。

    以本帧不透明像素的最低点为基准，只处理其上方 130px 横带内
    ``比采样背景暗至少 4、且 RGB 色差不超过 60`` 的像素。蒙版经
    GaussianBlur(1.2) 羽化后从原 alpha 减去，避免脚边出现硬切口。
    """
    rgba = im.convert("RGBA")
    w, h = rgba.size
    alpha = rgba.getchannel("A")
    hard = alpha.point(lambda v: 255 if v >= 128 else 0)
    bg = sample_bg_from_alpha(rgba)
    if bg is None:
        return rgba
    rgb = rgba.convert("RGB")
    dist = ImageChops.difference(
        rgb, Image.new("RGB", (w, h), bg)).convert("L")
    hp = hard.load()
    foot = h - 1
    while foot > 0 and not any(hp[x, foot] for x in range(0, w, 3)):
        foot -= 1
    bg_lum = int(0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2])
    darker = ImageChops.subtract(
        Image.new("L", (w, h), bg_lum).point(lambda v: max(0, v - 4)),
        rgb.convert("L"))
    darker = darker.point(lambda v: 255 if v > 0 else 0)
    rng = dist.point(lambda v: 255 if v <= 60 else 0)
    band = Image.new("L", (w, h), 0)
    band.paste(255, (0, foot - 130, w, h))
    cut = ImageChops.multiply(hard, darker)
    cut = ImageChops.multiply(cut, rng)
    cut = ImageChops.multiply(cut, band)
    cut = cut.filter(ImageFilter.GaussianBlur(1.2))
    rgba.putalpha(ImageChops.subtract(alpha, cut))
    return rgba


def subtract_contact_shadow(im, k=13, dilate=2, diff_keep=34, y_start=0.52):
    """对一张已抠好的帧只做"脚下接触阴影减法"，其余像素严格不动:
      hard  : 帧自身 alpha 二值化
      body  : 纵向开运算（厚实本体与腿间纵向灰雾都保留）
      cut   : 仅底部区域内、非深色保护的扁平薄带 = 接触阴影
    cut 做羽化后从原 alpha 减去，删除边缘不生硬。"""
    rgba = im.convert("RGBA")
    w, h = rgba.size
    alpha = rgba.getchannel("A")
    hard = alpha.point(lambda v: 255 if v >= 128 else 0)
    bg = sample_bg_from_alpha(rgba)
    if bg is None:
        return rgba
    body = vertical_open(hard, k)
    if dilate > 0:
        body = body.filter(ImageFilter.MaxFilter(dilate * 2 + 1))
    rgb = rgba.convert("RGB")
    dist = ImageChops.difference(rgb, Image.new("RGB", (w, h), bg)).convert("L")
    protected = dist.point(lambda v: 255 if v >= diff_keep else 0)
    region = Image.new("L", (w, h), 0)
    region.paste(255, (0, int(h * y_start), w, h))
    cut = ImageChops.subtract(hard, body)
    cut = ImageChops.multiply(cut, region)
    cut = ImageChops.subtract(cut, protected)
    cut_soft = cut.filter(ImageFilter.GaussianBlur(1.2))
    rgba.putalpha(ImageChops.subtract(alpha, cut_soft))
    return rgba


def matting_key(raw_im, bg, key_t=14, close_r=1, blur=1.2, shrink=0.55,
                decontam=6, min_comp=3000, shadow_k=13, shadow_dilate=2,
                shadow_keep=34, shadow_y=0.52):
    """亮度键主方案（无边缘泛洪路径，逐帧稳定不闪烁）:
    比背景暗（墨线/深色毛）或比背景亮（白毛）的都是角色，
    只有与背景色差小于 key_t 的像素透明；再封闭细缝、填回
    角色内部的浅灰毛孔洞。bg 为背景 RGB 三元组。
    shadow_k>0 时在最后分离脚下水彩接触阴影。"""
    raw = raw_im.convert("RGBA")
    bg_im = Image.new("RGB", raw.size, bg)
    dist = ImageChops.difference(raw.convert("RGB"), bg_im).convert("L")
    hard = dist.point(lambda v: 255 if v > key_t else 0)
    if close_r > 0:
        k = close_r * 2 + 1
        hard = hard.filter(ImageFilter.MaxFilter(k))
        hard = hard.filter(ImageFilter.MinFilter(k))
    hard = fill_enclosed_holes(hard)
    hard = remove_small_components(hard, raw, min_comp, 150)
    if shadow_k > 0:
        hard = separate_contact_shadow(raw, hard, bg, shadow_k,
                                       shadow_dilate, shadow_keep, shadow_y)
    alpha = hard
    if blur > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(blur))
        cut = int(255 * shrink)
        alpha = alpha.point(lambda v: 0 if v < cut else
                            min(255, int((v - cut) / (255 - cut) * 255)))
    if decontam > 0:
        return decontaminate(raw, hard, alpha, decontam)
    raw.putalpha(alpha)
    return raw


def matting_pure_flood(raw_im, thresh, blur, shrink, dilate=0,
                       decontam=5, pocket_grow=2, min_comp=3000):
    """无粗抠: 直接在 RGB 上容差泛洪（白毛靠内部连通性自保）。"""
    raw = raw_im.convert("RGBA")
    w, h = raw.size
    flooded = raw.copy()
    for s in edge_seeds(w, h):
        ImageDraw.floodfill(flooded, s, (0, 0, 0, 0), thresh=thresh)
    hard = flooded.getchannel("A")
    hard = open_enclosed_pockets(hard, pocket_grow)
    hard = remove_small_components(hard, raw, min_comp)
    hard = dilate_outside(hard, dilate)
    alpha = hard
    if blur > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(blur))
        cut = int(255 * shrink)
        alpha = alpha.point(lambda v: 0 if v < cut else
                            min(255, int((v - cut) / (255 - cut) * 255)))
    if decontam > 0:
        return decontaminate(raw, hard, alpha, decontam)
    raw.putalpha(alpha)
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--coarse", help="粗抠帧目录（组合模式）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["key", "flood", "shadowcut"],
                    default="key",
                    help="key=亮度键主方案(默认); flood=旧边缘泛洪方案; "
                         "shadowcut=对已抠帧仅减脚下接触阴影")
    ap.add_argument("--bg", default="218,215,210",
                    help="key 模式背景色 R,G,B")
    ap.add_argument("--key-t", type=int, default=14,
                    help="key 模式色差阈值")
    ap.add_argument("--close-r", type=int, default=2,
                    help="key 模式封闭细缝半径")
    ap.add_argument("--thresh", type=int, default=55,
                    help="flood 模式 RGB 容差")
    ap.add_argument("--dilate", type=int, default=0,
                    help="外部蒙版向角色膨胀像素数（去贴身灰雾）")
    ap.add_argument("--decontam", type=int, default=5,
                    help="边缘颜色去污带宽像素（去外发光白边，0=关闭）")
    ap.add_argument("--pocket-grow", type=int, default=2,
                    help="封闭背景口袋扩开像素（消除头顶碎发暗斑，0=关闭）")
    ap.add_argument("--min-comp", type=int, default=3000,
                    help="小于该面积的浅色孤立块按泼溅删除")
    ap.add_argument("--shadow-k", type=int, default=13,
                    help="接触阴影纵向开运算厚度，0=关闭")
    ap.add_argument("--shadow-dilate", type=int, default=2,
                    help="本体判定后膨胀像素数，保证脚掌完整")
    ap.add_argument("--shadow-keep", type=int, default=34,
                    help="色差≥该值的深色像素不参与阴影删除")
    ap.add_argument("--shadow-y", type=float, default=0.52,
                    help="仅在该高度比例以下执行阴影删除")
    ap.add_argument("--blur", type=float, default=0.8)
    ap.add_argument("--shrink", type=float, default=0.35,
                    help="羽化带内收比例 0-1")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    raw_files = list_png(args.raw)
    coarse_files = {}
    if args.coarse:
        for p in list_png(args.coarse):
            coarse_files[os.path.basename(p)] = p

    for rp in raw_files:
        name = os.path.basename(rp)
        raw_im = Image.open(rp)
        if args.mode == "shadowcut":
            out_im = subtract_contact_shadow(
                raw_im, args.shadow_k, args.shadow_dilate,
                args.shadow_keep, args.shadow_y)
        elif args.coarse:
            cp = coarse_files.get(name)
            if cp is None:
                print("跳过(无粗抠帧): %s" % name)
                continue
            out_im = matting_combo(raw_im, Image.open(cp),
                                   args.blur, args.shrink)
        else:
            if args.mode == "key":
                bg = tuple(int(x) for x in args.bg.split(","))
                out_im = matting_key(raw_im, bg, args.key_t, args.close_r,
                                     args.blur, args.shrink, args.decontam,
                                     args.min_comp, args.shadow_k,
                                     args.shadow_dilate, args.shadow_keep,
                                     args.shadow_y)
            else:
                out_im = matting_pure_flood(raw_im, args.thresh,
                                            args.blur, args.shrink,
                                            args.dilate, args.decontam,
                                            args.pocket_grow, args.min_comp)
        out_im.save(os.path.join(args.out, name))
        print(name)


if __name__ == "__main__":
    main()
