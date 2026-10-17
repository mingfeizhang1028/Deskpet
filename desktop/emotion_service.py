"""快路径 + 可取消的慢路径；旧代次结果不会覆盖新消息。"""
import threading
from concurrent.futures import ThreadPoolExecutor
from contracts import validate_emotion_result
from emotion_rules import detect

class EmotionService:
    def __init__(self, slow_detector=None, max_workers=1):
        self.slow_detector = slow_detector
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="emotion")
        self._lock = threading.Lock()
        self._latest_generation = 0

    def fast(self, text, trace_id=None, generation=0):
        with self._lock: self._latest_generation = max(self._latest_generation, generation)
        return detect(text, trace_id, generation)

    def slow(self, text, trace_id, generation, callback):
        if not self.slow_detector: return None
        def run():
            try:
                result = self.slow_detector(text, trace_id, generation)
                if validate_emotion_result(result): return
                with self._lock:
                    if generation != self._latest_generation: return
                callback(result)
            except Exception:
                return
        return self.executor.submit(run)

    def close(self): self.executor.shutdown(wait=False, cancel_futures=True)

