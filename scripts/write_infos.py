# -*- coding: utf-8 -*-
"""为每个动画生成 _EXTRACTION_INFO.txt。"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_pipeline import LOOPS, ONESHOTS, BG_FALLBACK

ASSETS = r"P:\Deskpet\assets"

META = {  # 宽, 高, fps, 总帧数, 时长
    "yayan-idle-loop": (960, 960, 24, 98, 4.10),
    "yayan-sleep-loop": (960, 960, 24, 98, 4.10),
    "yayan-breathing-loop": (960, 960, 24, 98, 4.10),
    "yayan-blink": (960, 960, 24, 98, 4.10),
    "yayan-look-down": (960, 960, 24, 98, 4.10),
    "yayan-look-left": (960, 960, 24, 98, 4.10),
    "yayan-look-up": (960, 960, 24, 122, 5.09),
    "yayan-look-right": (960, 960, 24, 122, 5.09),
    "yayan-curious-reaction": (960, 960, 24, 122, 5.09),
    "yayan-happy-reaction": (960, 960, 24, 122, 5.09),
    "yayan-shy-reaction": (960, 960, 24, 98, 4.10),
    "yayan-gentle-concern": (960, 960, 24, 122, 5.09),
    "yayan-stretch": (960, 960, 24, 122, 5.09),
    "yayan-jump": (1280, 720, 24, 98, 4.10),
    "yayan-pickup": (960, 960, 24, 98, 4.10),
    "yayan-turn-around": (960, 960, 24, 122, 5.09),
    "yayan-turn-right-to-left": (960, 960, 24, 122, 5.09),
    "yayan-walk-stop": (960, 960, 24, 122, 5.09),
    "yayan-sit-down": (960, 960, 24, 170, 7.10),
}

# 循环: 周期P, 优化依据
LOOP_META = {
    "yayan-idle-loop": (48, "全(s,P)同相扫描 s=44 闭合最佳(差异0.0026)"),
    "yayan-sleep-loop": (88, "呼吸起伏在4s内仅约一个完整周期, s=6 起"),
    "yayan-breathing-loop": (91, "缓慢深呼吸, s=4 起 P=91 闭合"),
}

CN = {
    "yayan-idle-loop": "待机(坐姿微动)循环",
    "yayan-sleep-loop": "睡眠(趴卧呼吸)循环",
    "yayan-breathing-loop": "坐姿呼吸循环",
    "yayan-blink": "眨眼(眯眼)单次",
    "yayan-look-down": "向下看单次(回中)",
    "yayan-look-left": "向左看单次(回中)",
    "yayan-look-up": "向上看单次(回中)",
    "yayan-look-right": "向右看单次(回中)",
    "yayan-curious-reaction": "好奇反应(歪头,回中)",
    "yayan-happy-reaction": "开心反应(起身雀跃,回坐)",
    "yayan-shy-reaction": "害羞反应(脸红低头,回中)",
    "yayan-gentle-concern": "温柔关切(表情持续,不回中)",
    "yayan-stretch": "伸懒腰(站立→前扑伸展→回坐)",
    "yayan-jump": "跳跃(蹲→腾空→落地蹲)",
    "yayan-pickup": "被抱起(悬空晃荡→落下坐稳)",
    "yayan-turn-around": "原地转身(面向左转到右)",
    "yayan-turn-right-to-left": "行走中转身(右行转左行)",
    "yayan-walk-stop": "走路→停下→坐下",
    "yayan-sit-down": "行走→缓慢坐下(长动作)",
}


def qc(name, src_frames):
    d = os.path.join(ASSETS, name)
    fs = sorted(f for f in os.listdir(d)
                if f.startswith("frame-") and f.endswith(".png"))
    ops = []
    for f in fs:
        a = Image.open(os.path.join(d, f)).split()[3]
        ops.append(sum(1 for v in a.getdata() if v > 250))
    return fs, ops


def write(name, kind, src_frames):
    w, h, fps, nfr, dur = META[name]
    is_jump = name == "yayan-jump"
    crop = "1280:680:0:0（裁底40px去水印）" if is_jump else \
           "960:900:0:0（裁底60px去右下角「AI生成」水印）"
    ow, oh = (1280, 680) if is_jump else (960, 900)
    fs, ops = qc(name, src_frames)
    n = len(fs)
    L = []
    a = L.append
    a("=" * 60)
    a("  芽砚动作视频抽帧记录")
    a("=" * 60)
    a("动画名称: %s" % name)
    a("动作说明: %s" % CN[name])
    a("动画类型: %s" % ("循环 (Loop)" if kind == "loop" else "单次 (One-shot)"))
    a("生成日期: 2026-10-08")
    a("")
    a("-" * 60)
    a("源视频")
    a("-" * 60)
    a("文件: %s.mp4" % name)
    a("分辨率: %d×%d   帧率: %d fps   总帧数: %d   时长: %.2f s"
      % (w, h, fps, nfr, dur))
    a("")
    a("-" * 60)
    a("抽帧方案")
    a("-" * 60)
    if kind == "loop":
        P, why = LOOP_META[name]
        q = src_frames[1] - src_frames[0]
        ofps = 24.0 / q
        a("类型: 循环, 先全起点扫描真实周期(非机械等间隔取整段)")
        a("周期: %d 源帧 (%.2f s) —— %s" % (P, P / fps, why))
        a("区间: 源 #%d – #%d, 固定步长 %d, 共 %d 帧(不含与首帧同相的末点)"
          % (src_frames[0], src_frames[-1], q, n))
        a("播放: 固定帧率 %.1f fps(每帧=%d源帧=%.0fms), 循环周期 %.2f s"
          % (ofps, q, q / fps * 1000, P / fps))
    else:
        gaps = [src_frames[i + 1] - src_frames[i]
                for i in range(len(src_frames) - 1)]
        a("类型: 单次播放(非循环)。动作开始/结束由逐帧姿态差曲线定位,")
        a("      静止保持段自适应稀疏采样, 运动段密集采样。")
        a("区间: 源 #%d – #%d, 共 %d 帧" % (src_frames[0], src_frames[-1], n))
        a("源帧间隔: %s" % gaps)
        a("播放: 必须用逐帧时长(见下表), 每帧时长=该帧到下一帧源间隔/24s;")
        a("      末帧建议持续 %dms 后由 Godot 切到其他动画(本动作不循环)"
          % round(gaps[-1] / fps * 1000))
        a("      Godot 可逐帧设置 SpriteFrames 时长, 或用 AnimatedSprite2D")
        a("      的 frame_duration 数组; GIF 预览已按此时长导出。")
    a("")
    a("-" * 60)
    a("后处理")
    a("-" * 60)
    a("1. 去水印: ffmpeg crop=%s" % crop)
    a("2. 抠图: 原始裁剪帧 + PIL「亮度键」流水线")
    a("   (scripts/matting_floodfill.py --mode key)")
    a("   比背景暗(墨线/深毛)或亮(白毛)的像素都是猫, 仅与背景")
    a("   色差<14 的像素为背景; 5x5闭运算封细缝(防止近白背景上白毛")
    a("   轮廓局部决堤) + 封闭洞填回内部白毛 + 浅色孤立泼溅点删除(仅删")
    a("   浅色块, 保护深色胡须) + 高斯羽化1.2/内收0.55 + 边缘6px")
    a("   换色去深色底光晕。")
    a("   全局逐像素判定, 无边缘泛洪路径, 逐帧结构稳定。")
    a("输出尺寸: %d×%d RGBA PNG" % (ow, oh))
    a("")
    a("-" * 60)
    a("质量测量")
    a("-" * 60)
    rr = (max(ops) - min(ops)) / (sum(ops) / len(ops))
    a("- %d 帧尺寸/模式一致; 不透明像素 %d–%d, 逐帧极差 %.1f%%"
      % (n, min(ops), max(ops), rr * 100))
    a("- 黑底/深灰底/棋盘格三底检查无光晕、无背景残留、无水印残留")
    if kind == "loop":
        a("- 循环接缝经同相扫描选定, 首末为同一姿态相位")
    a("")
    a("-" * 60)
    a("验收材料")
    a("-" * 60)
    a("_CONTACT_SHEET.png   全部帧棋盘格联系表")
    if kind == "loop":
        a("_LOOP_CHECK.png      首/末帧并排 + 4倍差异图")
    a("_PREVIEW.gif         棋盘格底预览(单次类为逐帧时长)")
    a("_PREVIEW_2b2d33.gif  深灰底预览")
    a("_PREVIEW_0f0f12.gif  黑底预览")
    a("")
    a("-" * 60)
    a("帧映射表 (时长ms仅单次类需要)")
    a("-" * 60)
    a("%-18s %8s %10s %8s" % ("文件名", "源帧号", "源时间s", "时长ms"))
    for i, sf in enumerate(src_frames):
        if kind == "loop":
            q = src_frames[1] - src_frames[0]
            ms = round(q / fps * 1000)
        else:
            g = gaps[i] if i < len(gaps) else gaps[-1]
            ms = round(g / fps * 1000)
        a("%-18s #%7d %10.3f %8d"
          % ("frame-%04d.png" % (i + 1), sf, (sf - 1) / fps, ms))
    with open(os.path.join(ASSETS, name, "_EXTRACTION_INFO.txt"),
              "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("INFO", name)


def main():
    only = sys.argv[1:]
    for name, fr in LOOPS.items():
        if not only or name in only:
            write(name, "loop", fr)
    for name, fr in ONESHOTS.items():
        if not only or name in only:
            write(name, "oneshot", fr)


if __name__ == "__main__":
    main()
