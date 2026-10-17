extends AnimatedSprite2D
## 水彩纸片猫动画播放器（2026-10 芽砚抽帧版）。
##
## 帧素材: res://assets/yayan-<动作>/frame-0001.png …（junction 到 P:\Deskpet\assets）。
## 动画清单: res://assets/anim_manifest.json（由 scripts/gen_godot_manifest.py 生成），
## 声明每个动画的目录、帧数、循环与否、循环帧率或单次逐帧时长、统一包络框。
##
## 循环动画(idle/walk/sleep/breathing)无缝循环；反应类为单次动画，
## 每个情绪状态只演一次，播完自动回 idle 循环；情绪变化后才允许再演。
##
## 跨动作观感统一：
## - 颜色: manifest 中每个动画带 balance 三通道增益(以 idle 白毛色为基准)，
##   用一个只做 COLOR.rgb *= gain 的轻量 shader 在绘制时校正，PNG 资产不改色。
## - 切换: 换动画时用共享同一份 SpriteFrames 的幽灵精灵做 ~0.12s 交叉淡入淡出，
##   替代硬切，避免姿态/大小/颜色突变。
##
## 降级：一帧都加载不到时退回静态水彩立绘；窗口、bridge、聊天不受影响。

const MANIFEST_PATH := "res://assets/anim_manifest.json"
## 无帧时的兜底立绘。
const FALLBACK_TEXTURE := "res://assets/yayan-watercolor-base.png"
const CANVAS_SIZE := 300
const TARGET_CONTENT_HEIGHT := 240.0
const TARGET_CONTENT_WIDTH := 270.0
const BASELINE_Y := 282
## 切换时长(秒)：新动画柔和淡入、旧动画略快淡出。
## 坐姿↔走路↔躺卧轮廓差异大，淡出比淡入稍快以避免中段长时间"两只猫"叠影；
## 时长取 ~0.2s 量级 + 两端缓入缓出，观感为柔和的姿态过渡而非闪切。
const FADE_IN_TIME := 0.18
const FADE_OUT_TIME := 0.13

const BALANCE_SHADER_CODE := """
shader_type canvas_item;
uniform vec3 gain = vec3(1.0, 1.0, 1.0);
void fragment() {
	// COLOR 默认已是 纹理色 * 顶点色；只乘每通道增益，alpha/modulate 保持原样。
	COLOR.rgb *= gain;
}
"""

var _manifest: Dictionary = {}
## 单次(非循环)动画名集合。
var _oneshot_names: Dictionary = {}
var _current_anim := ""
var _any_frame_loaded := false
## 当前状态键（mood|activity），用于保证单次反应只演一次。
var _state_key := ""
var _oneshot_done: Dictionary = {}
## 各动画的三通道校色增益。
var _balance: Dictionary = {}
## 交叉淡入淡出时定格旧动画的幽灵精灵(共享 sprite_frames，不额外占纹理内存)。
var _ghost: AnimatedSprite2D = null
var _fade_tween: Tween = null
var _balance_shader: Shader = null


func _ready() -> void:
	# 透明已烘焙进 PNG 的 alpha 通道，不套白底 shader，避免误抠白毛。
	animation_finished.connect(_on_animation_finished)
	_setup_balance_material()
	_build_frames()
	if not _any_frame_loaded:
		_build_fallback()
	else:
		_build_ghost()
	print("[pet] ready frames_loaded=", _any_frame_loaded,
		" animations=", sprite_frames.get_animation_names() if sprite_frames else [],
		" current=", _current_anim,
		" position=", global_position)


