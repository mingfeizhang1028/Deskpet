"""PetBridge：Python 与 Godot 之间的本地通信服务。

职责（边界）：
- 只监听本地回环端口，接收 Godot 宠物事件，转发已经决定好的宠物命令；
- 不接触 API Key、SQLite 或用户记忆；不把事件原文写入日志；
- Godot 断开或未连接时，本服务保持可运行，聊天功能不受影响；
- 通信使用 JSON 换行协议，信封契约见 contracts.py。

Godot 侧断开不拖垮 Python：accept 循环和每个客户端都在独立线程，
任何 socket 错误都只记录到 last_error，不向外抛出。
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Callable, List, Optional

from contracts import (
    DEFAULT_BRIDGE_HOST,
    DEFAULT_BRIDGE_PORT,
    decode_bridge_line,
    encode_bridge_message,
    make_bridge_message,
    parse_pet_event,
    validate_pet_command,
)

logger = logging.getLogger("pet_bridge")

RECV_CHUNK = 65536


class PetBridge:
    """本地 TCP 服务。start() 成功后在后台线程接受连接。"""

    def __init__(
        self,
        host: str = DEFAULT_BRIDGE_HOST,
        port: int = DEFAULT_BRIDGE_PORT,
        on_event: Optional[Callable[[dict], None]] = None,
    ):
        self.host = host
        self.port = port
        self.on_event = on_event
        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._clients: List[socket.socket] = []
        self._lock = threading.RLock()
        self._running = False
        self.last_error: Optional[str] = None
        self.hello_count = 0

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """绑定并监听。port=0 时由系统分配端口（测试用）。"""
        with self._lock:
            if self._running:
                return True
            try:
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((self.host, self.port))
                server.listen(4)
                server.settimeout(0.5)
            except OSError as error:
                self.last_error = f"bind 失败：{type(error).__name__}: {error}"
                logger.warning("pet_bridge bind failed: %s", self.last_error)
                return False
            self._server = server
            self.port = int(server.getsockname()[1])
            self._running = True
            self._thread = threading.Thread(target=self._accept_loop, name="pet-bridge-accept", daemon=True)
            self._thread.start()
            logger.info("pet_bridge listening on %s:%d", self.host, self.port)
            return True

    def stop(self) -> None:
        with self._lock:
            self._running = False
            for client in list(self._clients):
                try:
                    client.close()
                except OSError:
                    pass
            self._clients.clear()
            if self._server is not None:
                try:
                    self._server.close()
                except OSError:
                    pass
                self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def connected(self) -> bool:
        """是否存在存活客户端。"""
        with self._lock:
            return any(self._client_alive(client) for client in self._clients)

    @staticmethod
    def _client_alive(client: socket.socket) -> bool:
        try:
            client.getpeername()
            return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # 发送
    # ------------------------------------------------------------------

    def send_command(self, command: dict) -> bool:
        """向所有已连接客户端发送一条宠物命令。命令必须通过契约校验。"""
        errors = validate_pet_command(command)
        if errors:
            self.last_error = "命令未通过校验：" + "; ".join(errors)
            logger.warning("pet_bridge send rejected: %s", self.last_error)
            return False
        message = make_bridge_message("pet_command", command)
        raw = encode_bridge_message(message)
        with self._lock:
            clients = list(self._clients)
        if not clients and self._running:
            # accept() runs on a background thread; give a just-connected
            # Godot/client socket a short window to enter the client list.
            deadline = time.time() + 0.2
            while time.time() < deadline and not clients:
                time.sleep(0.005)
                with self._lock:
                    clients = list(self._clients)
        delivered = False
        for client in clients:
            try:
                client.sendall(raw)
                delivered = True
            except OSError as error:
                self.last_error = f"发送失败：{type(error).__name__}"
                logger.warning("pet_bridge send error: %s", self.last_error)
                with self._lock:
                    if client in self._clients:
                        self._clients.remove(client)
        return delivered

    # ------------------------------------------------------------------
    # 接收
    # ------------------------------------------------------------------

    def _accept_loop(self) -> None:
        while self._running:
            try:
                client, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._lock:
                self._clients.append(client)
            threading.Thread(
                target=self._handle_client,
                args=(client,),
                name="pet-bridge-client",
                daemon=True,
            ).start()

    def _handle_client(self, client: socket.socket) -> None:
        buffer = b""
        try:
            client.settimeout(1.0)
            while self._running:
                try:
                    chunk = client.recv(RECV_CHUNK)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    self._dispatch_line(line)
        except OSError:
            pass
        finally:
            with self._lock:
                if client in self._clients:
                    self._clients.remove(client)
            try:
                client.close()
            except OSError:
                pass

    def _dispatch_line(self, line: bytes) -> None:
        message = decode_bridge_line(line)
        if message is None:
            return
        payload = message.get("payload") or {}
        if message.get("type") == "pet_event":
            event = parse_pet_event(payload)
            if event is None:
                return
            if event.get("event") == "hello":
                self.hello_count += 1
            if self.on_event is not None:
                self.on_event(event)
