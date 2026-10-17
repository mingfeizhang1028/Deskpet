from contracts import make_trace_id

class ConversationManager:
    def __init__(self, store, settings=None):
        self.store, self.settings = store, settings or {}
        self.conversation_id = None

    def restore_or_create(self):
        rows = self.store.list_conversations(1)
        self.conversation_id = rows[0]["id"] if rows else self.store.create_conversation("芽砚对话", self.settings)
        return self.conversation_id

    def append(self, role, content, context_eligible=True, stopped=False, model_used=None):
        message = {"id": make_trace_id(), "role": role, "content": content, "timestamp": __import__('time').time(), "context_eligible": context_eligible, "stopped": stopped, "model_used": model_used}
        self.store.append_message(self.conversation_id, message)
        return message

    def recent(self, limit=16): return self.store.get_recent_messages(self.conversation_id, limit)

