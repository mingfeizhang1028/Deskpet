"""本地情绪快路径：规则透明、低延迟，不保存原始文本。"""
from contracts import make_trace_id, timestamp_now

KEYWORDS = {
    "sadness": ("难过", "伤心", "失落", "哭", "不想动", "崩溃"),
    "anger": ("生气", "愤怒", "气死", "烦死", "恼火"),
    "anxiety": ("焦虑", "担心", "害怕", "慌", "紧张", "压力好大"),
    "joy": ("开心", "高兴", "太好了", "顺利", "喜欢", "哈哈"),
    "sleepy": ("困", "好累", "疲惫", "想睡"),
    "surprise": ("没想到", "居然", "震惊", "惊讶"),
}

def detect(text, trace_id=None, generation=0, now=None):
    text = str(text or "")
    scores = {emotion: sum(text.count(word) for word in words) for emotion, words in KEYWORDS.items()}
    dominant, score = max(scores.items(), key=lambda item: item[1], default=("neutral", 0))
    if score <= 0:
        dominant, confidence = "neutral", 0.45
    else:
        confidence = min(0.95, 0.55 + score * 0.12)
    intensity = min(1.0, 0.35 + score * 0.15) if dominant != "neutral" else 0.0
    empathy = "concerned" if dominant in ("sadness", "anger", "anxiety") else "idle"
    urgency = "high" if any(x in text for x in ("自杀", "不想活", "伤害自己")) else ("medium" if dominant in ("anger", "anxiety") else "none")
    return {"schema_version": 1, "trace_id": trace_id or make_trace_id(), "generation": generation,
            "dominant_emotion": dominant, "intensity": intensity, "confidence": confidence,
            "pet_empathy": empathy, "urgency": urgency, "expires_in_seconds": 45,
            "evidence": "keyword"}