func _process(_delta: float) -> void:
	var parent := get_parent()	# RoamController
	if parent == null:
		return
	# 定格/拖拽 → 停在当前帧不动(含淡入淡出残影)
	var frozen: bool = parent.dragging or parent.activity == "fixed"
	speed_scale = 0.0 if frozen else 1.0
	if _ghost != null:
		_ghost.speed_scale = speed_scale
	if frozen:
		return
	var target := _resolve_anim(parent)
	var key := "%s|%s" % [parent.get("mood"), parent.get("activity")]
	if key != _state_key:
		_state_key = key
		_oneshot_done.clear()
	if _oneshot_names.has(target):
		# 单次反应: 同一状态内不打断、不重播；演完由 finished 信号切回 idle。
		if _current_anim != target and not _oneshot_done.get(key, false) \
				and sprite_frames != null and sprite_frames.has_animation(target):
			_switch_to(target)
	else:
		if target != _current_anim and sprite_frames != null \
				and sprite_frames.has_animation(target):
			_switch_to(target)
	# 走路：按真实移动方向翻转，让动画朝向与实际运动一致（向左走 vs 向右走）
	if target == "walk":
		_update_walk_facing(parent)
	else:
		flip_h = false


## 单次反应播完 → 回 idle 循环，并记录本状态已演过。
func _on_animation_finished(anim: String) -> void:
	if not _oneshot_names.has(anim):
		return
	if anim == "stretch":
		var parent := get_parent()
		if parent != null and parent.has_method("finish_wake"):
			parent.finish_wake()
			return
	_oneshot_done[_state_key] = true
	if sprite_frames != null and sprite_frames.has_animation("idle"):
		_switch_to("idle")


## 切换到新动画：旧动画交给幽灵精灵定格并淡出，新动画从透明淡入。
## 两个精灵共享同一份 SpriteFrames，只多一个播放节点、不复制纹理。
func _switch_to(anim: String) -> void:
	if anim == _current_anim or sprite_frames == null \
			or not sprite_frames.has_animation(anim):
		return
	if _ghost == null:
		# 兜底立绘/极端降级路径：直接硬切。
		play(anim)
		_current_anim = anim
		_apply_balance(self, anim)
		return
	if _fade_tween != null and _fade_tween.is_valid():
		# 快速连切：中止上一次淡变，幽灵直接接住主精灵当前帧，避免三层叠影。
		_fade_tween.kill()
	_ghost.sprite_frames = sprite_frames
	_ghost.play(_current_anim)
	_ghost.frame = frame
	_ghost.flip_h = flip_h
	_ghost.speed_scale = speed_scale
	_apply_balance(_ghost, _current_anim)
	_ghost.self_modulate = Color(1, 1, 1, 1)
	_ghost.visible = true
	play(anim)
	_current_anim = anim
	_apply_balance(self, anim)
	self_modulate.a = 0.0
	# 非对称时长 + 两端缓入缓出(SINE/IN_OUT)：淡入淡出都不生硬，
	# 同时旧帧略快离场，把"新旧同强"的重影区间压到最短。
	_fade_tween = create_tween()
	_fade_tween.set_parallel(true)
	_fade_tween.tween_property(self, "self_modulate:a", 1.0, FADE_IN_TIME) \
			.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_fade_tween.tween_property(_ghost, "self_modulate:a", 0.0, FADE_OUT_TIME) \
			.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_fade_tween.chain().tween_callback(_on_fade_finished)


func _on_fade_finished() -> void:
	if _ghost != null:
		_ghost.visible = false
		_ghost.stop()
		_ghost.self_modulate = Color(1, 1, 1, 1)
	self_modulate.a = 1.0


## 校色 shader：本精灵与幽灵各持一份材质实例(增益随当前动画不同)。
func _setup_balance_material() -> void:
	_balance_shader = Shader.new()
	_balance_shader.code = BALANCE_SHADER_CODE
	material = _make_balance_material()


func _make_balance_material() -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = _balance_shader
	mat.set_shader_parameter("gain", Vector3.ONE)
	return mat


func _apply_balance(sprite: CanvasItem, anim: String) -> void:
	var mat := sprite.material as ShaderMaterial
	if mat == null:
		return
	mat.set_shader_parameter("gain", _balance.get(anim, Vector3.ONE))


