extends Node2D
## Optional 3D presentation layer. It stays hidden until a versioned GLB exists.

const MODEL_PATH := "res://assets/3d/yayan_v001.glb"
const VIEW_SIZE := Vector2i(180, 180)

var model_loaded := false
var _viewport: SubViewport


func _ready() -> void:
	visible = false
	if not ResourceLoader.exists(MODEL_PATH):
		return
	var packed := load(MODEL_PATH)
	if not packed is PackedScene:
		push_warning("3D resource is not a scene: %s" % MODEL_PATH)
		return
	_build_viewport(packed)


func _build_viewport(packed: PackedScene) -> void:
	var container := SubViewportContainer.new()
	container.name = "ModelViewportContainer"
	container.size = Vector2(VIEW_SIZE)
	container.position = -Vector2(VIEW_SIZE) * 0.5
	container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(container)

	_viewport = SubViewport.new()
	_viewport.name = "ModelViewport"
	_viewport.size = VIEW_SIZE
	_viewport.transparent_bg = true
	_viewport.handle_input_locally = false
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_viewport.world_3d = World3D.new()
	container.add_child(_viewport)

	var camera := Camera3D.new()
	camera.position = Vector3(0.0, 1.05, 3.25)
	camera.look_at_from_position(camera.position, Vector3(0.0, 0.85, 0.0))
	_viewport.add_child(camera)

	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35.0, -25.0, 0.0)
	light.light_energy = 1.2
	_viewport.add_child(light)

	var model := packed.instantiate()
	model.name = "YayanModel"
	_viewport.add_child(model)
	model_loaded = true
	visible = true

