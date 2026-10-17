extends Node
## 窗口控制器：透明置顶窗口的多显示器定位、拖动跟随和位置持久化。

const DEFAULT_EDGE_PIXELS := 20
const STATE_PATH := "res://../output/runtime/desktop-state.json"
const SPRITE_SIZE := 240.0
const SPRITE_HALF := SPRITE_SIZE * 0.5
const ROAM_MARGIN := 24.0


func restore_or_snap() -> void:
	var saved: Variant = _load_saved_position()
	if saved != null:
		get_window().position = _clamp_to_screen(saved)
		print("[poc] restored window position=", get_window().position)
		return
	snap_to_current_screen()


func snap_to_current_screen() -> void:
	var screen_index: int = get_window().current_screen
	var usable: Rect2i = DisplayServer.screen_get_usable_rect(screen_index)
	var window := get_window()
	var target := Vector2i(
		usable.position.x + DEFAULT_EDGE_PIXELS,
		usable.position.y + DEFAULT_EDGE_PIXELS
	)
	window.position = target
	print("[poc] window positioned on screen=", screen_index, " at=", target)


func reveal() -> void:
	var window := get_window()
	var usable := DisplayServer.screen_get_usable_rect(0)
	window.position = Vector2i(
		usable.position.x + DEFAULT_EDGE_PIXELS,
		usable.position.y + DEFAULT_EDGE_PIXELS
	)
	window.show()
	window.grab_focus()
	print("[poc] window revealed at=", window.position)


func follow_pet(pet: Node2D) -> bool:
	var viewport_size := get_viewport().get_visible_rect().size
	var safe := Rect2(
		Vector2(SPRITE_HALF + ROAM_MARGIN, SPRITE_HALF + ROAM_MARGIN),
		viewport_size - Vector2(SPRITE_SIZE + ROAM_MARGIN * 2.0, SPRITE_SIZE + ROAM_MARGIN * 2.0)
	)
	var shift := Vector2.ZERO
	if pet.position.x < safe.position.x: shift.x = pet.position.x - safe.position.x
	elif pet.position.x > safe.end.x: shift.x = pet.position.x - safe.end.x
	if pet.position.y < safe.position.y: shift.y = pet.position.y - safe.position.y
	elif pet.position.y > safe.end.y: shift.y = pet.position.y - safe.end.y
	if shift == Vector2.ZERO:
		return false
	var window := get_window()
	window.position += Vector2i(roundi(shift.x), roundi(shift.y))
	pet.position -= shift
	window.position = _clamp_to_screen(window.position)
	return true


func save_position() -> void:
	var path := ProjectSettings.globalize_path(STATE_PATH)
	var data: Dictionary = {}
	if FileAccess.file_exists(path):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
		if typeof(parsed) == TYPE_DICTIONARY:
			data = parsed
	var position := get_window().position
	data["pet_window_position"] = {"x": position.x, "y": position.y}
	data["pet_window_screen"] = current_screen_index()
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(data, "  "))
		file.close()


func window_payload() -> Dictionary:
	var position := get_window().position
	return {
		"window_position": {"x": position.x, "y": position.y},
		"screen_position": {"x": position.x + int(get_viewport().get_visible_rect().size.x * 0.5), "y": position.y + int(get_viewport().get_visible_rect().size.y * 0.5)},
	}


func _load_saved_position():
	var path := ProjectSettings.globalize_path(STATE_PATH)
	if not FileAccess.file_exists(path): return null
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY: return null
	var value = parsed.get("pet_window_position")
	if typeof(value) != TYPE_DICTIONARY: return null
	if not value.has("x") or not value.has("y"): return null
	return Vector2i(int(value.x), int(value.y))


func _clamp_to_screen(position: Vector2i) -> Vector2i:
	var screen_index := get_window().current_screen
	for index in DisplayServer.get_screen_count():
		var usable := DisplayServer.screen_get_usable_rect(index)
		if usable.has_point(position):
			screen_index = index
			break
	var usable := DisplayServer.screen_get_usable_rect(screen_index)
	return Vector2i(
		clampi(position.x, usable.position.x + DEFAULT_EDGE_PIXELS, usable.end.x - get_window().size.x - DEFAULT_EDGE_PIXELS),
		clampi(position.y, usable.position.y + DEFAULT_EDGE_PIXELS, usable.end.y - get_window().size.y - DEFAULT_EDGE_PIXELS)
	)


func current_screen_index() -> int:
	return get_window().current_screen
