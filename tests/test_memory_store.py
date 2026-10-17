import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "desktop"))

from memory_store import (  # noqa: E402
    SCHEMA_VERSION,
    DatabaseUnavailable,
    MemoryStore,
    MigrationError,
)


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "memory.sqlite3"

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_database_auto_migrates_to_current_version(self):
        store = MemoryStore(self.db_path)
        try:
            self.assertEqual(store.schema_version(), SCHEMA_VERSION)
            self.assertTrue(store.integrity_ok())
        finally:
            store.close()
        self.assertTrue(self.db_path.exists())

    def test_reopen_does_not_remigrate_and_keeps_version(self):
        first = MemoryStore(self.db_path)
        first.close()
        backups_after_first = list(self.db_path.parent.glob(self.db_path.name + ".bak-v*"))
        self.assertEqual(len(backups_after_first), 1)  # 初次迁移产生一份备份
        store = MemoryStore(self.db_path)
        try:
            self.assertEqual(store.schema_version(), SCHEMA_VERSION)
        finally:
            store.close()
        backups_after_reopen = list(self.db_path.parent.glob(self.db_path.name + ".bak-v*"))
        self.assertEqual(len(backups_after_reopen), len(backups_after_first))  # 重开不再备份

    def test_meta_table_created(self):
        store = MemoryStore(self.db_path)
        try:
            with store._conn:
                row = store._conn.execute("SELECT value FROM meta WHERE key='app_version'").fetchone()
            self.assertIsNotNone(row)
        finally:
            store.close()

    def test_future_schema_version_is_not_silently_overwritten(self):
        store = MemoryStore(self.db_path)
        try:
            with store._conn:
                store._conn.execute("PRAGMA user_version = 999")
            with self.assertRaises(MigrationError):
                MemoryStore(self.db_path)
        finally:
            store.close()

    def test_corrupt_file_surfaces_as_unavailable(self):
        self.db_path.write_bytes(b"this is not a sqlite database at all")
        with self.assertRaises(DatabaseUnavailable):
            MemoryStore(self.db_path)

    def test_corrupt_header_is_detected_as_unavailable(self):
        # 篡改 SQLite 头部声明的页数：连接层面即可发现损坏，
        # 正确路径是抛 DatabaseUnavailable 降级到 session 模式，并保留原文件。
        MemoryStore(self.db_path).close()
        raw = bytearray(self.db_path.read_bytes())
        raw[28:32] = (0x40000000).to_bytes(4, "big")
        self.db_path.write_bytes(raw)
        with self.assertRaises(DatabaseUnavailable):
            MemoryStore(self.db_path)
        self.assertTrue(self.db_path.exists())  # 原文件保留，供恢复提示使用


if __name__ == "__main__":
    unittest.main()