## 交叉淡入淡出用的幽灵精灵：作为子节点继承位置/缩放，用 self_modulate
## (只影响自身、不向子节点传播)保证两条淡变曲线互不干扰。
func _build_ghost() -> void:
	_ghost = AnimatedSprite2D.new()
	_ghost.name = "TransitionGhost"
	_ghost.texture_filter = texture_filter
	_ghost.sprite_frames = sprite_frames
	# 同层子节点画在主精灵之后(之上)，但仍在地面阴影之上；交叉溶解对叠放顺序不敏感。
	_ghost.visible = false
	_ghost.self_modulate = Color(1, 1, 1, 0)
	_ghost.material = _make_balance_material()
	add_child(_ghost)


## 走路时按水平速度决定朝向：向左走原样，向右走水平翻转。
func _update_walk_facing(parent: Node) -> void:
	var vx: float = float(parent.get("velocity").x)
	flip_h = vx > 5.0


## mood/activity → 动画名 映射。未接入状态机的动画(blink/look_*/jump 等)
## 已在 SpriteFrames 中就绪，可由后续交互逻辑直接 play()。
func _resolve_anim(parent: Node) -> String:
	var activity: String = parent.get("activity")
	if activity == "wake":
		return "stretch"
	if activity == "roam":
		return "walk"
	var mood: String = parent.get("mood")
	match mood:
		"sleepy":
			return "sleep"
		"happy":
			return "happy"
		"shy":
			return "shy"
		"concerned":
			return "gentle_concern"
		"curious", "thinking":
			return "curious"
		_:
			return "idle"


## 读清单并构建全部 SpriteFrames。
func _build_frames() -> void:
	var text := FileAccess.get_file_as_string(MANIFEST_PATH)
	if text == "":
		push_warning("[pet] 缺少动画清单: %s" % MANIFEST_PATH)
		return
	var parser := JSON.new()
	if parser.parse(text) != OK:
		push_warning("[pet] 动画清单解析失败: %s" % parser.get_error_message())
		return
	_manifest = parser.data.get("anims", {})
	if _manifest.is_empty():
		return
	var frames := SpriteFrames.new()
	# idle 优先构建，保证初始/回退动画先存在。
	var names: Array = _manifest.keys()
	names.sort()
	if names.has("idle"):
		names.erase("idle")
		names = ["idle"] + names
	for anim in names:
		var info: Dictionary = _manifest[anim]
		var textures := _load_anim(info)
		if textures.is_empty():
			continue
		var balance: Array = info.get("balance", [])
		if balance.size() == 3:
			_balance[anim] = Vector3(
					float(balance[0]), float(balance[1]), float(balance[2]))
		frames.add_animation(anim)
		var is_loop: bool = bool(info.get("loop", false))
		var durations: Array = info.get("durations", [])
		frames.set_animation_loop(anim, is_loop)
		if is_loop:
			frames.set_animation_speed(anim, float(info.get("fps", 8.0)))
		else:
			# animation_speed=1 时, 每帧实际时长 = add_frame 第三参数的秒数。
			frames.set_animation_speed(anim, 1.0)
			_oneshot_names[anim] = true
		for i in textures.size():
			# Godot 4.7.2 SpriteFrames 无 set_frame_duration，时长须随 add_frame 传入。
			var duration := 1.0
			if not is_loop and i < durations.size():
				duration = float(durations[i])
			frames.add_frame(anim, textures[i], duration)
		_any_frame_loaded = true
	if _any_frame_loaded:
		# SpriteFrames.new() 自带空的 "default" 动画，移除以保持清单动画名。
		frames.remove_animation("default")
		sprite_frames = frames
		play("idle")
		_current_anim = "idle"
		_apply_balance(self, "idle")


