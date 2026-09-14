"""UI-independent focus session state and reminder rules."""

import math
import time


class FocusSession:
    """A single user-started focus session with deterministic time handling."""

    MINUTES_MIN = 1
    MINUTES_MAX = 120
    DEFAULT_MINUTES = 12
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"

    def __init__(
        self,
        duration_minutes=DEFAULT_MINUTES,
        task="",
        next_step="",
        reminder_level=2,
        now=None,
        status=RUNNING,
        started_at=None,
        deadline=None,
        remaining_seconds=None,
        reminders_sent=None,
        finished_reason=None,
    ):
        duration_minutes = int(duration_minutes)
        if not self.MINUTES_MIN <= duration_minutes <= self.MINUTES_MAX:
            raise ValueError("专注时长必须在 1 到 120 分钟之间。")
        reminder_level = max(1, min(5, int(reminder_level)))
        self.duration_seconds = duration_minutes * 60
        self.task = str(task or "")
        self.next_step = str(next_step or "")
        self.reminder_level = reminder_level
        self.status = status if status in {self.RUNNING, self.PAUSED, self.COMPLETED} else self.COMPLETED
        current = time.time() if now is None else float(now)
        self.started_at = current if started_at is None else float(started_at)
        self.deadline = None if deadline is None else float(deadline)
        if remaining_seconds is None:
            remaining_seconds = self.duration_seconds
        self.remaining_seconds = max(0, int(remaining_seconds))
        self.reminders_sent = {int(value) for value in (reminders_sent or [])}
        self.finished_reason = finished_reason
        if self.status == self.RUNNING and self.deadline is None:
            self.deadline = current + self.remaining_seconds

    @classmethod
    def start(cls, duration_minutes=DEFAULT_MINUTES, task="", next_step="", reminder_level=2, now=None):
        current = time.time() if now is None else float(now)
        return cls(
            duration_minutes=duration_minutes,
            task=task,
            next_step=next_step,
            reminder_level=reminder_level,
            now=current,
            started_at=current,
            deadline=current + int(duration_minutes) * 60,
            remaining_seconds=int(duration_minutes) * 60,
            status=cls.RUNNING,
        )

    @classmethod
    def from_dict(cls, data, now=None):
        if not isinstance(data, dict):
            raise ValueError("专注状态不是对象。")
        duration_seconds = int(data.get("duration_seconds", 0))
        if duration_seconds <= 0 or duration_seconds % 60:
            raise ValueError("专注时长状态无效。")
        return cls(
            duration_minutes=duration_seconds // 60,
            task=data.get("task", ""),
            next_step=data.get("next_step", ""),
            reminder_level=data.get("reminder_level", 2),
            now=now,
            status=data.get("status", cls.COMPLETED),
            started_at=data.get("started_at"),
            deadline=data.get("deadline"),
            remaining_seconds=data.get("remaining_seconds", duration_seconds),
            reminders_sent=data.get("reminders_sent", []),
            finished_reason=data.get("finished_reason"),
        )

    @property
    def duration_minutes(self):
        return self.duration_seconds // 60

    @property
    def elapsed_seconds(self):
        return max(0, self.duration_seconds - self.remaining_seconds)

    @property
    def is_active(self):
        return self.status in {self.RUNNING, self.PAUSED}

    def refresh(self, now=None):
        """Update remaining time and return whether the session just expired."""
        if self.status != self.RUNNING:
            return False
        current = time.time() if now is None else float(now)
        remaining = max(0, self.deadline - current)
        self.remaining_seconds = int(math.ceil(remaining))
        if remaining <= 0:
            self.status = self.COMPLETED
            self.finished_reason = self.finished_reason or "expired"
            self.deadline = None
            self.remaining_seconds = 0
            return True
        return False

    def pause(self, now=None):
        self.refresh(now)
        if self.status != self.RUNNING:
            return False
        self.status = self.PAUSED
        self.deadline = None
        return True

    def resume(self, now=None):
        if self.status != self.PAUSED or self.remaining_seconds <= 0:
            return False
        current = time.time() if now is None else float(now)
        self.status = self.RUNNING
        self.deadline = current + self.remaining_seconds
        return True

    def finish(self, now=None, reason="manual"):
        self.refresh(now)
        if self.status == self.COMPLETED:
            return False
        self.status = self.COMPLETED
        self.finished_reason = reason
        self.deadline = None
        return True

    def reminder_offsets(self):
        total = self.duration_seconds
        level = self.reminder_level
        if level == 1:
            offsets = []
        elif level == 2:
            offsets = [total // 2]
        elif level == 3:
            offsets = [total // 2, total - 120]
        elif level == 4:
            offsets = [total // 4, total // 2, (total * 3) // 4]
        else:
            offsets = list(range(300, total, 300))
            if total < 15 * 60:
                offsets = offsets[:2]
        return sorted({offset for offset in offsets if 0 < offset < total})

    def due_reminders(self, now=None):
        self.refresh(now)
        elapsed = self.duration_seconds - self.remaining_seconds
        due = [offset for offset in self.reminder_offsets() if offset <= elapsed and offset not in self.reminders_sent]
        self.reminders_sent.update(due)
        return due

    @staticmethod
    def should_present_reminder(quiet, final=False):
        return bool(final or not quiet)

    def to_dict(self):
        return {
            "version": 1,
            "duration_seconds": self.duration_seconds,
            "task": self.task,
            "next_step": self.next_step,
            "reminder_level": self.reminder_level,
            "status": self.status,
            "started_at": self.started_at,
            "deadline": self.deadline,
            "remaining_seconds": self.remaining_seconds,
            "reminders_sent": sorted(self.reminders_sent),
            "finished_reason": self.finished_reason,
        }
