"""跨进程与内存契约：消息、情绪、记忆候选、宠物命令与 bridge 消息。

本模块只包含数据结构和纯函数校验，不依赖 PyQt、openai 或数据库，
保证可以完全离线单元测试。所有校验函数返回错误字符串列表，空列表表示合法。

RUNTIME_SCHEMA_VERSION 是所有运行时格式（bridge 信封、设置、数据库）的
统一版本号来源，避免各模块各自维护一份容易漂移的版本常量。
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, List, Optional

RUNTIME_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# 时间与标识
# ---------------------------------------------------------------------------


def make_trace_id() -> str:
    """生成短 trace_id，用于从用户消息追踪到宠物反应。"""
    return uuid.uuid4().hex[:12]


def timestamp_now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# 会话消息（持久化契约）
# ---------------------------------------------------------------------------

ROLES = ("user", "assistant", "system")

MESSAGE_FIELDS = (
    "id",
    "conversation_id",
    "role",
    "content",
    "timestamp",
    "context_eligible",
    "stopped",
    "model_used",
    "metadata_json",
)


def validate_message(message: Any) -> List[str]:
    """校验一条待持久化的会话消息。"""
    errors: List[str] = []
    if not isinstance(message, dict):
        return ["message 必须是 dict"]
    if not isinstance(message.get("id"), str) or not message["id"]:
        errors.append("id 缺失或不是字符串")
    if not isinstance(message.get("conversation_id"), str) or not message["conversation_id"]:
        errors.append("conversation_id 缺失或不是字符串")
    if message.get("role") not in ROLES:
        errors.append(f"role 必须是 {ROLES} 之一")
    if not isinstance(message.get("content"), str) or not message["content"].strip():
        errors.append("content 缺失或为空")
    if "timestamp" in message and not isinstance(message["timestamp"], (int, float)):
        errors.append("timestamp 必须是数字")
    if "context_eligible" in message and not isinstance(message["context_eligible"], bool):
        errors.append("context_eligible 必须是布尔值")
    if "stopped" in message and not isinstance(message["stopped"], bool):
        errors.append("stopped 必须是布尔值")
    return errors


# ---------------------------------------------------------------------------
# 情绪结果契约
# ---------------------------------------------------------------------------

USER_EMOTIONS = (
    "neutral",
    "joy",
    "sadness",
    "anger",
    "anxiety",
    "surprise",
    "sleepy",
    "shy",
)

PET_MOODS = (
    "idle",
    "happy",
    "concerned",
    "curious",
    "sleepy",
    "shy",
)

# 聊天等待回复时的过渡状态，不属于稳定宠物情绪，单独列出。
PET_TRANSITION_STATES = ("thinking",)

URGENCY_LEVELS = ("none", "low", "medium", "high", "danger")

EMOTION_RESULT_FIELDS = (
    "schema_version",
    "trace_id",
    "dominant_emotion",
    "intensity",
    "confidence",
    "pet_empathy",
    "urgency",
    "expires_in_seconds",
    "evidence",
)


def validate_emotion_result(result: Any) -> List[str]:
    """校验慢路径情绪识别结果。非法结果必须降级为 neutral，不能阻塞聊天。"""
    errors: List[str] = []
    if not isinstance(result, dict):
        return ["emotion result 必须是 dict"]
    if result.get("dominant_emotion") not in USER_EMOTIONS:
        errors.append(f"dominant_emotion 必须是 {USER_EMOTIONS} 之一")
    if not 0.0 <= float(result.get("intensity", 0.0)) <= 1.0:
        errors.append("intensity 必须在 0..1")
    if not 0.0 <= float(result.get("confidence", 0.0)) <= 1.0:
        errors.append("confidence 必须在 0..1")
    if result.get("pet_empathy") not in PET_MOODS:
        errors.append(f"pet_empathy 必须是 {PET_MOODS} 之一")
    if result.get("urgency") not in URGENCY_LEVELS:
        errors.append(f"urgency 必须是 {URGENCY_LEVELS} 之一")
    return errors


# ---------------------------------------------------------------------------
# 记忆候选契约
# ---------------------------------------------------------------------------

MEMORY_TYPES = ("preference", "profile", "constraint", "episode")
RISK_LEVELS = ("low", "medium", "high")
MEMORY_STATUSES = (
    "candidate",
    "observed",
    "pending",
    "confirmed",
    "rejected",
    "deferred",
    "superseded",
    "deleted",
    "expired",
)

CANDIDATE_FIELDS = (
    "subject",
    "predicate",
    "value",
    "memory_type",
    "risk_level",
    "confidence",
    "evidence_message_id",
    "expires_at",
)


def validate_memory_candidate(candidate: Any) -> List[str]:
    """校验单个记忆候选。缺字段、类型错误即非法，返回空候选而不是落库。"""
    errors: List[str] = []
    if not isinstance(candidate, dict):
        return ["candidate 必须是 dict"]
    for field in ("subject", "predicate", "value"):
        value = candidate.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} 缺失或不是非空字符串")
    if candidate.get("memory_type") not in MEMORY_TYPES:
        errors.append(f"memory_type 必须是 {MEMORY_TYPES} 之一")
    if candidate.get("risk_level") not in RISK_LEVELS:
        errors.append(f"risk_level 必须是 {RISK_LEVELS} 之一")
    confidence = candidate.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
        errors.append("confidence 必须是 0..1 的数字")
    if not isinstance(candidate.get("evidence_message_id"), str) or not candidate["evidence_message_id"]:
        errors.append("evidence_message_id 缺失或不是字符串")
    if "expires_at" in candidate and candidate["expires_at"] is not None:
        if not isinstance(candidate["expires_at"], (int, float)):
            errors.append("expires_at 必须是数字或 null")
    return errors


def validate_candidates_payload(payload: Any) -> List[str]:
    """校验候选提取器返回的完整 JSON，返回首个非法候选对应的错误。"""
    errors: List[str] = []
    if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
        return ["candidates payload 必须是 {\"candidates\": [...]}"]
    for index, candidate in enumerate(payload["candidates"]):
        item_errors = validate_memory_candidate(candidate)
        if item_errors:
            errors.append(f"candidates[{index}]: {'; '.join(item_errors)}")
            break
    return errors


# ---------------------------------------------------------------------------
# 宠物命令（Python → Godot）
# ---------------------------------------------------------------------------

PET_COMMANDS = ("set_state", "show_bubble", "set_activity", "freeze", "move_to", "show_window")
PET_COMMAND_STATES = PET_MOODS + PET_TRANSITION_STATES

COMMAND_FIELDS = ("command", "state", "duration_ms", "trace_id", "expires_at", "text")


def make_pet_command(
    command: str,
    state: Optional[str] = None,
    duration_ms: Optional[int] = None,
    trace_id: Optional[str] = None,
    text: Optional[str] = None,
    expires_at: Optional[float] = None,
) -> dict:
    """构造一条宠物命令。旧命令带过期时间，避免慢结果覆盖新状态。"""
    payload: dict = {"command": command, "trace_id": trace_id or make_trace_id()}
    if state is not None:
        payload["state"] = state
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if text is not None:
        payload["text"] = text
    if expires_at is not None:
        payload["expires_at"] = expires_at
    return payload


def validate_pet_command(command: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(command, dict):
        return ["pet command 必须是 dict"]
    if command.get("command") not in PET_COMMANDS:
        errors.append(f"command 必须是 {PET_COMMANDS} 之一")
    state = command.get("state")
    if state is not None and state not in PET_COMMAND_STATES:
        errors.append(f"state 必须是 {PET_COMMAND_STATES} 之一")
    duration_ms = command.get("duration_ms")
    if duration_ms is not None and (not isinstance(duration_ms, (int, float)) or duration_ms <= 0):
        errors.append("duration_ms 必须是正数或省略")
    return errors


# ---------------------------------------------------------------------------
# 宠物事件（Godot → Python）
# ---------------------------------------------------------------------------

PET_EVENTS = (
    "hello",
    "clicked",
    "double_clicked",
    "hover_start",
    "hover_end",
    "dragged",
    "drag_end",
    "state_changed",
    "activity_started",
    "activity_ended",
    "window_moved",
    "heartbeat",
)

EVENT_FIELDS = ("event", "position", "timestamp", "trace_id", "state")


def validate_pet_event(event: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(event, dict):
        return ["pet event 必须是 dict"]
    if event.get("event") not in PET_EVENTS:
        errors.append(f"event 必须是 {PET_EVENTS} 之一")
    if "timestamp" in event and not isinstance(event["timestamp"], (int, float)):
        errors.append("timestamp 必须是数字")
    return errors


def parse_pet_event(raw: Any) -> Optional[dict]:
    """把 bridge 收到的 payload 解析成 pet event；非法返回 None。"""
    event = raw if isinstance(raw, dict) else None
    if event is None:
        return None
    if validate_pet_event(event):
        return None
    return event


# ---------------------------------------------------------------------------
# bridge 消息信封
# ---------------------------------------------------------------------------

BRIDGE_TYPES = ("pet_command", "pet_event")


def make_bridge_message(msg_type: str, payload: dict, trace_id: Optional[str] = None) -> dict:
    """构造一条 bridge 信封。"""
    return {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "type": msg_type,
        "payload": payload,
        "trace_id": trace_id or make_trace_id(),
        "timestamp": timestamp_now(),
    }


def validate_bridge_message(message: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(message, dict):
        return ["bridge message 必须是 dict"]
    if message.get("schema_version") != RUNTIME_SCHEMA_VERSION:
        errors.append(f"schema_version 必须是 {RUNTIME_SCHEMA_VERSION}")
    if message.get("type") not in BRIDGE_TYPES:
        errors.append(f"type 必须是 {BRIDGE_TYPES} 之一")
    if not isinstance(message.get("trace_id"), str) or not message["trace_id"]:
        errors.append("trace_id 缺失")
    if not isinstance(message.get("timestamp"), (int, float)):
        errors.append("timestamp 缺失或不是数字")
    return errors


def encode_bridge_message(message: dict) -> bytes:
    """序列化为单行 JSON（换行分隔协议）。"""
    return json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def decode_bridge_line(line: bytes) -> Optional[dict]:
    """安全解析一行 JSON；非法输入返回 None 而不是抛异常。"""
    try:
        message = json.loads(line.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if validate_bridge_message(message):
        return None
    return message


# ---------------------------------------------------------------------------
# bridge 网络默认值
# ---------------------------------------------------------------------------

DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 17899
BRIDGE_PORT_FILE = "bridge-port.txt"
