"""候选提取：模型失败时安全返回空列表，也支持离线固定候选测试。"""
import json
from contracts import validate_candidates_payload

class MemoryExtractor:
    def __init__(self, client=None): self.client = client

    @staticmethod
    def parse_payload(raw):
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if validate_candidates_payload(payload): return []
        return [c for c in payload["candidates"] if c.get("subject") == "user"]

    def extract(self, messages):
        if not self.client or not getattr(self.client, "configured", False): return []
        try:
            raw = self.client.chat([{"role":"user", "content": "仅输出候选 JSON：" + json.dumps(messages, ensure_ascii=False)}])
            return self.parse_payload(raw)
        except Exception:
            return []

