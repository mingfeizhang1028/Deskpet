import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "desktop"))

from contracts import (  # noqa: E402
    PET_COMMAND_STATES,
    PET_COMMANDS,
    PET_EVENTS,
    RUNTIME_SCHEMA_VERSION,
    USER_EMOTIONS,
    decode_bridge_line,
    encode_bridge_message,
    make_bridge_message,
    make_pet_command,
    make_trace_id,
    validate_bridge_message,
    validate_candidates_payload,
    validate_emotion_result,
    validate_memory_candidate,
    validate_message,
    validate_pet_command,
    validate_pet_event,
)


class MessageContractTests(unittest.TestCase):
    def test_valid_message_passes(self):
        message = {
            "id": "msg_1",
            "conversation_id": "conv_1",
            "role": "user",
            "content": "我喜欢乌龙茶",
            "timestamp": 100.0,
            "context_eligible": True,
            "stopped": False,
        }
        self.assertEqual(validate_message(message), [])

    def test_stopped_partial_message_is_still_structured(self):
        message = {
            "id": "msg_2",
            "conversation_id": "conv_1",
            "role": "assistant",
            "content": "半段",
            "timestamp": 100.0,
            "context_eligible": False,
            "stopped": True,
        }
        self.assertEqual(validate_message(message), [])

    def test_invalid_role_and_empty_content_rejected(self):
        errors = validate_message({"id": "m", "conversation_id": "c", "role": "pet", "content": ""})
        self.assertTrue(any("role" in error for error in errors))
        self.assertTrue(any("content" in error for error in errors))

    def test_non_dict_rejected(self):
        self.assertNotEqual(validate_message("not-a-dict"), [])


class EmotionContractTests(unittest.TestCase):
    def test_valid_slow_result_passes(self):
        result = {
            "schema_version": 1,
            "trace_id": "abc",
            "dominant_emotion": "sadness",
            "intensity": 0.72,
            "confidence": 0.84,
            "pet_empathy": "concerned",
            "urgency": "none",
            "expires_in_seconds": 1800,
            "evidence": [],
        }
        self.assertEqual(validate_emotion_result(result), [])

    def test_unknown_emotion_and_bad_confidence_rejected(self):
        errors = validate_emotion_result(
            {"dominant_emotion": "sad", "intensity": 0.5, "confidence": 2.0, "pet_empathy": "sad"}
        )
        self.assertTrue(any("dominant_emotion" in error for error in errors))
        self.assertTrue(any("confidence" in error for error in errors))

    def test_emotion_sets_are_stable(self):
        self.assertEqual(
            USER_EMOTIONS,
            ("neutral", "joy", "sadness", "anger", "anxiety", "surprise", "sleepy", "shy"),
        )
        self.assertEqual(
            PET_COMMAND_STATES[:6], ("idle", "happy", "concerned", "curious", "sleepy", "shy")
        )


class MemoryCandidateContractTests(unittest.TestCase):
    def test_valid_low_risk_candidate_passes(self):
        candidate = {
            "subject": "user",
            "predicate": "prefers",
            "value": "晚上工作",
            "memory_type": "preference",
            "risk_level": "low",
            "confidence": 0.86,
            "evidence_message_id": "msg_123",
            "expires_at": None,
        }
        self.assertEqual(validate_memory_candidate(candidate), [])
        self.assertEqual(validate_candidates_payload({"candidates": [candidate]}), [])

    def test_missing_evidence_and_bad_risk_rejected(self):
        candidate = {
            "subject": "user",
            "predicate": "prefers",
            "value": "晚上工作",
            "memory_type": "preference",
            "risk_level": "extreme",
            "confidence": 0.9,
        }
        errors = validate_memory_candidate(candidate)
        self.assertTrue(any("risk_level" in error for error in errors))
        self.assertTrue(any("evidence_message_id" in error for error in errors))

    def test_payload_with_first_invalid_candidate_reports_that_index(self):
        errors = validate_candidates_payload({"candidates": [{"bad": True}]})
        self.assertTrue(any("candidates[0]" in error for error in errors))

    def test_non_candidates_payload_rejected(self):
        self.assertNotEqual(validate_candidates_payload({"items": []}), [])


class PetCommandContractTests(unittest.TestCase):
    def test_valid_set_state_command(self):
        command = make_pet_command("set_state", state="concerned", duration_ms=3000)
        self.assertEqual(validate_pet_command(command), [])
        self.assertEqual(command["state"], "concerned")
        self.assertIn("trace_id", command)

    def test_invalid_command_and_state_rejected(self):
        errors = validate_pet_command({"command": "fly", "state": "sad"})
        self.assertTrue(any("command" in error for error in errors))
        self.assertTrue(any("state" in error for error in errors))


class PetEventContractTests(unittest.TestCase):
    def test_valid_event_passes(self):
        event = {"event": "clicked", "position": {"x": 100, "y": 200}, "timestamp": 100.0}
        self.assertEqual(validate_pet_event(event), [])
        self.assertIsNotNone(validate_pet_event({"event": "hello"}))

    def test_unknown_event_rejected(self):
        self.assertNotEqual(validate_pet_event({"event": "warp"}), [])


class BridgeEnvelopeTests(unittest.TestCase):
    def test_envelope_roundtrip_preserves_fields(self):
        command = make_pet_command("set_state", state="happy", duration_ms=1000)
        message = make_bridge_message("pet_command", command)
        self.assertEqual(validate_bridge_message(message), [])
        decoded = decode_bridge_line(encode_bridge_message(message))
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["payload"]["state"], "happy")
        self.assertEqual(decoded["trace_id"], message["trace_id"])

    def test_wrong_schema_version_rejected(self):
        message = make_bridge_message("pet_command", {"command": "set_state"})
        message["schema_version"] = RUNTIME_SCHEMA_VERSION + 1
        self.assertNotEqual(validate_bridge_message(message), [])
        self.assertIsNone(decode_bridge_line(b"not json\n"))

    def test_trace_id_is_unique(self):
        self.assertNotEqual(make_trace_id(), make_trace_id())

    def test_pet_sets_are_complete(self):
        self.assertIn("set_state", PET_COMMANDS)
        self.assertIn("clicked", PET_EVENTS)


if __name__ == "__main__":
    unittest.main()
