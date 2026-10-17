"""SQLite 存储：连接、迁移框架与损坏保护。

步骤 1 只提供运行框架：
- 统一连接参数（WAL、外键、busy timeout）；
- schema 版本使用 PRAGMA user_version，由 MIGRATIONS 字典驱动；
- 每次迁移前备份原数据库到 .bak-v<version>；
- 数据库版本高于程序支持时明确报错，绝不静默覆盖；
- 数据库损坏或无法打开时抛出 DatabaseUnavailable，由调用方降级为 session 模式。

步骤 2 增加会话、候选、画像、情节、审计和 FTS5 索引。
"""

from __future__ import annotations

import shutil
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

SCHEMA_VERSION = 2
BUSY_TIMEOUT_SECONDS = 5.0
BACKUP_SUFFIX_TEMPLATE = ".bak-v{version}"


class DatabaseUnavailable(RuntimeError):
    """数据库无法打开、被占用或损坏。调用方应降级运行，不阻塞聊天。"""


class MigrationError(RuntimeError):
    """迁移失败或版本冲突。"""


def _migration_1(conn: sqlite3.Connection) -> None:
    """初始化：meta 表记录应用与运行时版本。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('app_version', 'step1-runtime-skeleton')")


def _migration_2(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at REAL NOT NULL,
            updated_at REAL NOT NULL, archived INTEGER NOT NULL DEFAULT 0,
            deleted_at REAL, settings_snapshot TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
            content TEXT NOT NULL, timestamp REAL NOT NULL,
            context_eligible INTEGER NOT NULL DEFAULT 1, stopped INTEGER NOT NULL DEFAULT 0,
            model_used TEXT, metadata_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );
        CREATE TABLE IF NOT EXISTS memory_items (
            id TEXT PRIMARY KEY, memory_type TEXT NOT NULL, subject TEXT NOT NULL,
            predicate TEXT NOT NULL, value TEXT NOT NULL, risk_level TEXT NOT NULL,
            confidence REAL NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL DEFAULT 'user',
            source_message_id TEXT, source_conversation_id TEXT, created_at REAL NOT NULL,
            last_seen_at REAL NOT NULL, expires_at REAL, supersedes_id TEXT,
            user_confirmed INTEGER NOT NULL DEFAULT 0, deleted_at REAL,
            FOREIGN KEY(source_message_id) REFERENCES messages(id),
            FOREIGN KEY(source_conversation_id) REFERENCES conversations(id)
        );
        CREATE TABLE IF NOT EXISTS memory_observations (
            id TEXT PRIMARY KEY, memory_key TEXT NOT NULL, source_message_id TEXT NOT NULL,
            observed_value TEXT NOT NULL, confidence REAL NOT NULL, observed_at REAL NOT NULL,
            FOREIGN KEY(source_message_id) REFERENCES messages(id)
        );
        CREATE TABLE IF NOT EXISTS memory_actions (
            id TEXT PRIMARY KEY, memory_id TEXT, action TEXT NOT NULL, actor TEXT NOT NULL,
            reason TEXT, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS episodes (
            id TEXT PRIMARY KEY, conversation_id TEXT, message_id TEXT, text TEXT NOT NULL,
            importance REAL NOT NULL DEFAULT 0.5, created_at REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            FOREIGN KEY(conversation_id) REFERENCES conversations(id),
            FOREIGN KEY(message_id) REFERENCES messages(id)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS episode_fts USING fts5(text, content='episodes', content_rowid='rowid');
        CREATE INDEX IF NOT EXISTS idx_memory_status ON memory_items(status);
        CREATE INDEX IF NOT EXISTS idx_memory_key ON memory_observations(memory_key);
        CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, timestamp);
        CREATE VIEW IF NOT EXISTS profile AS SELECT * FROM memory_items WHERE status IN ('confirmed','observed');
        CREATE VIEW IF NOT EXISTS candidate AS SELECT * FROM memory_items WHERE status IN ('candidate','pending','deferred');
        CREATE VIEW IF NOT EXISTS action AS SELECT * FROM memory_actions;
        CREATE VIEW IF NOT EXISTS episode AS SELECT * FROM episodes;
        """
    )


# 每个迁移都是纯 SQLite 事务函数，失败时整体回滚。
MIGRATIONS: Dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migration_1,
    2: _migration_2,
}


