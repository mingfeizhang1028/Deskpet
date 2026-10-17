extends Area2D
## 透明窗口内的安全漫游与交互骨架。
## 真实 GLB/骨骼动画接入前，使用低成本绘制保持可运行与可测试。

signal pet_event(event_name: String, payload: Dictionary)

const MARGIN := 24.0
## 动画精灵目标显示尺寸：画布 300 * 场景 scale 0.8 ≈ 240px。
## 漫游边界、碰撞热区和视觉包络共用这套尺寸，保证猫不切边。
const SPRITE_SIZE := 240.0
const SPRITE_HALF := SPRITE_SIZE * 0.5
const MIN_STOP := 0.6
const MAX_STOP := 1.8
## 太久没人理(触摸/悬停)就犯困睡着的时长(秒)。
const IDLE_SLEEP_SECONDS := 25.0
const DRAG_THRESHOLD := 8.0

var mood := "idle"
var activity := "idle"
var target := Vector2.ZERO
var velocity := Vector2.ZERO
var stop_left := 0.0
var dragging := false
var drag_offset := Vector2.ZERO
var _press_pos := Vector2.ZERO
var _moved := false
var hovered := false
var _rng := RandomNumberGenerator.new()
var _last_interact := 0.0
## 锁定在一条水平线上左右移动(只动 X，Y 固定)。
var home_y := 0.0

func _ready() -> void:
	mouse_entered.connect(_mouse_enter)
	mouse_exited.connect(_mouse_exit)
	_rng.randomize()
	_last_interact = Time.get_unix_time_from_system()
	home_y = get_viewport_rect().size.y - SPRITE_HALF - MARGIN
	position = Vector2(get_viewport_rect().size.x * 0.5, home_y)
	_pick_target()
	set_process(true)
	queue_redraw()

func set_state(state: String) -> void:
	if state in ["idle", "happy", "concerned", "curious", "sleepy", "shy", "thinking"]:
		mood = state
		if state == "sleepy":
			# 睡眠时停止位置移动，但让 pet_sprite 继续播放 sleep 循环。
			activity = "quiet"
		queue_redraw()

func set_activity(value: String) -> void:
	activity = value
	if value in ["quiet", "fixed"]: velocity = Vector2.ZERO
	queue_redraw()

## 记录一次人类互动；若是睡着状态则唤醒到 idle。
func _touch() -> void:
	_last_interact = Time.get_unix_time_from_system()
	if mood == "sleepy":
		set_state("idle")
		_set_wake_target()
		queue_redraw()

func _process(delta: float) -> void:
	# 太久没人理 -> 犯困睡着(即便在漫游中也停下睡)
	if not dragging and not hovered and mood == "idle" \
			and Time.get_unix_time_from_system() - _last_interact > IDLE_SLEEP_SECONDS:
		set_state("sleepy")
	var bounds := Rect2(Vector2(SPRITE_HALF, SPRITE_HALF), get_viewport_rect().size - Vector2(SPRITE_SIZE, SPRITE_SIZE))
	if dragging or activity in ["quiet", "fixed"]:
		queue_redraw()
		return
	if activity == "wake":
		velocity = Vector2.ZERO
		queue_redraw()
		return
	if stop_left > 0.0:
		stop_left -= delta
		if stop_left <= 0.0: _pick_target()
		queue_redraw()
		return
	var distance := absf(target.x - position.x)
	if distance < 5.0:
		velocity = Vector2.ZERO
		stop_left = _rng.randf_range(MIN_STOP, MAX_STOP)
	else:
		# 走路速度与步幅匹配: walk 为原地循环动画(25帧/12fps≈2.08s)，
		# 按步长≈0.65身长估算每循环应位移约196px → 约90px/s，避免脚下打滑。
		var speed := 90.0 if activity == "roam" else 24.0
		velocity = Vector2(speed if target.x > position.x else -speed, 0.0)
		position.x += velocity.x * delta
		position.x = clampf(position.x, bounds.position.x, bounds.end.x)
		position.y = home_y
	queue_redraw()

func _pick_target() -> void:
	var size := get_viewport_rect().size - Vector2(SPRITE_SIZE, SPRITE_SIZE)
	target = Vector2(SPRITE_HALF + _rng.randf_range(0.0, maxf(1.0, size.x)), home_y)
	activity = "roam"

func _set_wake_target() -> void:
	var size := get_viewport_rect().size - Vector2(SPRITE_SIZE, SPRITE_SIZE)
	target = Vector2(SPRITE_HALF + _rng.randf_range(0.0, maxf(1.0, size.x)), home_y)
	activity = "wake"
	velocity = Vector2.ZERO

func finish_wake() -> void:
	if activity == "wake":
		_pick_target()
		queue_redraw()

func _input_event(_viewport: Node, event: InputEvent, _shape_idx: int) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			dragging = true
			_press_pos = get_global_mouse_position()
			_moved = false
			drag_offset = get_global_mouse_position() - global_position
			_touch()
		else:
			var was_click: bool = dragging and not _moved \
					and get_global_mouse_position().distance_to(_press_pos) < DRAG_THRESHOLD
			dragging = false
			position.y = home_y
			if was_click:
				pet_event.emit("clicked", {"position": global_position})
			elif _moved:
				pet_event.emit("drag_end", {"position": global_position})
	elif event is InputEventMouseMotion and dragging:
		if _moved or get_global_mouse_position().distance_to(_press_pos) >= DRAG_THRESHOLD:
			_moved = true
			global_position = get_global_mouse_position() - drag_offset
			pet_event.emit("dragged", {"position": global_position})

func _mouse_enter() -> void:
	hovered = true
	_touch()
	pet_event.emit("hover_start", {})
	queue_redraw()

func _mouse_exit() -> void:
	hovered = false
	pet_event.emit("hover_end", {})
	queue_redraw()

func _draw() -> void:
	# 角色外观由动画精灵（pet_controller 下方 PetSprite）提供；这里画地面阴影
	# 强化"纸片蹲桌面"感，并按情绪微调阴影大小（变量状态下落得"更稳"）。
	var shadow_scale := 1.0
	if mood in ["sleepy", "shy"]:
		shadow_scale = 0.82
	elif mood == "happy":
		shadow_scale = 1.15
	draw_set_transform(
		Vector2(0.0, SPRITE_HALF - 10.0),
		0.0,
		Vector2(1.5, 0.42) * shadow_scale
	)
	draw_circle(Vector2.ZERO, 30.0, Color(0.0, 0.0, 0.0, 0.06))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
