# 芽砚 · 水彩纸片猫 动画帧提示词包

把"静态蹲着的水彩猫"变成会呼吸、会走、会脸红、会困的**几帧动画**。
你来生图（用任何文生图模型），我这边已经做好 Godot 播放器，你按下面的命名把图丢进指定目录，猫就会动。

---

## 一、你要做的三件事（看完这一节就懂全流程）

1. 每张图都用下面的固定语法拼提示词，**只替换"动作短语"**：
   > `角色主锚点 + 动作短语 + 全局取景`
2. 生成**纯白背景、全身居中、四分之三侧面偏左**的方图，每张都单独存为 PNG。
3. 按 `状态-编号.png` 命名，放进对应子目录：`godot/assets/anim/<状态>/`，例如 `godot/assets/anim/idle/idle-01.png`。

> 如果生出来的图是白底，不用手动抠：运行 `scripts/remove_white_bg.py` 会自动把与边缘相连的白底抠成透明（保留毛内的白胸口/爪尖），并先备份原图到 `tmp/anim_bg_originals/`。放好图后运行一次它，再重启 Godot 就能看到动画。

---

## 二、【必须前置】三个固定块，直接复制

### 2.1 角色主锚点（每个提示词的前缀，一字不改）
> INDIGO AND CREAM FLAT WATERCOLOR FOX-CAT DESKTOP PET, cream-orange gradient fur, white chest and paw tips, big soft eyes, fluffy large tail, round chubby chibi proportions, soft natural watercolor texture, flat paper silhouette style

中文释义：扁平水彩纸片风格的狐狸+猫桌宠，奶油橙渐变毛、白胸白爪尖、大而温柔的眼睛、蓬松大尾巴、圆滚滚的 Q 版比例、柔和的水彩质感、扁平纸片剪影风。

### 2.2 全局取景（每个提示词的后缀，一字不改）
> full body, single centered subject, isolated on a plain pure white background, soft even studio lighting, consistent three-quarter view facing slightly left, consistent size and framing, 1:1 square canvas, high detail

中文释义：全身、单一居中主体、纯白背景、柔和均匀光、统一四分之三侧面微偏左、尺寸取景一致、1:1 方图、高细节。

### 2.3 负面提示（Negative Prompt）
> complex background, scenery, other animals, multiple subjects, extra limbs, malformed paws, deformed, watermark, text, signature, frame, border, ground shadow, drop shadow

中文释义：复杂背景、风景、别的动物、多个主体、多出来的肢体、畸形爪子、变形、水印、文字、签名、边框、地面阴影、投影。

---

## 三、每张图的拼贴公式

把它们一条条复制，例如 idle 第一帧：

    <角色主锚点>, sitting calmly upright, still, neutral resting expression, <全局取景>

即：**每个提示词 = 主锚点 + 逗号 + 该帧动作短语 + 逗号 + 全局取景。**
负面提示始终粘贴在负面输入框。

---

## 四、动画状态与帧清单（共约 26 帧）

> 每帧后面"动作短语"就是你要替换进公式里的那一段。

### idle 呼吸（5 帧）→ 目录 `godot/assets/anim/idle/`
| 文件 | 动作短语 |
|---|---|
| `idle-01.png` | sitting calmly upright, still, neutral resting expression |
| `idle-02.png` | sitting calmly, inhaling softly, belly gently beginning to swell |
| `idle-03.png` | sitting calmly, deep breath in, belly and chest fully puffed round |
| `idle-04.png` | sitting calmly, exhaling, body gently relaxing and deflating slightly |
| `idle-05.png` | sitting calmly upright again, settled, neutral resting expression |

