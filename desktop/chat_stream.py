"""Provider-independent chat streaming helpers."""


MAX_RECENT_MESSAGES = 16
MAX_CONTEXT_CHARACTERS = 12_000


class ChatCancelled(RuntimeError):
    """Raised when the user stops waiting for a chat response."""

    def __init__(self, partial_text=""):
        super().__init__("聊天请求已停止。")
        self.partial_text = partial_text


def _content_text(message):
    content = message.get("content", "") if isinstance(message, dict) else ""
    if isinstance(content, str):
        return content
    return str(content)


def select_recent_messages(
    messages,
    max_messages=MAX_RECENT_MESSAGES,
    max_characters=MAX_CONTEXT_CHARACTERS,
):
    """Keep newest messages within count and character budgets."""
    selected = []
    characters = 0
    for message in reversed(list(messages or [])):
        if not isinstance(message, dict) or message.get("context_eligible", True) is False:
            continue
        if len(selected) >= max_messages:
            break
        size = len(_content_text(message))
        if selected and characters + size > max_characters:
            break
        selected.append(message)
        characters += size
    return list(reversed(selected))


def chat_completion_delta(chunk):
    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return ""
    delta = getattr(choices[0], "delta", None)
    content = getattr(delta, "content", None) if delta is not None else None
    return content if isinstance(content, str) else ""


def responses_delta(event):
    event_type = str(getattr(event, "type", ""))
    if event_type.endswith("output_text.delta"):
        delta = getattr(event, "delta", "")
        return delta if isinstance(delta, str) else ""
    return ""


def extract_delta(event, mode):
    if mode == "chat":
        return chat_completion_delta(event)
    return responses_delta(event)
