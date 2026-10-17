"""可测试的记忆风险与候选状态策略。"""

class MemoryPolicy:
    THRESHOLDS = {"low": 2, "medium": 3, "high": 1}

    def __init__(self, settings=None):
        self.settings = settings or {}

    def decide(self, candidate, observations=0, settings=None):
        settings = settings or self.settings
        if settings.get("memory_mode", "graded") == "session":
            return {"action": "ignore", "reason": "session mode", "next_threshold": None}
        risk = candidate.get("risk_level")
        if risk == "high":
            return {"action": "confirm_required", "reason": "high risk requires explicit confirmation", "next_threshold": 1}
        threshold = self.THRESHOLDS.get(risk, 3)
        if observations + 1 < threshold:
            return {"action": "observe", "reason": f"needs {threshold} observations", "next_threshold": threshold}
        if risk == "low" and settings.get("low_risk_learning", "confirm") == "auto":
            return {"action": "confirm", "reason": "low risk threshold reached", "next_threshold": threshold}
        return {"action": "queue_confirmation", "reason": f"{risk} risk requires confirmation", "next_threshold": threshold}

