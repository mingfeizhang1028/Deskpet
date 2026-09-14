import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "desktop"))

from chat_stream import (  # noqa: E402
    MAX_CONTEXT_CHARACTERS,
    ChatCancelled,
    extract_delta,
    select_recent_messages,
)


class ChatStreamTests(unittest.TestCase):
    def test_chat_completion_and_responses_deltas_are_normalized(self):
        chat_event = SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="你好"))]
        )
        response_event = SimpleNamespace(type="response.output_text.delta", delta="，芽砚")
        self.assertEqual(extract_delta(chat_event, "chat"), "你好")
        self.assertEqual(extract_delta(response_event, "responses"), "，芽砚")
        self.assertEqual(extract_delta(SimpleNamespace(type="response.completed"), "responses"), "")

    def test_recent_messages_respect_count_and_character_budget(self):
        messages = [
            {"role": "user", "content": "旧"},
            {"role": "assistant", "content": "x" * (MAX_CONTEXT_CHARACTERS + 10)},
            {"role": "user", "content": "当前问题"},
        ]
        selected = select_recent_messages(messages, max_messages=16)
        self.assertEqual(selected[-1]["content"], "当前问题")
        self.assertLessEqual(
            sum(len(str(item["content"])) for item in selected), MAX_CONTEXT_CHARACTERS + len("当前问题")
        )

    def test_recent_messages_ignore_cancelled_partial_turns(self):
        messages = [
            {"role": "user", "content": "问题"},
            {"role": "assistant", "content": "半段", "context_eligible": False},
            {"role": "user", "content": "新问题"},
        ]
        selected = select_recent_messages(messages)
        self.assertEqual([item["content"] for item in selected], ["问题", "新问题"])

    def test_cancelled_request_preserves_partial_text_without_completion(self):
        cancelled = ChatCancelled("已经收到一半")
        self.assertEqual(cancelled.partial_text, "已经收到一半")
        self.assertIn("停止", str(cancelled))


if __name__ == "__main__":
    unittest.main()