## 按统一包络框加载并校准一个动画的全部帧到 300 画布。
## 同一动画所有帧共用一个缩放比例和对齐基准，跳跃/悬空等位移帧不会忽大忽小。
func _load_anim(info: Dictionary) -> Array:
	var dir: String = info.get("dir", "")
	var n_frames: int = int(info.get("frame_count", 0))
	var union: Array = info.get("union", [0, 0, 0, 0])
	if dir == "" or n_frames <= 0 or union.size() < 4:
		return []
	var ux: int = int(union[0])
	var uy: int = int(union[1])
	var uw: int = int(union[2])
	var uh: int = int(union[3])
	if uw <= 0 or uh <= 0:
		return []
	var scale := minf(TARGET_CONTENT_HEIGHT / float(uh),
			TARGET_CONTENT_WIDTH / float(uw))
	var part_w := maxi(1, int(round(float(uw) * scale)))
	var part_h := maxi(1, int(round(float(uh) * scale)))
	# union 水平居中、底边对齐基线。
	var dest := Vector2i(
			int(round(float(CANVAS_SIZE - part_w) * 0.5)),
			BASELINE_Y - part_h)
	var textures: Array = []
	for i in range(1, n_frames + 1):
		var path := "res://assets/%s/frame-%04d.png" % [dir, i]
		if not ResourceLoader.exists(path):
			push_warning("[pet] 缺帧: %s" % path)
			break
		var source: Image = (load(path) as Texture2D).get_image()
		if source == null:
			continue
		source.convert(Image.FORMAT_RGBA8)
		var part := Image.create(uw, uh, false, Image.FORMAT_RGBA8)
		part.fill(Color(0.0, 0.0, 0.0, 0.0))
		part.blit_rect(source, Rect2i(ux, uy, uw, uh), Vector2i.ZERO)
		part.resize(part_w, part_h, Image.INTERPOLATE_LANCZOS)
		var canvas := Image.create(CANVAS_SIZE, CANVAS_SIZE, false,
				Image.FORMAT_RGBA8)
		canvas.fill(Color(0.0, 0.0, 0.0, 0.0))
		canvas.blit_rect(part, Rect2i(Vector2i.ZERO, Vector2i(part_w, part_h)),
				dest)
		textures.append(ImageTexture.create_from_image(canvas))
	if textures.size() < n_frames:
		push_warning("[pet] %s 仅加载 %d/%d 帧" % [dir, textures.size(), n_frames])
	return textures


## 完全没有帧图时的兜底：单帧静态水彩立绘（缩到 300px 画布，脚底对齐基线）。
func _build_fallback() -> void:
	var tex: Texture2D = null
	if ResourceLoader.exists(FALLBACK_TEXTURE):
		tex = load(FALLBACK_TEXTURE)
	if tex == null:
		return
	var tex_300 := _calibrate_texture(tex)
	var fallback := SpriteFrames.new()
	fallback.add_animation("idle")
	fallback.set_animation_loop("idle", false)
	fallback.add_frame("idle", tex_300)
	sprite_frames = fallback
	play("idle")
	_current_anim = "idle"


## 保持比例统一透明内容包络和脚底基线（仅兜底立绘使用）。
func _calibrate_texture(tex: Texture2D) -> Texture2D:
	var source := tex.get_image()
	if source == null:
		return tex
	var used := source.get_used_rect()
	if used.size.x <= 0 or used.size.y <= 0:
		return tex
	var scale := minf(
		float(TARGET_CONTENT_HEIGHT) / float(used.size.y),
		float(TARGET_CONTENT_WIDTH) / float(used.size.x)
	)
	var scaled_size := Vector2i(
		 maxi(1, int(round(float(used.size.x) * scale))),
		 maxi(1, int(round(float(used.size.y) * scale)))
	)
	var cropped := Image.create(used.size.x, used.size.y, false, Image.FORMAT_RGBA8)
	cropped.blit_rect(source, used, Vector2i.ZERO)
	cropped.resize(scaled_size.x, scaled_size.y, Image.INTERPOLATE_LANCZOS)
	var canvas := Image.create(CANVAS_SIZE, CANVAS_SIZE, false, Image.FORMAT_RGBA8)
	canvas.fill(Color(0.0, 0.0, 0.0, 0.0))
	var destination := Vector2i(
		(CANVAS_SIZE - scaled_size.x) / 2,
		BASELINE_Y - scaled_size.y
	)
	canvas.blit_rect(cropped, Rect2i(Vector2i.ZERO, scaled_size), destination)
	return ImageTexture.create_from_image(canvas)
