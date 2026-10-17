import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from emotion_policy import map_to_pet
from emotion_rules import detect
from emotion_service import EmotionService

class EmotionProcessingTests(unittest.TestCase):
    def test_fast_path_is_local_and_traceable(self):
        result = detect("我有点焦虑，最近压力好大", trace_id="t1", generation=2)
        self.assertEqual(result["trace_id"], "t1")
        self.assertEqual(result["dominant_emotion"], "anxiety")
        self.assertEqual(map_to_pet(result)["pet_mood"], "concerned")

    def test_low_confidence_is_neutral(self):
        result = detect("你好", trace_id="t2")
        result["confidence"] = 0.2
        self.assertEqual(map_to_pet(result)["pet_mood"], "idle")

    def test_old_slow_result_is_dropped(self):
        received = []
        service = EmotionService(lambda text, trace, generation: detect("开心", trace, generation))
        service.fast("第一条", generation=1)
        service.fast("第二条", generation=2)
        service.slow("第一条", "old", 1, received.append)
        service.slow("第二条", "new", 2, received.append).result(timeout=2)
        self.assertTrue(all(item["trace_id"] == "new" for item in received))
        service.close()
