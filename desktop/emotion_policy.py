"""用户情绪到宠物反应的克制映射。"""
from contracts import validate_emotion_result

def map_to_pet(result, quiet=False):
    if quiet or validate_emotion_result(result):
        return {"pet_mood": "sleepy" if quiet else "idle", "bubble": None, "suppressed": True}
    if result.get("confidence", 0) < 0.6:
        return {"pet_mood": "idle", "bubble": None, "suppressed": True}
    emotion = result["dominant_emotion"]
    if emotion in ("sadness", "anxiety"):
        return {"pet_mood": "concerned", "bubble": "我在这里，先不用急着解决全部。", "suppressed": False}
    if emotion == "anger":
        return {"pet_mood": "concerned", "bubble": "听起来这件事真的很让人烦，我先陪你缓一缓。", "suppressed": False}
    if emotion == "joy":
        return {"pet_mood": "happy", "bubble": None, "suppressed": False}
    if emotion == "sleepy":
        return {"pet_mood": "sleepy", "bubble": None, "suppressed": False}
    return {"pet_mood": "idle", "bubble": None, "suppressed": True}

