import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "desktop"))

from focus_session import FocusSession  # noqa: E402


class FocusSessionTests(unittest.TestCase):
    def test_default_duration_and_bounds(self):
        session = FocusSession.start(now=100)
        self.assertEqual(session.duration_minutes, 12)
        self.assertEqual(session.remaining_seconds, 720)
        with self.assertRaises(ValueError):
            FocusSession.start(duration_minutes=0, now=100)
        with self.assertRaises(ValueError):
            FocusSession.start(duration_minutes=121, now=100)

    def test_pause_resume_preserves_remaining_time(self):
        session = FocusSession.start(duration_minutes=12, now=100)
        self.assertTrue(session.pause(now=250))
        self.assertEqual(session.status, FocusSession.PAUSED)
        self.assertEqual(session.remaining_seconds, 570)
        self.assertTrue(session.resume(now=500))
        session.refresh(now=620)
        self.assertEqual(session.remaining_seconds, 450)

    def test_expiry_and_early_finish_are_explicit(self):
        expired = FocusSession.start(duration_minutes=5, now=100)
        self.assertTrue(expired.refresh(now=400))
        self.assertEqual(expired.status, FocusSession.COMPLETED)
        self.assertEqual(expired.finished_reason, "expired")

        early = FocusSession.start(duration_minutes=5, now=100)
        self.assertTrue(early.finish(now=140, reason="manual"))
        self.assertEqual(early.finished_reason, "manual")
        self.assertEqual(early.status, FocusSession.COMPLETED)

    def test_reminder_levels_match_approved_rules(self):
        self.assertEqual(FocusSession.start(10, reminder_level=1, now=0).reminder_offsets(), [])
        self.assertEqual(FocusSession.start(10, reminder_level=2, now=0).reminder_offsets(), [300])
        self.assertEqual(FocusSession.start(10, reminder_level=3, now=0).reminder_offsets(), [300, 480])
        self.assertEqual(FocusSession.start(10, reminder_level=4, now=0).reminder_offsets(), [150, 300, 450])
        self.assertEqual(FocusSession.start(10, reminder_level=5, now=0).reminder_offsets(), [300])
        self.assertEqual(FocusSession.start(14, reminder_level=5, now=0).reminder_offsets(), [300, 600])

    def test_due_reminders_are_not_repeated(self):
        session = FocusSession.start(25, reminder_level=4, now=0)
        self.assertEqual(session.due_reminders(now=400), [375])
        self.assertEqual(session.due_reminders(now=401), [])
        saved = session.to_dict()
        restored = FocusSession.from_dict(saved, now=401)
        self.assertEqual(restored.due_reminders(now=500), [])

    def test_running_state_can_be_recovered_from_deadline(self):
        session = FocusSession.start(12, task="方案", now=100)
        restored = FocusSession.from_dict(session.to_dict(), now=200)
        self.assertEqual(restored.status, FocusSession.RUNNING)
        restored.refresh(now=300)
        self.assertEqual(restored.remaining_seconds, 520)

    def test_expired_recovery_and_malformed_state_are_safe(self):
        session = FocusSession.start(5, now=100)
        restored = FocusSession.from_dict(session.to_dict(), now=500)
        self.assertTrue(restored.refresh(now=500))
        self.assertEqual(restored.finished_reason, "expired")
        with self.assertRaises(ValueError):
            FocusSession.from_dict({"duration_seconds": "broken"}, now=500)

    def test_quiet_mode_only_suppresses_mid_session_reminders(self):
        self.assertFalse(FocusSession.should_present_reminder(quiet=True))
        self.assertTrue(FocusSession.should_present_reminder(quiet=False))
        self.assertTrue(FocusSession.should_present_reminder(quiet=True, final=True))


if __name__ == "__main__":
    unittest.main()
