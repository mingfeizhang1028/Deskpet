import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from memory_extractor import MemoryExtractor
from memory_policy import MemoryPolicy
from memory_store import MemoryStore


class MemoryProcessingTests(unittest.TestCase):
    def test_assistant_candidates_are_filtered(self):
        raw = '{"candidates":[{"subject":"assistant","predicate":"is","value":"x","memory_type":"profile","risk_level":"low","confidence":0.9,"evidence_message_id":"a"}]}'
        self.assertEqual(MemoryExtractor.parse_payload(raw), [])

    def test_risk_policy(self):
        high = {"risk_level": "high"}
        self.assertEqual(MemoryPolicy({"memory_mode": "graded"}).decide(high, 99)["action"], "confirm_required")
        self.assertEqual(MemoryPolicy({"memory_mode": "session"}).decide(high, 0)["action"], "ignore")

    def test_delete_removes_episode_recall(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "memory.sqlite3")
            conversation = store.create_conversation()
            store.append_message(conversation, {"id": "u1", "role": "user", "content": "乌龙茶", "timestamp": 1})
            store.add_episode("用户讨论乌龙茶", conversation, "u1")
            self.assertEqual(len(store.search_episodes("乌龙茶")), 1)
            store.clear_memories()
            self.assertEqual(store.search_episodes("乌龙茶"), [])
            store.close()


if __name__ == "__main__":
    unittest.main()