class MemoryStore:
    """SQLite 连接的持有者与迁移执行器。所有方法可被多线程安全调用。"""

    def __init__(self, db_path, busy_timeout: float = BUSY_TIMEOUT_SECONDS):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(str(self.db_path), timeout=busy_timeout)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout * 1000)}")
            self._migrate()
        except sqlite3.Error as error:
            self._release_connection()
            raise DatabaseUnavailable(f"数据库无法打开：{type(error).__name__}") from error
        except MigrationError:
            self._release_connection()
            raise

    def _release_connection(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None

    # ------------------------------------------------------------------
    # 连接属性
    # ------------------------------------------------------------------

    def _journal_mode(self) -> str:
        row = self._conn.execute("PRAGMA journal_mode").fetchone()
        return str(row[0]) if row else ""

    def schema_version(self) -> int:
        with self._lock:
            return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    def integrity_ok(self) -> bool:
        """快速完整性检查；大库用 quick_check 而不是全量 integrity_check。"""
        with self._lock:
            row = self._conn.execute("PRAGMA quick_check").fetchone()
            return bool(row) and str(row[0]) == "ok"

    # ------------------------------------------------------------------
    # 迁移
    # ------------------------------------------------------------------

    def _current_version(self) -> int:
        return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    def _backup(self, target_version: int) -> Path:
        backup_path = self.db_path.with_name(
            self.db_path.name + BACKUP_SUFFIX_TEMPLATE.format(version=target_version)
        )
        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def _migrate(self) -> None:
        with self._lock:
            current = self._current_version()
            if current > SCHEMA_VERSION:
                raise MigrationError(
                    f"数据库版本 {current} 高于程序支持的 {SCHEMA_VERSION}，"
                    "已保留原文件，拒绝静默覆盖。"
                )
            if current == SCHEMA_VERSION:
                return
            for version in range(current + 1, SCHEMA_VERSION + 1):
                if version not in MIGRATIONS:
                    raise MigrationError(f"缺少迁移脚本 v{version}")
                # A new database has no user data; keep the historical single
                # bootstrap backup while avoiding one backup per bootstrap step.
                backup_path = self._backup(version) if (current > 0 or version == current + 1) and not (current == 0 and version > 1) else self.db_path
                try:
                    self._conn.execute("BEGIN")
                    MIGRATIONS[version](self._conn)
                    self._conn.execute(f"PRAGMA user_version = {version}")
                    self._conn.commit()
                except Exception:
                    try:
                        self._conn.rollback()
                    except sqlite3.Error:
                        pass
                    raise MigrationError(f"迁移到 v{version} 失败，备份已保留在 {backup_path}")
        # 打开 WAL 放在迁移之后，避免旧版本数据库以 WAL 模式被低版本程序误读。
        with self._lock:
            self._conn.execute("PRAGMA journal_mode = WAL")

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except sqlite3.Error:
                    pass
                self._conn = None

    def _execute(self, sql, args=(), commit=True):
        with self._lock:
            cur = self._conn.execute(sql, args)
            if commit:
                self._conn.commit()
            return cur

    def create_conversation(self, title="新对话", settings_snapshot=None, conversation_id=None, now=None):
        import json, time, uuid
        now = time.time() if now is None else now
        cid = conversation_id or uuid.uuid4().hex
        self._execute("INSERT INTO conversations(id,title,created_at,updated_at,settings_snapshot) VALUES(?,?,?,?,?)",
                      (cid, title or "新对话", now, now, json.dumps(settings_snapshot or {}, ensure_ascii=False)))
        return cid

    def list_conversations(self, limit=20):
        rows = self._execute("SELECT * FROM conversations WHERE deleted_at IS NULL ORDER BY updated_at DESC LIMIT ?", (int(limit),), False).fetchall()
        return [dict(r) for r in rows]

    def append_message(self, conversation_id, message):
        import json, time
        now = float(message.get("timestamp", time.time()))
        self._execute("INSERT OR REPLACE INTO messages(id,conversation_id,role,content,timestamp,context_eligible,stopped,model_used,metadata_json) VALUES(?,?,?,?,?,?,?,?,?)",
                      (message["id"], conversation_id, message["role"], message["content"], now,
                       int(message.get("context_eligible", True)), int(message.get("stopped", False)),
                       message.get("model_used"), json.dumps(message.get("metadata", {}), ensure_ascii=False)))
        self._execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))

    def get_recent_messages(self, conversation_id, limit=16):
        rows = self._execute("SELECT * FROM messages WHERE conversation_id=? AND context_eligible=1 ORDER BY timestamp DESC LIMIT ?", (conversation_id, int(limit)), False).fetchall()
        return [dict(r) for r in reversed(rows)]

    def create_candidate(self, candidate, conversation_id=None, status="candidate", now=None):
        import time, uuid
        now = time.time() if now is None else now
        mid = candidate.get("id") or uuid.uuid4().hex
        self._execute("INSERT INTO memory_items(id,memory_type,subject,predicate,value,risk_level,confidence,status,source_message_id,source_conversation_id,created_at,last_seen_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid, candidate["memory_type"], candidate["subject"], candidate["predicate"], candidate["value"], candidate["risk_level"], float(candidate["confidence"]), status, candidate.get("evidence_message_id"), conversation_id, now, now, candidate.get("expires_at")))
        return mid

    def observation_count(self, subject, predicate, value):
        row = self._execute("SELECT COUNT(*) FROM memory_observations WHERE memory_key=? AND observed_value=?", (f"{subject}:{predicate}", value), False).fetchone()
        return int(row[0])

    def upsert_observation(self, observation):
        import time, uuid
        self._execute("INSERT INTO memory_observations(id,memory_key,source_message_id,observed_value,confidence,observed_at) VALUES(?,?,?,?,?,?)",
            (uuid.uuid4().hex, f"{observation['subject']}:{observation['predicate']}", observation["evidence_message_id"], observation["value"], float(observation["confidence"]), observation.get("observed_at", time.time())))
        return self.observation_count(observation["subject"], observation["predicate"], observation["value"])

    def list_active_memories(self, filters=None):
        where = ["status IN ('confirmed','observed')", "(expires_at IS NULL OR expires_at > ?)"]
        args = [__import__('time').time()]
        for key in ("memory_type", "risk_level"):
            if filters and filters.get(key): where.append(key + "=?"); args.append(filters[key])
        rows = self._execute("SELECT * FROM memory_items WHERE " + " AND ".join(where) + " ORDER BY last_seen_at DESC", args, False).fetchall()
        return [dict(r) for r in rows]

    def transition_memory(self, memory_id, status, actor="user", reason=None):
        import time, uuid
        self._execute("UPDATE memory_items SET status=?, user_confirmed=?, deleted_at=? WHERE id=?", (status, int(status == 'confirmed'), time.time() if status == 'deleted' else None, memory_id))
        self._execute("INSERT INTO memory_actions(id,memory_id,action,actor,reason,created_at) VALUES(?,?,?,?,?,?)", (uuid.uuid4().hex, memory_id, status, actor, reason, time.time()))

    def confirm_memory(self, memory_id, actor="user"): self.transition_memory(memory_id, "confirmed", actor)
    def reject_memory(self, memory_id, actor="user"): self.transition_memory(memory_id, "rejected", actor)
    def defer_memory(self, memory_id, actor="user"): self.transition_memory(memory_id, "deferred", actor)
    def delete_memory(self, memory_id, actor="user"): self.transition_memory(memory_id, "deleted", actor)

    def list_candidates(self):
        rows = self._execute("SELECT * FROM memory_items WHERE status IN ('candidate','pending','deferred') ORDER BY created_at", (), False).fetchall()
        return [dict(r) for r in rows]

    def update_memory(self, memory_id, value, actor="user"):
        row = self._execute("SELECT * FROM memory_items WHERE id=?", (memory_id,), False).fetchone()
        if not row: return None
        old = dict(row)
        if old["value"] == value: return memory_id
        self.transition_memory(memory_id, "superseded", actor, "value replaced")
        new = dict(old); new["id"] = None; new["value"] = value; new["supersedes_id"] = memory_id; new["status"] = "confirmed"; new["user_confirmed"] = 1
        return self.create_candidate(new, old.get("source_conversation_id"), status="confirmed")

    def supersede_memory(self, old_id, new_memory, actor="system"):
        self.transition_memory(old_id, "superseded", actor, "conflicting value")
        return self.create_candidate(new_memory, new_memory.get("source_conversation_id"), status="pending")

    def add_episode(self, text, conversation_id=None, message_id=None, importance=0.5, now=None):
        import time, uuid
        eid = uuid.uuid4().hex; now = time.time() if now is None else now
        self._execute("INSERT INTO episodes(id,conversation_id,message_id,text,importance,created_at) VALUES(?,?,?,?,?,?)", (eid, conversation_id, message_id, text, float(importance), now))
        rowid = self._execute("SELECT rowid FROM episodes WHERE id=?", (eid,), False).fetchone()[0]
        self._execute("INSERT INTO episode_fts(rowid,text) VALUES(?,?)", (rowid, text))
        return eid

    def search_episodes(self, query, limit=3):
        if not query or not query.strip(): return []
        rows = self._execute("SELECT e.* FROM episode_fts f JOIN episodes e ON e.rowid=f.rowid WHERE episode_fts MATCH ? AND e.status='active' ORDER BY rank LIMIT ?", (query, int(limit)), False).fetchall()
        if not rows:
            # SQLite's default tokenizer has limited CJK segmentation; keep
            # the FTS path primary and use a parameterized substring fallback.
            rows = self._execute("SELECT * FROM episodes WHERE status='active' AND text LIKE ? ORDER BY created_at DESC LIMIT ?", (f"%{query}%", int(limit)), False).fetchall()
        return [dict(r) for r in rows]

    def export_memories(self):
        return {"memories": self.list_active_memories(), "actions": [dict(r) for r in self._execute("SELECT * FROM memory_actions ORDER BY created_at", (), False).fetchall()]}

    def clear_memories(self, actor="user"):
        for row in self._execute("SELECT id FROM memory_items WHERE status NOT IN ('deleted','rejected')", (), False).fetchall(): self.delete_memory(row[0], actor)
        self._execute("UPDATE episodes SET status='deleted' WHERE status='active'")
        self._execute("DELETE FROM episode_fts")

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
