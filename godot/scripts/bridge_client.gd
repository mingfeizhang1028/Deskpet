extends Node
## Bridge 客户端：连接 Python PetBridge，发送宠物事件，接收宠物命令。
##
## 契约见 desktop/contracts.py：JSON 换行协议，信封带 schema_version / trace_id / timestamp。
## 重连策略：指数退避，上限 10 秒；永不崩溃，断线只打印日志。

signal command_received(command: Dictionary)

const DEFAULT_HOST := "127.0.0.1"
const DEFAULT_PORT := 17899
const PORT_FILE := "../output/runtime/bridge-port.txt"
const MAX_BACKOFF_SECONDS := 10.0
const MAX_RETRIES_BEFORE_NOTICE := 5

var host := DEFAULT_HOST
var port := DEFAULT_PORT

var _socket: StreamPeerTCP
var _buffer := PackedByteArray()
var _retry := 0
var _backoff := 2.0
var _reconnect_timer: Timer
var _hello_sent := false


func start(custom_host: String = DEFAULT_HOST, custom_port: int = -1) -> void:
	host = custom_host
	port = _resolve_port(custom_port)
	print("[bridge] connecting to ", host, ":", port)
	_connect()


func _resolve_port(custom_port: int) -> int:
	if custom_port > 0:
		return custom_port
	var project_dir := ProjectSettings.globalize_path("res://")
	var port_file := project_dir.path_join(PORT_FILE)
	if FileAccess.file_exists(port_file):
		var stream := FileAccess.open(port_file, FileAccess.READ)
		if stream != null:
			var parsed := int(stream.get_line().strip_edges())
			if parsed > 0:
				return parsed
	return DEFAULT_PORT


func _process(_delta: float) -> void:
	if _socket == null:
		return
	var status: int = _socket.get_status()
	if _socket.poll() != OK:
		_drop_connection()
		return
	status = _socket.get_status()
	if status == StreamPeerTCP.STATUS_CONNECTED:
		if not _hello_sent:
			_hello_sent = true
			_send_hello()
		_poll()


func _connect() -> void:
	_retry += 1
	_hello_sent = false
	_socket = StreamPeerTCP.new()
	var error := _socket.connect_to_host(host, port)
	if error != OK:
		_schedule_reconnect()
		return
	if _socket.get_status() == StreamPeerTCP.STATUS_CONNECTED:
		_hello_sent = true
		_send_hello()


func _schedule_reconnect() -> void:
	if _reconnect_timer != null:
		return
	if _retry > MAX_RETRIES_BEFORE_NOTICE:
		print("[bridge] still offline after ", _retry, " attempts; will keep retrying")
	_reconnect_timer = Timer.new()
	_reconnect_timer.one_shot = true
	_reconnect_timer.wait_time = _backoff
	_reconnect_timer.timeout.connect(_on_reconnect_timeout)
	add_child(_reconnect_timer)
	_reconnect_timer.start()
	_backoff = minf(_backoff * 2.0, MAX_BACKOFF_SECONDS)


func _on_reconnect_timeout() -> void:
	_reconnect_timer = null
	_connect()


func _send_hello() -> void:
	if _socket == null or _socket.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return
	var now := Time.get_unix_time_from_system()
	_send_line({
		"schema_version": 1,
		"type": "pet_event",
		"payload": {
			"event": "hello",
			"timestamp": now,
			"trace_id": "poc-hello-%d" % Time.get_ticks_msec(),
		},
		"trace_id": "poc-hello-%d" % Time.get_ticks_msec(),
		"timestamp": now,
	})
	print("[bridge] hello sent")


func _poll() -> void:
	if _socket.get_available_bytes() <= 0:
		return
	var result := _socket.get_data(_socket.get_available_bytes())
	if result[0] != OK:
		_drop_connection()
		return
	_buffer.append_array(result[1])
	while true:
		var newline_index := _find_newline(_buffer)
		if newline_index == -1:
			break
		var line := _buffer.slice(0, newline_index)
		_buffer = _buffer.slice(newline_index + 1)
		_handle_line(line)


## 手动查找换行字节(0x0A)，避免 PackedByteArray.find 的 int 参数歧义。
func _find_newline(data: PackedByteArray) -> int:
	for index in data.size():
		if data[index] == 0x0A:
			return index
	return -1


func _handle_line(line: PackedByteArray) -> void:
	var parsed: Variant = JSON.parse_string(line.get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	var message: Dictionary = parsed
	if message.get("type") != "pet_command":
		return
	var payload: Variant = message.get("payload")
	if typeof(payload) != TYPE_DICTIONARY:
		return
	var command: Dictionary = payload
	print("[bridge] pet_command=", command.get("command", "?"), " state=", command.get("state", "-"))
	command_received.emit(command)


func _send_line(payload: Dictionary) -> void:
	if _socket == null:
		return
	_socket.put_data((JSON.stringify(payload) + "\n").to_utf8_buffer())


func _drop_connection() -> void:
	if _socket != null:
		_socket.disconnect_from_host()
		_socket = null
	_backoff = 2.0
	_schedule_reconnect()