### walk 走路（8 帧，侧向向左走，身体前倾）→ `godot/assets/anim/walk/`
| 文件 | 动作短语 |
|---|---|
| `walk-01.png` | side walking gait, moving left, left forepaw lifted forward, right hindpaw pushed back, body leaning slightly forward |
| `walk-02.png` | side walking gait, moving left, forepaws and hindpaws passing each other, body at mid stride |
| `walk-03.png` | side walking gait, moving left, right forepaw forward, left hindpaw forward, body leaning forward |
| `walk-04.png` | side walking gait, moving left, paws gathered under the body, returning to neutral |
| `walk-05.png` | side walking gait, moving left, left forepaw forward again, starting a new stride |
| `walk-06.png` | side walking gait, moving left, legs swinging past, body centered |
| `walk-07.png` | side walking gait, moving left, right forepaw forward, weight shifting forward |
| `walk-08.png` | side walking gait, moving left, paws together, about to begin the next loop |

> **【走路请分两次生成，保证帧间一致】**
> - 💡 建议每次只出一批，**同批用固定 seed** 一口气生成，跨批尽量保持相同 seed/参数。
> - 🅰️ **第一批**：`walk-01` ~ `walk-04`（起始→跨步→落步→回中，先出这半圈）
> - 🅱️ **第二批**：`walk-05` ~ `walk-08`（第二半圈）
> - 各批完整可复制的提示词直接看下方"两批分步提示词"。
> - 小技巧：走路最容易"帧间不一致"，宁可每批风格优先统一；接受轻微漂移，4 帧循环其实已够用，多的帧是备选。

### sleep 睡觉（3 帧）→ `godot/assets/anim/sleep/`
| 文件 | 动作短语 |
|---|---|
| `sleep-01.png` | lying down curled up, eyes closed, peaceful, body softly resting on the ground |
| `sleep-02.png` | lying down curled, sleeping, breathing out, body gently flattened lower |
| `sleep-03.png` | lying down curled, sleeping, gentle inhale, body softly rising up |

### happy 开心（4 帧）→ `godot/assets/anim/happy/`
| 文件 | 动作短语 |
|---|---|
| `happy-01.png` | excited, ears perked up, sitting eagerly |
| `happy-02.png` | happy hop, front paws lifted, tail raised, bouncing up |
| `happy-03.png` | joyful peak of a little jump, ears up, tail up, mid-air |
| `happy-04.png` | coming back down to a sit, cheerful bright mood |

### shy 害羞（3 帧）→ `godot/assets/anim/shy/`
| 文件 | 动作短语 |
|---|---|
| `shy-01.png` | shy, gentle pink blush on the cheeks, head tilting slightly to the side |
| `shy-02.png` | shy, blush deepening pinker, looking down bashfully |
| `shy-03.png` | timid, head lowered, cheeks flushed pink, shy reserved posture |

### curious 好奇（3 帧）→ `godot/assets/anim/curious/`
| 文件 | 动作短语 |
|---|---|
| `curious-01.png` | curious, leaning slightly forward, ears alert |
| `curious-02.png` | curious, leaning forward more, watching intently |
| `curious-03.png` | curious, leaning back a little, head tilted, thoughtful |

---

## 五、状态与角色的对应关系

| Godot 状态 | 播放动画 |
|---|---|
| 空闲 idle / 坐下 | idle |
| 漫游 roam（满桌走） | walk |
| 困 sleepy | sleep |
| 开心 happy | happy |
| 害羞 shy / 关心 concerned | shy |
| 好奇 curious / 思考 thinking | curious |
| 定格 quiet/fixed、被拖拽 dragging | 停在当前帧不动 |

---

## 六、命名与放置规范（Godot 播放器就按这个读）

- 文件：小写状态名 + 短横线 + 两位编号，**必须从 01 连续递增**（缺一帧就停在对齐处）。
- 路径：`godot/assets/anim/<状态>/<状态>-NN.png`
  - 例：`godot/assets/anim/idle/idle-01.png`
- 背景：纯白（播放器自动把近白抠成透明）。若某些图已经自带透明背景（PNG alpha）则更佳。
- 尺寸：建议 512–1024 方图即可，不要超大（会拖慢窗口）。

> 没放任何帧图时，Godot 会自动退回"当前这张静态水彩猫"，窗口、聊天、四个面板都不受影响——所以你可以放心先补帧、后看效果。