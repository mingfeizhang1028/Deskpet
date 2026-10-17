"""结构化画像和 FTS5 情节检索。"""
import math, time

class MemorySearch:
    def __init__(self, store): self.store = store

    def build_context_hint(self, query=""):
        items = self.store.list_active_memories()
        if not items: return ""
        lines = [f"- {x['predicate']}: {x['value']}" for x in items[:12]]
        return "\n".join(lines)

    def search_episodes(self, query, limit=3):
        rows = self.store.search_episodes(query, limit)
        now = time.time()
        for row in rows:
            age_days = max(0.0, (now - float(row.get("created_at", now))) / 86400)
            row["recency"] = math.exp(-age_days / 30)
            row["source"] = {"conversation_id": row.get("conversation_id"), "message_id": row.get("message_id")}
        return rows

