import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "desktop"))

from event_bus import EVENT_TYPES, EventBus  # noqa: E402


class EventBusTests(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()

    def tearDown(self):
        self.bus.clear()

    def test_subscribe_and_publish_delivers_payload_and_trace(self):
        received = []
        self.bus.subscribe("chat.user_message", lambda _type, envelope: received.append(envelope))
        self.bus.publish("chat.user_message", {"text": "你好"}, trace_id="t-1")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["payload"]["text"], "你好")
        self.assertEqual(received[0]["trace_id"], "t-1")

    def test_unknown_event_type_rejected(self):
        with self.assertRaises(ValueError):
            self.bus.subscribe("nope.nope", lambda *args: None)
        with self.assertRaises(ValueError):
            self.bus.publish("nope.nope")

    def test_unsubscribe_stops_delivery(self):
        received = []
        token = self.bus.subscribe("focus.completed", lambda _t, e: received.append(e))
        self.assertTrue(self.bus.unsubscribe(token))
        self.bus.publish("focus.completed")
        self.assertEqual(received, [])
        self.assertEqual(self.bus.subscriber_count("focus.completed"), 0)

    def test_priority_order_high_first(self):
        order = []
        self.bus.subscribe("pet.command_sent", lambda _t, e: order.append("low"), priority=1)
        self.bus.subscribe("pet.command_sent", lambda _t, e: order.append("high"), priority=100)
        self.bus.publish("pet.command_sent")
        self.assertEqual(order, ["high", "low"])

    def test_subscriber_error_does_not_break_publish(self):
        received = []

        def broken(_type, _envelope):
            raise RuntimeError("订阅者挂了")

        def good(_type, envelope):
            received.append(envelope)

        self.bus.subscribe("memory.confirmed", broken)
        self.bus.subscribe("memory.confirmed", good)
        self.bus.publish("memory.confirmed")
        self.assertEqual(len(received), 1)
        self.assertEqual(len(self.bus.last_publish_errors), 1)

    def test_event_types_include_step1_core_events(self):
        for event in ("chat.user_message", "emotion.slow_ready", "memory.candidate_ready", "pet.event_received"):
            self.assertIn(event, EVENT_TYPES)


if __name__ == "__main__":
    unittest.main()
