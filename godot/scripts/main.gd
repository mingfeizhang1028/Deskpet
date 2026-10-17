extends Node2D
## 芽砚 Godot 空窗口 POC 主控。
##
## 用法：
##   正常模式  godot --path godot            （右下角 + 连接 Python PetBridge）
##   自检模式  godot --path godot -- --self-check
##
## 自检模式会打印窗口属性与屏幕信息、截透明窗口图到 output/runtime/godot-poc.png，
## 然后连接 bridge（可选），最后以 POC_OK 退出。bridge 不可达不视为失败，
## 因为 Godot 掉线绝不能影响 Python 侧聊天。

const SELF_CHECK_ARG := "--self-check"

@onready var window_controller: Node = $WindowController
@onready var bridge_client: Node = $BridgeClient
@onready var roam_controller: Node = $RoamController

var _user_args: PackedStringArray


func _ready() -> void:
	_user_args = OS.get_cmdline_user_args()
	_enforce_transparent_window()
	window_controller.restore_or_snap()
	print("[poc] pet_state visible=", $RoamController/PetSprite.visible,
		" position=", $RoamController/PetSprite.global_position,
		" viewport=", get_viewport().get_visible_rect().size)
	# The PNG sprite is the current fallback; the old POC panel must not cover it.
	bridge_client.command_received.connect(_on_pet_command)
	roam_controller.pet_event.connect(_on_pet_event)
	if _user_args.has(SELF_CHECK_ARG):
		_run_self_check()
	else:
		bridge_client.start()

func _on_pet_command(command: Dictionary) -> void:
	var name := str(command.get("command", ""))
	if name == "show_window": window_controller.reveal()
	elif name == "set_state": roam_controller.set_state(str(command.get("state", "idle")))
	elif name == "set_activity": roam_controller.set_activity(str(command.get("state", "idle")))
	elif name == "freeze": roam_controller.set_activity("fixed")
	elif name == "move_to": roam_controller.target = Vector2(float(command.get("x", 100)), float(command.get("y", 100)))

func _on_pet_event(event_name: String, payload: Dictionary) -> void:
	if event_name == "dragged":
		window_controller.follow_pet(roam_controller)
	elif event_name == "drag_end":
		window_controller.save_position()
	var now := Time.get_unix_time_from_system()
	var enriched := {"event": event_name, "timestamp": now}.merged(payload)
	enriched.merge(window_controller.window_payload())
	var envelope := {"schema_version": 1, "type": "pet_event", "payload": enriched, "trace_id": "pet-%d" % Time.get_ticks_msec(), "timestamp": now}
	bridge_client._send_line(envelope)


## 使用真正的逐像素透明窗口，让 PNG 的 alpha 直接透出桌面。
func _enforce_transparent_window() -> void:
	var window := get_window()
	window.transparent = true
	var viewport := window
	viewport.transparent_bg = true
	RenderingServer.set_default_clear_color(Color(0.0, 0.0, 0.0, 0.0))


func _run_self_check() -> void:
	var window := get_window()
	print("[poc-check] borderless=", window.borderless)
	print("[poc-check] always_on_top=", window.always_on_top)
	print("[poc-check] transparent=", window.transparent)
	print("[poc-check] screen_count=", DisplayServer.get_screen_count())
	print("[poc-check] primary_screen=", DisplayServer.get_primary_screen())
	for screen_index in DisplayServer.get_screen_count():
		print("[poc-check] screen_rect=", screen_index, " ", DisplayServer.screen_get_usable_rect(screen_index))
	print("[poc-check] window_position=", window.position)
	print("[poc-check] window_size=", window.size, " viewport=", get_viewport().get_visible_rect().size)
	await get_tree().create_timer(0.6).timeout
	# 无渲染环境（headless）viewport 纹理为空，截图步骤跳过，不阻塞自检。
	var image: Image = null
	if DisplayServer.get_name() != "headless":
		var viewport_texture := get_viewport().get_texture()
		if viewport_texture != null:
			image = viewport_texture.get_image()
	if image != null:
		var project_dir := ProjectSettings.globalize_path("res://")
		var shot_path := project_dir.path_join(
			"../runtime/godot-poc-export.png" if OS.has_feature("standalone")
			else "../output/runtime/godot-poc.png"
		)
		image.save_png(shot_path)
		print("[poc-check] screenshot=", shot_path)
	else:
		print("[poc-check] screenshot=skipped (headless)")
	# bridge 握手：可选验证，失败不阻塞（与生产降级路径一致）
	bridge_client.start()
	await get_tree().create_timer(2.5).timeout
	print("[poc-check] POC_OK")
	get_tree().quit(0)
