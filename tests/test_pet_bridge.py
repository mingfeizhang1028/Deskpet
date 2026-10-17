import socket
import sys
import time
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "desktop"))

from contracts import (  # noqa: E402
    make_bridge_message,
    make_pet_command,
)
from pet_bridge import PetBridge  # noqa: E402


class PetBridgeTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.bridge = PetBridge(host="127.0.0.1", port=0, on_event=self.events.append)

    def tearDown(self):
        self.bridge.stop()

    def _connect(self):
        client = socket.create_connection(("127.0.0.1", self.bridge.port), timeout=3)
        return client

    def test_start_binds_an_ephemeral_port(self):
        self.assertTrue(self.bridge.start())
        self.assertTrue(self.bridge.running)
        self.assertGreater(self.bridge.port, 0)

    def test_hello_event_is_parsed_and_delivered(self):
        self.assertTrue(self.bridge.start())
        client = self._connect()
        message = make_bridge_message("pet_event", {"event": "hello"})
        client.sendall(
            (
                '{"schema_version": %d, "type": "pet_event", "payload": {"event": "hello"},'
                ' "trace_id": "t1", "timestamp": 100.0}\n' % message["schema_version"]
            ).encode("utf-8")
        )
        deadline = time.time() + 3
        while time.time() < deadline and not self.events:
            time.sleep(0.02)
        client.close()
        self.assertEqual([event["event"] for event in self.events], ["hello"])
        self.assertEqual(self.bridge.hello_count, 1)

    def test_invalid_event_is_ignored(self):
        self.assertTrue(self.bridge.start())
        client = self._connect()
        client.sendall(
            b'{"schema_version": 1, "type": "pet_event", "payload": {"event": "warp"},'
            b' "trace_id": "t2", "timestamp": 100.0}\n'
        )
        time.sleep(0.2)
        client.close()
        self.assertEqual(self.events, [])

    def test_send_command_delivers_to_connected_client(self):
        self.assertTrue(self.bridge.start())
        client = self._connect()
        command = make_pet_command("set_state", state="happy", duration_ms=1000)
        self.assertTrue(self.bridge.send_command(command))
        deadline = time.time() + 3
        data = b""
        while time.time() < deadline:
            try:
                chunk = client.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break
        self.assertIn(b'"state":"happy"', data)
        deadline = time.time() + 3
        while time.time() < deadline and not self.bridge.connected:
            time.sleep(0.02)
        self.assertTrue(self.bridge.connected)
        client.close()

    def test_send_invalid_command_is_rejected(self):
        self.assertTrue(self.bridge.start())
        self.assertFalse(self.bridge.send_command({"command": "fly"}))
        self.assertIn("未通过校验", self.bridge.last_error or "")

    def test_disconnect_does_not_break_bridge(self):
        self.assertTrue(self.bridge.start())
        client = self._connect()
        client.close()
        time.sleep(0.2)
        self.assertTrue(self.bridge.running)
        second = self._connect()
        deadline = time.time() + 3
        while time.time() < deadline and not self.bridge.connected:
            time.sleep(0.02)
        self.assertTrue(self.bridge.connected)
        second.close()


if __name__ == "__main__":
    unittest.main()
