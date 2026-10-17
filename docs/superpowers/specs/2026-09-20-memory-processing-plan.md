# 芽砚 3D 桌宠、情绪识别与记忆系统全量实施计划

## 文档状态

- 状态：全量实施计划草案，未开始实现
- 日期：2026-09-20
- 适用项目：`P:\Deskpet`
- 本文范围：3D 桌宠运行时、自由活动、情绪识别、宠物状态、聊天接入、记忆系统、隐私、测试、打包和回滚
- 暂缓范围：MCP 工具调用、复杂剧本系统、摄像头人脸情绪识别、多角色群聊

## 1. 背景与目标

当前项目是 PyQt5 桌面程序，已经有透明宠物窗口、聊天、专注、任务记录、语音接口和 `memory_mode` 设置项。当前宠物形象仍是一张整体 PNG，动作主要依靠整图旋转、缩放和窗口平移；聊天消息保存在进程内的 `self.messages`，重启后不会自动恢复；模型请求只收到当前上下文，跨会话也没有可查询的长期信息。`desktop/persona.md` 已经规定了“低风险偏好可逐渐学习，个人事实和稳定情绪规律需确认，高风险信息必须明确确认”的边界，本计划把 3D 表现、情绪识别和记忆能力统一落实为可测试的系统。

本计划的目标是让芽砚能够：

1. 保存可恢复的会话记录。
2. 从用户消息中提取记忆候选，但不把模型臆测直接写成用户事实。
3. 根据风险和置信度决定自动保存、轻量确认或明确确认。
4. 在新对话中只召回与当前问题相关的记忆。
5. 处理记忆重复、冲突、过期和用户修改。
6. 给用户提供查看、编辑、删除、导出和清空入口。
7. 在离线、无 API Key 和检索失败时保持聊天功能可用。
8. 使用 Godot 4 承载 3D 宠物和自由活动，保留 Python 作为聊天、情绪、记忆和隐私服务。
9. 让用户情绪识别结果可以驱动克制、可解释的宠物行为。
10. 保证 3D 运行时异常不会拖垮聊天和记忆服务。

## 2. 设计决策

### 2.1 先结构化记忆，再接向量检索

第一阶段使用 SQLite + FTS5 或参数化 SQL 完成会话记录、用户画像和候选管理。向量检索作为后续适配器加入，不作为第一阶段的强依赖。

原因：

- 结构化事实更容易解释、修改和删除。
- 桌面程序不需要启动额外数据库服务。
- 可以在没有 embedding 服务时完整运行。
- 先测量记忆质量，再决定是否需要本地 embedding 或 `sqlite-vec`。

### 2.2 用户事实与情节记忆分开

“用户喜欢乌龙茶”属于稳定画像；“上周我们讨论过论文大纲”属于情节记忆。两者的保存条件、召回方式、过期策略不同，不能混在一个无法解释的文本列表中。

### 2.3 候选提取异步执行

用户发送消息后，聊天回复应立即开始。记忆候选提取在独立线程中执行，失败、超时或返回非法 JSON 时只记录日志，不影响聊天。

### 2.4 只有用户内容可以形成用户画像

assistant 内容可以作为会话或情节记录保存，但不能直接成为用户事实。只有用户明确说出的内容，或用户确认过的候选，才能进入 `profile`。

### 2.5 删除是可验证的状态变化

删除记忆后，后续检索不能再返回它；必要时同时删除向量和全文索引内容。软删除用于保留审计和冲突来源，用户选择“清空全部”时提供彻底清理选项。

## 3. 记忆分层

```text
L0 当前请求
   当前用户消息、最近几条可用上下文、当前任务状态

L1 会话记录
   当前会话的完整 user/assistant 消息，可重启恢复

L2 用户画像
   用户确认或达到低风险写入条件的稳定事实和偏好

L3 情节记忆
   可复用的经历摘要，例如完成一次专注、讨论过一个计划

L4 检索索引
   L1/L3 的 FTS5 索引，未来可以增加 embedding 适配器
```

读取优先级：

1. L0 必须带入。
2. L2 只带入有效且与当前问题相关的字段。
3. L3 默认最多召回 3 条，并保留来源和时间。
4. L1 只带当前会话需要的最近消息，不把所有历史聊天塞入 prompt。
5. L4 只负责查询，不把索引当成新的事实源。

## 4. 功能需求

### M-01 会话持久化

系统应保存每个会话的标题、创建时间、更新时间、消息数量和归档状态。

每条消息至少保存：

- `id`
- `conversation_id`
- `role`
- `content`
- `timestamp`
- `context_eligible`
- `model_used`
- `stopped`
- `metadata_json`

停止生成的半截 assistant 消息必须继续遵守当前 `context_eligible=False` 规则，不能污染后续上下文或记忆候选。

### M-02 记忆候选提取

候选提取器接收最近 3 条有效用户消息和必要的会话上下文，返回严格 JSON：

```json
{
  "candidates": [
    {
      "subject": "user",
      "predicate": "prefers",
      "value": "晚上工作",
      "memory_type": "preference",
      "risk_level": "low",
      "confidence": 0.86,
      "evidence_message_id": "msg_123",
      "expires_at": null
    }
  ]
}
```

提取器必须满足：

- 只提取用户明确表达或明确确认的事实。
- 不把问题、假设、玩笑和模型回复当成事实。
- 不保存原始敏感内容到日志。
- 缺字段、类型错误或 JSON 非法时返回空候选。
- 候选必须带来源消息 ID。

### M-03 风险分级与写入策略

| 风险 | 例子 | 默认策略 | 用户交互 |
| --- | --- | --- | --- |
| low | 喜欢的饮料、常用语言、工作时段 | 重复 2 次后生成确认提示或按设置自动保存 | 非阻塞提示，可关闭 |
| medium | 工作单位、长期项目、生活安排 | 重复 3 次后进入确认队列 | 用户点击确认才保存 |
| high | 住址、健康状况、财务、联系方式 | 永不自动保存 | 明确确认框，支持永久拒绝此类记忆 |

低风险自动学习也必须受 `memory_mode` 控制。`session` 模式不写入 L2/L3；`graded` 模式按上表执行。

### M-04 记忆候选状态机

```text
detected
  ├─ low + 未达到阈值 → observed
  ├─ low + 达到阈值 → pending_confirmation 或 confirmed（由设置决定）
  ├─ medium → pending_confirmation
  └─ high → explicit_confirmation_required

pending_confirmation
  ├─ confirm → confirmed
  ├─ reject → rejected
  └─ later → deferred

confirmed
  ├─ 新值冲突 → superseded
  ├─ 用户删除 → deleted
  └─ 过期 → expired
```

状态变化要有时间、来源和操作主体，便于解释“为什么记住”以及恢复误操作。

### M-05 记忆去重与冲突

同一个 `subject + predicate` 的相同值应合并计数，不重复创建多条记录。

值发生变化时：

1. 旧记录标记为 `superseded`。
2. 新记录进入候选或确认流程。
3. 旧值不再参与默认召回。
4. 详情页仍可显示“曾经被替换”的来源。

### M-06 记忆检索

第一版提供两个查询接口：

```python
profile.build_context_hint(query: str) -> str
memory.search_episodes(query: str, limit: int = 3) -> list[dict]
```

默认排序：

```text
final_score =
    0.55 * relevance
  + 0.25 * importance
  + 0.20 * recency
```

其中：

- `relevance`：FTS5 或关键词相关度；
- `importance`：用户确认、高风险但已确认、任务结果等重要程度；
- `recency`：时间衰减；
- 已删除、拒绝、过期和被替换记录不得进入结果。

检索结果必须返回：

- 记忆文本；
- 记忆类型；
- 来源会话；
- 创建时间或相对时间；
- 置信度；
- 是否用户确认。

### M-07 Prompt 注入

`llm_client.py` 的 instructions 追加两个独立区块：

```text
## 用户长期画像
只把已确认或低风险已生效的事实当作参考。

## 相关经历
这些内容来自历史记录，可能过时；与当前问题无关时忽略，不要当作硬事实。
```

不得把原始数据库 SQL、内部状态名、风险评分和拒绝记录发送给模型。

### M-08 记忆管理界面

设置面板增加“我的记忆”入口，至少支持：

- 查看生效记忆；
- 按类型和风险筛选；
- 查看来源和时间；
- 编辑低风险字段；
- 删除单条记忆；
- 导出 JSON；
- 清空全部记忆；
- 查看待确认候选；
- 关闭某一类记忆的自动学习。

删除和清空必须二次确认。界面不能只提供“关闭记忆”而不提供已保存内容的删除入口。

## 5. 数据库设计

建议新增 `output/runtime/memory.sqlite3`，该路径已属于本地运行状态，不进入 Git。

### 5.1 conversations

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    deleted_at REAL,
    settings_snapshot TEXT NOT NULL DEFAULT '{}'
);
```

### 5.2 messages

```sql
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    timestamp REAL NOT NULL,
    context_eligible INTEGER NOT NULL DEFAULT 1,
    stopped INTEGER NOT NULL DEFAULT 0,
    model_used TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

### 5.3 memory_items

```sql
CREATE TABLE memory_items (
    id TEXT PRIMARY KEY,
    memory_type TEXT NOT NULL CHECK (
        memory_type IN ('preference', 'profile', 'constraint', 'episode')
    ),
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value TEXT NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status TEXT NOT NULL CHECK (
        status IN ('candidate', 'observed', 'pending', 'confirmed',
                   'rejected', 'deferred', 'superseded', 'deleted', 'expired')
    ),
    scope TEXT NOT NULL DEFAULT 'user',
    source_message_id TEXT,
    source_conversation_id TEXT,
    created_at REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    expires_at REAL,
    supersedes_id TEXT,
    user_confirmed INTEGER NOT NULL DEFAULT 0,
    deleted_at REAL,
    FOREIGN KEY (source_message_id) REFERENCES messages(id),
    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id)
);
```

### 5.4 memory_observations

```sql
CREATE TABLE memory_observations (
    id TEXT PRIMARY KEY,
    memory_key TEXT NOT NULL,
    source_message_id TEXT NOT NULL,
    observed_value TEXT NOT NULL,
    confidence REAL NOT NULL,
    observed_at REAL NOT NULL,
    FOREIGN KEY (source_message_id) REFERENCES messages(id)
);
```

该表用于统计“同一事实出现过几次”，避免把计数器和最终记忆混在一起。

### 5.5 memory_actions

```sql
CREATE TABLE memory_actions (
    id TEXT PRIMARY KEY,
    memory_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT,
    created_at REAL NOT NULL
);
```

`actor` 可取 `system`、`user`、`migration`。该表只记录必要的操作信息，不复制完整敏感内容。

### 5.6 索引

第一阶段建立：

```sql
CREATE INDEX idx_memory_status ON memory_items(status);
CREATE INDEX idx_memory_type_status ON memory_items(memory_type, status);
CREATE INDEX idx_memory_source ON memory_items(source_message_id);
CREATE INDEX idx_memory_key ON memory_observations(memory_key);
```

需要全文检索时再增加 FTS5 虚拟表，并通过事务同步写入和删除。

## 6. 模块与接口设计

### 6.1 `desktop/memory_store.py`

职责：数据库连接、迁移、事务、基础 CRUD。

接口：

```python
class MemoryStore:
    def create_conversation(self, title, settings_snapshot): ...
    def append_message(self, conversation_id, message): ...
    def get_recent_messages(self, conversation_id, limit): ...
    def upsert_observation(self, observation): ...
    def create_candidate(self, candidate): ...
    def confirm_memory(self, memory_id, actor="user"): ...
    def reject_memory(self, memory_id, actor="user"): ...
    def supersede_memory(self, old_id, new_memory): ...
    def list_active_memories(self, filters=None): ...
    def delete_memory(self, memory_id, actor="user"): ...
    def export_memories(self): ...
    def clear_memories(self, actor="user"): ...
```

### 6.2 `desktop/memory_policy.py`

职责：风险分级、阈值、自动保存策略、隐私拒绝策略。

策略必须是纯函数或接近纯函数，便于单元测试：

```python
decision = policy.decide(candidate, observations, settings)
```

返回：

```python
{
    "action": "observe|queue_confirmation|confirm_required|ignore",
    "reason": "medium risk requires user confirmation",
    "next_threshold": 3,
}
```

### 6.3 `desktop/memory_extractor.py`

职责：异步调用模型提取候选，解析和校验 JSON。

要求：

- 不把提取失败传播到聊天主线程；
- 有超时；
- 有最大输入和输出长度；
- 使用独立 prompt；
- 过滤 assistant 来源；
- 对不合法值进行 schema 校验；
- 默认不保存原始模型响应。

### 6.4 `desktop/memory_search.py`

职责：画像摘要、情节检索、打分、去重和 prompt 安全格式化。

未来可定义：

```python
class RecallProvider(Protocol):
    def search(self, query: str, limit: int) -> list[dict]: ...
```

SQLite FTS5、`sqlite-vec` 和本地 embedding 都实现同一个接口，避免以后重写 Controller。

### 6.5 `desktop/memory_confirmation.py`

职责：向 UI 发布待确认候选，不直接操作 QWidget。

信号建议：

```python
candidate_ready(candidate_id)
confirmation_requested(candidate_id, level)
memory_confirmed(memory_id)
memory_rejected(memory_id)
```

### 6.6 `desktop/conversation_manager.py`

职责：会话和消息读写，与长期记忆提取解耦。

`ConversationManager` 不决定一条内容是否应该进入画像；它只保存消息并提供查询接口。

## 7. 现有代码接入点

### 7.1 `YayanController.__init__`

新增：

```python
self.memory_store = MemoryStore(runtime_dir / "memory.sqlite3")
self.memory_policy = MemoryPolicy(self.settings)
self.memory_extractor = MemoryExtractor(self.client)
self.memory_search = MemorySearch(self.memory_store)
```

初始化失败时：

- 记录本地错误；
- 使用 `memory_mode="session"` 运行；
- 不阻止聊天窗口打开；
- 在设置页提示记忆功能暂时不可用。

### 7.2 `send_chat()`

顺序：

1. 创建用户消息 ID。
2. 写入 `messages`。
3. 根据 `memory_mode` 启动候选提取任务。
4. 检索当前问题所需的画像和情节记忆。
5. 构造 `merged_context`。
6. 启动原有聊天 Worker。

检索失败时使用没有长期记忆的 context 继续请求。

### 7.3 `worker_completed()`

聊天完成后：

1. 保存完整 assistant 消息。
2. 根据 `context_eligible` 判断是否进入情节记忆。
3. 不把 assistant 内容直接写入用户画像。
4. 触发异步摘要或索引任务。
5. 保留现有 TTS 行为。

### 7.4 `chat_stream.py`

继续使用现有 `context_eligible` 过滤，并补充：

- `stopped` 消息不能进入画像候选；
- 空内容消息不能进入记忆；
- 主动消息默认不进入普通会话上下文，除非用户回复。

### 7.5 `llm_client.py`

只增加安全的 context 拼接函数，不把数据库逻辑放进模型客户端：

```python
def build_memory_context(profile_hint, recalled_episodes):
    ...
```

模型客户端只负责把已经格式化的记忆参考附加到 instructions，不能直接查询数据库。

### 7.6 `SettingsPanel`

新增设置：

- 记忆模式：仅当前会话 / 分级记忆；
- 低风险偏好：自动记忆 / 询问后记忆 / 不记忆；
- 主动提示记忆候选：开启 / 关闭；
- 记忆管理入口；
- 导出和清空操作。

## 8. 实施阶段

### 阶段 0：契约与迁移准备

任务：

- [ ] 定义消息、候选、记忆、检索结果的数据结构。
- [ ] 给本地数据库增加 schema 版本。
- [ ] 增加安全的 runtime 路径解析。
- [ ] 保持现有 `memory_mode` 兼容。
- [ ] 设计损坏数据库的备份和重建提示。

验收：

- [ ] 旧版本没有数据库时可以自动创建。
- [ ] 数据库版本不匹配时不会静默覆盖。
- [ ] `session` 模式不写长期记忆。

### 阶段 1：会话持久化

任务：

- [ ] 实现 conversations 表。
- [ ] 实现 messages 表。
- [ ] 接入用户消息写入。
- [ ] 接入 assistant 完整回复写入。
- [ ] 保存停止状态和上下文资格。
- [ ] 重启恢复最近会话。

验收：

- [ ] 重启后会话和消息顺序不变。
- [ ] 停止生成的半截回复不进入下一次模型上下文。
- [ ] 损坏一条消息不会破坏其他会话。

### 阶段 2：画像候选与确认

任务：

- [ ] 实现候选 JSON schema。
- [ ] 实现 low / medium / high 风险策略。
- [ ] 实现 occurrence counter。
- [ ] 实现确认、拒绝、稍后处理。
- [ ] 实现 confirmed、rejected、superseded 状态。
- [ ] 接入设置页待确认列表。

验收：

- [ ] assistant 内容不会直接生成用户画像。
- [ ] high 风险内容不会自动保存。
- [ ] 用户拒绝后不会在每条消息中重复弹窗。
- [ ] 相同事实不会创建重复记录。

### 阶段 3：记忆管理

任务：

- [ ] 显示生效记忆。
- [ ] 显示来源和风险等级。
- [ ] 单条删除。
- [ ] 编辑低风险事实。
- [ ] 导出 JSON。
- [ ] 清空全部记忆。
- [ ] 记录 memory_actions。

验收：

- [ ] 删除后检索结果不再返回该条。
- [ ] 导出文件不包含 API Key。
- [ ] 清空操作可恢复前备份或明确提示不可恢复。

### 阶段 4：可解释检索

任务：

- [ ] 实现 profile hint。
- [ ] 实现 episode 检索。
- [ ] 实现相关度、重要性和时间衰减。
- [ ] 限制召回条数和字符数。
- [ ] 记录召回 ID 供调试。
- [ ] 增加 FTS5 适配器。

验收：

- [ ] 当前问题优先召回相关记忆。
- [ ] 旧的低重要性内容不会长期霸占结果。
- [ ] 被删除、拒绝、过期和替换的记录不被召回。
- [ ] 没有记忆或检索失败时聊天仍能完成。

### 阶段 5：可选 embedding

任务：

- [ ] 先收集 FTS5 召回失败样例。
- [ ] 定义 `RecallProvider` 接口。
- [ ] 选择本地 embedding 或 `sqlite-vec`。
- [ ] 异步生成向量。
- [ ] 为向量记录保存模型版本。
- [ ] 支持删除和重建索引。

验收：

- [ ] embedding 不影响无网络启动。
- [ ] embedding 失败回退 FTS5。
- [ ] 更换 embedding 模型不会破坏结构化记忆。

## 9. 测试清单

### 单元测试

- [ ] 数据库初始化和 schema 迁移。
- [ ] 会话创建、更新、归档和删除。
- [ ] 消息追加和顺序读取。
- [ ] `context_eligible=False` 过滤。
- [ ] 候选 JSON 合法性校验。
- [ ] low / medium / high 策略。
- [ ] 重复观察计数。
- [ ] 相同候选去重。
- [ ] 冲突候选 supersede。
- [ ] 记忆过期。
- [ ] 删除后检索为空。
- [ ] 导出不包含密钥字段。
- [ ] FTS5 查询为空时安全返回。
- [ ] 检索失败回退为空上下文。

### 集成测试

- [ ] `send_chat()` 写入用户消息并带入检索结果。
- [ ] `worker_completed()` 写入 assistant 回复。
- [ ] 聊天取消后不产生画像候选。
- [ ] 模型提取超时不阻塞聊天。
- [ ] 设置从 `graded` 切换到 `session` 后立即生效。
- [ ] 用户确认后记忆可被下一次聊天召回。
- [ ] 用户删除后下一次聊天不再召回。

### 隐私测试

- [ ] API Key 不进入数据库。
- [ ] API Key 不进入导出文件。
- [ ] 高风险候选默认不落库为 confirmed。
- [ ] 日志不打印完整敏感文本。
- [ ] 删除后全文索引同步删除。
- [ ] 清空操作处理 SQLite WAL 和临时文件。

### 离线测试

- [ ] 无网络时数据库和设置页正常打开。
- [ ] 没有 embedding 包时使用 FTS5 或关键词检索。
- [ ] 没有模型 Key 时不调用候选提取器。
- [ ] 数据库被占用时给出可理解提示。
- [ ] 数据库损坏时保留原文件并创建恢复提示。

## 10. 验收场景

### 场景 A：低风险偏好

用户两次说“我喜欢乌龙茶”。系统生成低风险候选，达到阈值后提示用户；用户确认后，下一次询问饮料时可以参考该偏好。

### 场景 B：中风险事实

用户多次提到正在准备考试。系统在达到重复阈值后只显示一次确认，用户选择“以后再说”时不保存，之后一段时间不重复询问。

### 场景 C：高风险事实

用户提到住址或健康情况。系统不会自动确认或写入画像；只有用户明确点击确认后才保存，并且管理界面允许删除。

### 场景 D：冲突更新

用户先说“我晚上工作”，后来改为“我最近改成早上工作”。旧记录被替换，下一次建议优先使用新记录，并可以查看来源。

### 场景 E：助手幻觉

芽砚在回复中猜测用户喜欢某种食物。该猜测不能进入用户画像，也不能在以后作为确定事实使用。

### 场景 F：停止生成

用户停止模型回复。半截 assistant 内容显示在界面上，但不进入长期画像，不参与默认情节召回。

### 场景 G：数据库不可用

数据库无法打开。聊天继续使用当前会话上下文，设置页显示记忆暂时不可用，程序不退出。

## 11. 文件修改清单

### 新增文件

```text
desktop/memory_store.py
desktop/memory_policy.py
desktop/memory_extractor.py
desktop/memory_search.py
desktop/memory_confirmation.py
desktop/conversation_manager.py
tests/test_memory_store.py
tests/test_memory_policy.py
tests/test_memory_search.py
tests/test_memory_integration.py
```

### 可能修改文件

```text
desktop/main.pyw
desktop/llm_client.py
desktop/chat_stream.py
desktop/persona.md
desktop/settings.json
scripts/verify_desktop.py
README.md
```

### 运行时新增文件

```text
output/runtime/memory.sqlite3
output/runtime/memory.sqlite3-wal
output/runtime/memory.sqlite3-shm
output/runtime/memory-export.json
```

这些文件属于本机状态，不应进入 Git。

## 12. 不建议直接照搬的教材内容

1. 不要把五层记忆一次性全部实现，先完成 L1、L2 和可解释检索。
2. 不要让 assistant 输出直接写入用户画像。
3. 不要把高风险信息按重复次数自动保存。
4. 不要在聊天主线程同步等待记忆提取模型。
5. 不要把完整历史消息全部拼进 prompt。
6. 不要将“用户没有来”解释成用户对宠物的负面关系。
7. 不要把记忆系统设计成无法删除的隐形状态。
8. 教材示例中的中文分块参数需要重新验证；块长和重叠长度不能相同，否则滑动窗口无法前进。

## 13. 完成标准

记忆子系统完成的最低标准：

- [ ] 会话可以重启恢复。
- [ ] 用户画像有风险分级和确认流程。
- [ ] assistant 内容不会污染用户事实。
- [ ] 记忆可以查看、编辑、删除和导出。
- [ ] 记忆检索有来源、时间和置信度。
- [ ] 删除、拒绝、过期和替换记录不会继续召回。
- [ ] 无网络和无 Key 时不影响聊天基础功能。
- [ ] 单元、集成、隐私和离线测试全部通过。
- [ ] 现有聊天、专注、任务和设置功能回归通过。

## 14. 记忆子系统实施顺序

记忆部分仍按以下顺序实现：

1. 数据库、迁移和纯逻辑策略，不接模型。
2. 固定候选数据的风险分级、确认和冲突测试。
3. 会话写入和重启恢复。
4. 候选提取 Worker。
5. 设置页记忆管理。
6. profile hint 和 FTS5 检索。
7. 在真实检索失败样例足够多后，再评估 embedding。

这样可以先验证“记忆可靠、可控、可删除”，再增加模型调用和更复杂的检索能力。

## 15. 全量系统架构

### 15.1 进程划分

```text
Godot 4 进程
  ├─ 透明置顶 3D 宠物窗口
  ├─ 骨骼动画和自由活动
  ├─ 鼠标、拖拽、悬停事件
  └─ 气泡和轻量特效

Python 主进程
  ├─ PyQt 聊天、设置、任务和专注面板
  ├─ YayanLLMClient
  ├─ 情绪快路径和慢路径
  ├─ MemoryStore / ProfileStore / EpisodeStore
  ├─ 主动行为调度
  └─ PetBridge 通信服务

本地运行时数据
  ├─ output/runtime/memory.sqlite3
  ├─ output/runtime/user-settings.json
  ├─ output/runtime/desktop-state.json
  └─ output/runtime/logs/
```

### 15.2 通信边界

Godot 不直接读取 API Key、SQLite 或用户记忆。Python 只向 Godot 发送已经决定好的行为命令。

Python → Godot：

```json
{
  "type": "pet_command",
  "command": "set_state",
  "state": "concerned",
  "duration_ms": 3000,
  "trace_id": "msg-001"
}
```

Godot → Python：

```json
{
  "type": "pet_event",
  "event": "clicked",
  "position": {"x": 1200, "y": 760},
  "timestamp": 1780000000
}
```

通信要求：

- 每条消息有 `schema_version`、`trace_id` 和时间戳。
- Godot 断开时 Python 不崩溃，聊天继续工作。
- Python 重启后 Godot 可以重新连接。
- 命令有过期时间，旧命令不能覆盖新状态。
- 通信日志不记录 API Key 和完整敏感原文。

## 16. 3D 桌宠运行时实施

### 16.1 工具和资源

- Blender：建模、材质、骨骼、权重和动画。
- Godot 4：运行时、动画状态机和桌面窗口。
- GLB/glTF：模型交换格式。
- Windows 原生窗口接口：透明、置顶、多显示器和工作区信息。

不把当前水彩 PNG 直接放大成 3D。PNG 继续作为视觉参考，需要重新制作低面数、轮廓清晰的 3D 模型。

### 16.2 目录规划

```text
godot/
  project.godot
  scenes/Main.tscn
  scenes/Pet.tscn
  scripts/pet_controller.gd
  scripts/animation_controller.gd
  scripts/roam_controller.gd
  scripts/bridge_client.gd
  scripts/window_controller.gd
  assets/yayan.glb
  assets/materials/
  assets/animations/
  tests/

assets/3d/yayan.glb
assets/3d/preview/
```

### 16.3 模型要求

- 身体、头、耳朵、尾巴和四肢可绑定骨骼。
- 眼皮和耳朵可以单独播放动画。
- 尾巴有独立骨骼，动作带滞后。
- 身体有胸口呼吸和轻微重心变化。
- 模型在 320 至 500 像素高的窗口中仍能看清脸部。
- 使用简单材质和少量纹理，优先保证流畅度。
- 记录模型版本、骨骼版本和动画版本。

### 16.4 第一批动画

```text
idle
blink
breathe
look_left
look_right
look_up
look_down
walk
turn_left
turn_right
stop
sit
stretch
sleepy
happy
concerned
curious
shy
dragged
```

### 16.5 动画状态机

```text
IDLE
  ├─ cursor_near → LOOK
  ├─ timer → ROAM_DECIDE
  ├─ user_click → REACT
  ├─ user_drag → DRAGGED
  └─ quiet_mode → SLEEPY

ROAM_DECIDE → TURNING → WALKING → STOPPING → IDLE
LOOK → IDLE
REACT → IDLE
DRAGGED → IDLE
EMOTION_REACT → IDLE
```

每个状态必须定义：

- 优先级；
- 最短持续时间；
- 最大持续时间；
- 可以被什么事件打断；
- 对应动画；
- 是否允许移动；
- 是否允许气泡。

### 16.6 桌面自由活动

第一版采用无障碍的二维安全区域，不做复杂桌面障碍物寻路：

- 默认活动区域为当前显示器工作区底部 15% 至 25%。
- 宠物不得覆盖任务栏关键区域。
- 多显示器时使用当前窗口所在显示器。
- 用户可以选择左下、右下、底部居中或固定位置。
- 进入安静模式后停止自主移动。
- 全屏应用检测失败时，使用保守的低频活动策略。

动作顺序：

1. 选择目标点。
2. 计算朝向。
3. 转身动画。
4. 行走动画和位置同步。
5. 减速和停步。
6. 进入 idle。

### 16.7 透明窗口 POC

这是 3D 实施的第一道技术门槛，必须在正式建模前完成：

- 无边框窗口；
- 透明背景；
- 置顶；
- 点击事件；
- 拖动事件；
- 多显示器定位；
- 窗口关闭和重启；
- 不遮挡聊天面板。

如果 Godot 默认窗口能力无法满足要求，再增加 Windows 原生窗口扩展，不能等模型和动画完成后才验证。

## 17. 情绪识别实施

### 17.1 输入范围

第一版读取：

- 用户主动输入的文字；
- 语音转写文本；
- 最近几轮对话的上下文；
- 用户明确提出的“安静”“陪我一下”等意图。

第一版不读取：

- 摄像头；
- 屏幕截图；
- 全局键盘内容；
- 用户未主动提供的窗口内容。

### 17.2 情绪双路径

快路径在本地同步执行：

- 中文情绪词；
- 否定词和程度词；
- 表情符号；
- 标点和短句模式。

慢路径异步执行：

- 结合最近上下文；
- 处理反话、玩笑和复杂叙述；
- 返回 8 类情绪分布；
- 返回强度、置信度、紧急程度和建议回应方式。

### 17.3 情绪结果

```json
{
  "schema_version": 1,
  "trace_id": "msg-001",
  "dominant_emotion": "sadness",
  "intensity": 0.72,
  "confidence": 0.84,
  "pet_empathy": "concerned",
  "urgency": "none",
  "expires_in_seconds": 1800,
  "evidence": ["用户明确表达了失落"]
}
```

慢路径结果必须检查 `trace_id` 和消息代次。已经开始新一轮聊天后，旧结果不得覆盖当前宠物状态。

### 17.4 用户情绪和宠物状态分离

用户情绪使用：

```text
neutral / joy / sadness / anger / anxiety / surprise / sleepy / shy
```

宠物表现使用：

```text
idle / happy / concerned / curious / sleepy / shy
```

用户的 `sadness` 不等于宠物的 `sad`。宠物只需要表现为更靠近、更安静、更关注。

### 17.5 情绪安全规则

- 低置信度保持 neutral。
- 单条消息不能永久修改用户画像。
- 情绪结果必须过期。
- 明确的危险表达触发独立安全流程，不交给普通宠物情绪处理。
- 情绪识别不做疾病诊断。
- 用户开启安静模式后，不因情绪识别发起主动气泡。
- 识别失败不能阻塞聊天。

## 18. 宠物状态和情绪联动

### 18.1 状态优先级

```text
安全响应
> 用户拖拽
> 正在聊天
> 明确点击
> 专注完成或任务事件
> 情绪回应
> 自主移动
> 普通待机
```

### 18.2 映射规则

| 用户状态 | 宠物表现 | 主动行为 |
| --- | --- | --- |
| neutral | idle / curious | 正常 |
| joy | happy | 短暂庆祝 |
| sadness | concerned | 靠近，减少提醒 |
| anger | concerned / shy | 先承接情绪，不说教 |
| anxiety | concerned | 小幅动作，只给一个小建议 |
| surprise | curious | 歪头、耳朵立起 |
| sleepy | sleepy | 降低活动频率 |
| 不确定 | idle | 不强行猜测 |

### 18.3 状态过渡

不能把所有状态直接瞬间切换。每个状态要支持：

- transition；
- hold；
- exit；
- cancel；
- expiration。

例如：

```text
idle → look_at_user → concerned_transition → concerned → idle_transition → idle
```

## 19. Python 与现有 PyQt 接入

### 19.1 新增文件

```text
desktop/contracts.py
desktop/event_bus.py
desktop/pet_bridge.py
desktop/emotion_schema.py
desktop/emotion_rules.py
desktop/emotion_service.py
desktop/emotion_policy.py
desktop/memory_store.py
desktop/memory_policy.py
desktop/memory_extractor.py
desktop/memory_search.py
desktop/memory_confirmation.py
desktop/conversation_manager.py
desktop/proactive.py
desktop/proactive_policy.py
```

### 19.2 现有文件修改

```text
desktop/main.pyw
desktop/llm_client.py
desktop/chat_stream.py
desktop/persona.md
desktop/settings.json
scripts/verify_desktop.py
Start-Yayan.cmd
Stop-Yayan.cmd
README.md
```

### 19.3 `main.pyw` 改造顺序

1. 先保留当前 PyQt `ChatPanel`、`SettingsPanel`、`FocusSession`。
2. 将宠物状态事件从 `PetWindow` 中抽成接口。
3. 将 `user_emotion`、`pet_mood`、`interaction_state` 和 `activity_state` 分开。
4. 接入 `MemoryStore` 和 `MemorySearch`。
5. 接入 `EmotionService`。
6. 接入 `PetBridge`。
7. 逐步关闭旧的整图 `paintEvent()` 动画路径。
8. 最终由 Godot 接管宠物窗口，PyQt 保留聊天和设置面板。

### 19.4 聊天接入点

`send_chat()`：

1. 创建带 ID 的 user message。
2. 写入会话数据库。
3. 启动快路径情绪识别。
4. 检索 profile 和 episode 记忆。
5. 启动慢路径情绪识别。
6. 把合并后的 context 交给聊天 Worker。
7. 发送 `set_state` 或 `show_bubble` 到 Godot。

`worker_completed()`：

1. 保存完整 assistant 回复。
2. 只把符合 `context_eligible` 的内容送入情节摘要。
3. 不把 assistant 内容写入用户画像。
4. 启动 assistant 情绪识别。
5. 根据回复内容发送最终宠物状态。
6. 保留原有 TTS 行为。

## 20. 主动行为和自由活动联动

### 20.1 活动等级

- 安静：停止主动气泡和自主移动，只响应用户。
- 平衡：偶尔走动和靠近，每小时主动气泡不超过 2 次。
- 活跃：允许更多靠近和事件回应，但仍受冷却限制。

### 20.2 情绪抑制

用户处于 sadness、anger、anxiety 或 urgency 时：

- 暂停普通喝水和任务提醒；
- 降低主动对话概率；
- 只保留与当前情绪直接相关的简短回应；
- 用户不回复时自动结束，不连续追问。

### 20.3 事件来源

第一阶段只接入：

- 用户点击；
- 聊天开始和结束；
- 专注会话完成；
- 安静模式切换；
- 用户返回桌面宠物；
- 长时间没有输入。

屏幕窗口内容、文件内容和全局键盘内容不作为第一阶段事件来源。

## 21. 启动、打包和回滚

### 21.1 启动流程

`Start-Yayan.cmd` 负责：

1. 检查 Python 运行环境。
2. 启动 Python 主进程。
3. 等待 `PetBridge` 就绪。
4. 启动 Godot 宠物进程。
5. Godot 连接成功后进入 idle。
6. 连接失败时保留 PyQt 聊天功能，并显示可理解的错误提示。

### 21.2 退出流程

`Stop-Yayan.cmd` 负责：

- 先通知 Godot 停止活动；
- 等待 Python 保存数据库事务；
- 关闭 Godot；
- 关闭 Python；
- 超时后只结束本项目启动的进程，不结束其他 Python 进程。

### 21.3 版本和迁移

- `memory.sqlite3` 有 schema version。
- `desktop-state.json` 和 `settings.json` 增加格式版本。
- 3D 模型、动画和通信协议分别记录版本。
- 每次数据库迁移前备份运行时数据库。
- 不用 `git reset --hard` 或覆盖用户运行时数据完成迁移。

### 21.4 回滚策略

每个阶段都保留可运行版本：

- 3D 连接失败时回退到旧 PyQt 宠物窗口。
- 情绪服务失败时回退到 neutral。
- 记忆数据库失败时回退到 session 模式。
- embedding 失败时回退 FTS5。
- 新协议无法连接时保留聊天和设置功能。

## 22. 范围核对矩阵与性能指标

本节把用户要求的全部能力映射到设计、实现、测试和验收，后续实施不得只完成其中一部分。

### 22.1 端到端范围核对矩阵

| 能力域 | 设计内容 | 主要实现 | 必须验证 |
| --- | --- | --- | --- |
| 技术选型 | Godot 4 + Blender + GLB/glTF + Python/PyQt | `godot/`、`desktop/`、启动脚本 | 无模型 POC 可启动、通信可重连、旧版可回退 |
| 系统架构 | Godot 表现层、Python 服务层、SQLite 数据层、PetBridge 边界 | `pet_bridge.py`、`contracts.py`、`memory_store.py` | 进程隔离、故障降级、协议版本兼容 |
| 3D 模型设计 | 低面数、清晰轮廓、独立骨骼、尾巴/耳朵/眼皮、材质和版本管理 | `assets/3d/`、Blender 资源、`Pet.tscn` | 320–500px 窗口中脸部可辨、动作不穿模、资源可替换 |
| 活动方式 | 安全区域、目标点、转身、行走、停步、安静模式、多显示器 | `roam_controller.gd`、`window_controller.gd` | 不遮挡任务栏/聊天区、不越界、不持续抖动 |
| 交互 | 点击、双击、悬停、拖动、气泡、固定位置、快捷关闭 | `pet_controller.gd`、`bridge_client.gd` | 事件可追踪、拖动不误触、键鼠交互不阻塞聊天 |
| 情绪识别 | 快路径规则 + 慢路径模型、置信度、紧急度、过期和 trace_id | `emotion_rules.py`、`emotion_service.py`、`emotion_policy.py` | 识别失败/超时/旧结果不影响聊天 |
| 后续反应 | 用户情绪与宠物状态分离，状态优先级、过渡、抑制和主动行为冷却 | `proactive.py`、Godot AnimationTree | sadness/anger/anxiety 下克制回应；低置信度保持 neutral |
| 记忆系统 | 会话、画像、情节记忆、候选、确认、冲突、删除、FTS5、可选 embedding | `memory_*`、SQLite migration、设置页 | 重启恢复、相关召回、删除后不可召回、assistant 不污染画像 |
| 性能与可靠性 | 启动、交互、动画帧率、CPU/GPU、内存、检索、降级和日志 | `scripts/verify_desktop.py`、性能测试 | 达到 22.2 的阈值，异常可诊断并可回滚 |

### 22.2 性能预算与 SLO

以下指标以 Windows 10/11、普通办公电脑（4 核 CPU、8GB 内存、集成显卡）为最低基线；高配机器不得以更高资源消耗掩盖实现问题。

| 指标 | 目标 | 硬上限/失败条件 | 测量方式 |
| --- | --- | --- | --- |
| 冷启动到可交互 | ≤ 3 秒 | > 6 秒失败 | 从启动脚本开始计时，到聊天面板、Godot 窗口和 bridge 就绪 |
| Godot 进程连接 | ≤ 1 秒 | > 3 秒或连续重连失败 | bridge 握手日志 |
| 点击/悬停到宠物反应 | p95 ≤ 120 ms | p95 > 250 ms | 事件时间戳到首个动画状态变更 |
| 拖动跟手延迟 | p95 ≤ 50 ms | p95 > 100 ms | 鼠标采样与窗口位置更新差值 |
| 动画帧率 | 常态 60 FPS | 连续 5 秒低于 30 FPS 失败 | Godot 帧时间统计 |
| 空闲 CPU | Python + Godot 平均 ≤ 5% | 连续 60 秒 > 10% | Windows 进程采样 |
| 空闲 GPU | 平均 ≤ 8% | 连续 60 秒 > 15% | Windows GPU 引擎采样 |
| 常驻内存 | Python + Godot ≤ 350 MB | > 500 MB 或持续增长 | 工作集/私有字节采样 |
| 快路径情绪识别 | p95 ≤ 80 ms | > 200 ms 阻塞发送流程 | 本地规则计时 |
| 慢路径情绪识别 | 异步；超时 ≤ 2 秒 | 阻塞聊天或返回过期结果 | worker 计时与 trace_id 校验 |
| 记忆检索 | 10000 条以内 p95 ≤ 150 ms | > 500 ms 或检索失败导致聊天失败 | SQLite/FTS5 基准测试 |
| 记忆写入/确认 | p95 ≤ 100 ms | > 300 ms | 事务计时 |
| 数据库迁移 | ≤ 2 秒 | 失败且无备份 | migration 测试 |
| 主动行为频率 | 平衡模式每小时 ≤ 2 次气泡 | 超过上限失败 | 行为审计日志 |
| 日志体积 | 单日 ≤ 20 MB | 包含 API Key、完整敏感原文即失败 | 日志扫描 |

### 22.3 可观测性和性能测试要求

- 所有跨进程、情绪、记忆和宠物动作事件必须带 `trace_id`、事件类型、时间戳和结果状态。
- 性能测试必须覆盖冷启动、空闲 10 分钟、连续聊天 30 分钟、拖动 1 分钟、多显示器、安静模式和数据库 10000 条记忆。
- 记录 p50/p95/p99，不只记录平均值；任何硬上限失败都阻止发布。
- 性能回归报告必须标明机器规格、Windows 版本、Godot 版本、模型版本和测试数据规模。
- 发生性能退化时，优先关闭高频主动行为、降低动画采样或回退旧 PyQt 宠物，不牺牲聊天、删除和隐私控制。

## 23. 五步实施计划与依赖

为降低执行复杂度，主计划合并为 5 步。第 8 节的记忆子系统顺序和第 22 节的指标仍然有效，但作为本节步骤内的子任务，不再单独形成项目阶段。

### 步骤 1：基线、契约与运行时骨架

依赖：无。

- [x] 检查当前 PyQt 聊天、设置、任务和宠物行为基线。
- [x] 定义消息、情绪、记忆、宠物命令和 bridge schema。
- [x] 建立 SQLite migration、运行时版本和日志规范。
- [x] 建立 Godot 空窗口 POC：透明、无边框、置顶、多显示器、退出重启。
- [x] 创建回归测试入口和旧版 PyQt 回退开关。

完成条件：旧版程序仍可运行；Godot 空窗口可独立启动；跨进程协议和回退路径确定。

> 进度记录（2026-09-20）：
> - 基线：12 个旧测试通过；`verify_desktop.py` 退出 0。
> - 新增 `desktop/contracts.py`（schema + 校验 + bridge 信封）、`event_bus.py`、`memory_store.py`（迁移+损坏备份）、`pet_bridge.py`（本地 TCP 服务）。
> - `settings.json` 增加 `runtime_version:1`、`pet_renderer:"pyqt"`；`main.pyw` 增加 `resolve_pet_renderer` 回退开关。
> - 新增 Godot 4.7.2 空窗口 POC（`godot/`）：透明(gl_compatibility)+无边框+置顶+多显示器定位；透明自检通过（截图 corner_alpha=0）。
> - bridge e2e 通过：hello 握手 + `set_state` 命令下发（`tmp/godot_bridge_e2e.py`）。
> - 新增 4 个测试文件；全量 49 个测试通过，verify_desktop 全绿。
> - 注意事项：Windows + Godot 需 `gl_compatibility` 渲染器并运行时强制 `transparent`；`connect_to_host` 异步需 `poll()` 并补发 hello。

### 步骤 2：记忆系统与会话持久化

依赖：步骤 1。

- [x] 实现 conversations/messages、profile、episode、candidate、action 表。
- [x] 实现风险分级、候选状态机、确认/拒绝/延后、冲突替换和删除。
- [x] 接入会话恢复、异步提取 Worker、FTS5 检索和来源审计。
- [x] 增加设置页记忆管理：查看、编辑、删除、导出、清空和关闭自动学习。
- [x] 验证 assistant 不污染画像，删除后不可被全文或向量召回。

完成条件：无模型时固定候选测试通过；用户可解释、可控制、可删除所有记忆。

> 进度记录（2026-09-20）：
> - 新增 SQLite v2 业务表、FTS5 索引、事务 CRUD、状态审计、删除/清空/导出。
> - 新增 `memory_policy.py`、`memory_extractor.py`、`memory_search.py`、`conversation_manager.py`。
> - `main.pyw` 接入会话恢复、用户/assistant 消息持久化、异步候选提取、相关经历召回和设置页记忆管理。
> - 无模型候选过滤、风险策略、删除后检索不可召回测试通过；全量 52 个单元测试与 `verify_desktop.py` 通过。

### 步骤 3：情绪识别与反应策略

依赖：步骤 1；可与步骤 2 的后半段并行。

- [x] 实现本地快路径和异步慢路径情绪识别。
- [x] 加入 trace_id、消息代次、置信度、紧急度和过期时间。
- [x] 分离 user_emotion、pet_mood、interaction_state 和 activity_state。
- [x] 实现情绪到宠物状态、主动行为、气泡和抑制规则的映射。
- [x] 对低置信度、超时、危险表达和安静模式做安全降级。

完成条件：情绪识别失败或旧结果不会影响聊天；宠物反应克制、可解释、可过期。

> 进度记录（2026-09-20）：
> - 新增 `emotion_rules.py`、`emotion_policy.py`、`emotion_service.py`。
> - 聊天发送接入本地快路径，携带 trace_id、消息代次、置信度、紧急度和过期时间。
> - 慢路径使用独立线程池并丢弃旧代次、非法和异常结果；低置信度/安静模式保持克制状态。
> - `main.pyw` 已接入模型慢路径 JSON 请求；结果通过 Qt 定时器回到主线程应用，模型不可用时不影响聊天。
> - 新增 3 个情绪回归测试；全量 55 个单元测试与 `verify_desktop.py` 通过。

### 步骤 4：3D 角色、活动与交互

依赖：步骤 1；接入步骤 3 的宠物命令。

- [ ] 完成 Blender 低面数模型、骨骼、权重、材质和 GLB 版本管理。
- [ ] 完成 idle、blink、breathe、walk、turn、stop、happy、concerned、curious、sleepy 等动画。
- [ ] 在 Godot 中实现 AnimationTree、透明窗口、气泡和特效。
- [x] 实现安全区域、目标点、转身、行走、停步、靠近鼠标、多显示器。
- [x] 实现点击、双击、悬停、拖动、固定位置和安静模式。
- [x] 接入 Python bridge、重连、命令过期和 Godot 崩溃保活。

完成条件：宠物不再依赖整图平移；活动不遮挡任务栏和聊天面板；交互事件可追踪。

> 进度记录（2026-09-20）：
> - 新增 `godot/scripts/roam_controller.gd`，提供安全边界、随机目标点、漫游/停步/拖动/悬停和基础状态绘制。
> - `Main.tscn` 接入交互区域；bridge 命令可驱动状态和活动，宠物事件可回传 Python bridge。
> - Blender/GLB、骨骼动画和 AnimationTree 尚未实现；当前绘制角色是运行时占位骨架。
> - 当前环境没有 `godot` 可执行文件，未能执行 Godot headless 语法验证；Python 侧回归测试保持通过。

### 步骤 5：联调、性能、隐私与发布

依赖：步骤 2、3、4。

- [ ] 联调聊天、记忆、情绪、专注完成事件和 3D 动画。
- [ ] 按第 22 节验证启动、bridge、交互延迟、帧率、CPU/GPU、内存、检索和主动行为频率。
- [ ] 验证无网络、无 Key、数据库损坏、Godot 崩溃、Python 重启和旧版回退。
- [ ] 完成隐私、删除、导出、日志脱敏和运行时文件检查。
- [ ] 完成 README、启动/停止脚本、故障排查、发布包冒烟测试。

完成条件：所有关键链路可通过 trace_id 追踪；性能、隐私、降级和回滚验收全部通过。

## 24. 全量验收标准

### 3D 和活动

- [ ] 宠物是骨骼驱动的 3D 模型。
- [ ] idle、walk、turn、stop、happy、concerned 可稳定播放。
- [ ] 宠物能在安全区域自由活动。
- [ ] 点击、拖动和悬停事件正确。
- [ ] 多显示器和安静模式可用。
- [ ] 透明窗口不遮挡主要界面。

### 情绪

- [ ] 快路径低延迟。
- [ ] 慢路径不阻塞聊天。
- [ ] 旧结果不覆盖新结果。
- [ ] 用户情绪与宠物状态分离。
- [ ] 低置信度保持中性。
- [ ] 情绪自动过期。
- [ ] 高风险表达进入独立流程。

### 记忆

- [ ] 会话可以重启恢复。
- [ ] assistant 内容不会污染用户事实。
- [ ] high 风险信息默认不自动保存。
- [ ] 记忆支持查看、确认、拒绝、编辑、删除、导出和清空。
- [ ] 冲突记忆有 supersede 关系。
- [ ] 删除后不会被 FTS5 或 embedding 召回。
- [ ] 记忆检索失败时聊天继续。

### 工程和发布

- [ ] 现有聊天、专注、任务和设置功能回归通过。
- [ ] 无网络、无 Key 和数据库损坏场景可处理。
- [ ] Godot 崩溃不拖垮 Python。
- [ ] Python 崩溃后可重新启动 Godot。
- [ ] 运行时数据库、密钥和日志不进入 Git。
- [ ] 启动和停止脚本只管理本项目进程。
- [ ] 有可回退到旧 PyQt 宠物的路径。

### 性能与可观测性

- [ ] 冷启动、bridge 握手、点击反馈、拖动跟手和动画帧率达到 22.2 的阈值。
- [ ] 空闲 CPU/GPU、常驻内存和主动行为频率达到 22.2 的阈值。
- [ ] 快路径情绪识别和慢路径超时不阻塞聊天。
- [ ] 记忆检索、写入和数据库迁移达到 22.2 的阈值。
- [ ] 性能测试产出 p50/p95/p99 报告，并包含可复现实验环境。
- [ ] 所有关键链路可以用 `trace_id` 从用户消息追踪到宠物反应。

## 25. 交接提示词

以下提示词可以直接交给下一位执行代理。它要求代理先读取本计划，再按五个步骤实施，不把设计文档误当成已经完成的代码。

```text
你正在继续 P:\Deskpet 项目。请先完整阅读：

1. P:\Deskpet\AGENTS.md（如果存在）
2. P:\Deskpet\README.md
3. P:\Deskpet\docs\superpowers\specs\2026-09-20-memory-processing-plan.md
4. P:\Deskpet\desktop\main.pyw
5. P:\Deskpet\desktop\llm_client.py
6. P:\Deskpet\desktop\chat_stream.py
7. P:\Deskpet\desktop\persona.md
8. P:\Deskpet\desktop\settings.json
9. P:\Deskpet\tests\

用户目标：把芽砚升级为 3D、可以在 Windows 桌面自由活动的桌宠，重点做好用户情绪识别和长期记忆；宠物自身情绪保持简单、稳定、克制。

本次交接必须把计划中的技术选型、进程架构、3D 模型设计、活动方式、鼠标交互、情绪识别、情绪后的宠物反应、记忆系统以及性能指标全部实施；不能只实现聊天或只实现 3D 外观。

必须遵守：

- 不覆盖、清理、回退或提交现有用户改动。
- 先检查 git status，再检查相关文件，再实施。
- 记忆、情绪和 3D 运行时必须分层。
- assistant 生成内容不能直接写入用户画像。
- high 风险个人信息不能自动保存，必须明确确认。
- 删除的记忆不能继续被数据库、FTS5 或 embedding 召回。
- 情绪识别失败、超时或返回非法 JSON 时，聊天必须继续。
- 旧的慢结果不能覆盖当前新消息状态。
- 不使用摄像头或全局键盘内容作为第一阶段情绪输入。
- Godot 崩溃不能拖垮 Python 聊天和记忆服务。
- 必须按第 22 节性能预算验证启动时间、交互延迟、帧率、CPU/GPU、内存、情绪延迟、记忆检索和主动行为频率。
- 不要一开始实现 MCP、复杂剧本、多角色群聊或完整养成数值。

推荐实施顺序（合并为五步）：

步骤 1：基线、契约与运行时骨架。
步骤 2：记忆系统与会话持久化。
步骤 3：情绪识别与反应策略。
步骤 4：3D 角色、活动与交互。
步骤 5：联调、性能、隐私与发布。

第 8 节和第 22 节是步骤内的技术子任务与验收标准，不是额外的项目阶段。

每个步骤开始前：

1. 重新读取本计划中对应章节。
2. 列出要修改和新增的文件。
3. 说明风险和验证方式。
4. 只做当前步骤范围内的工作。

每个步骤完成后：

1. 运行对应测试和离线验证。
2. 检查 git diff 和敏感信息。
3. 更新本计划中的复选框和进度记录。
4. 报告修改文件、验证结果、已知问题和下一阶段。

第一步只做“步骤 1”的只读检查和接口设计，不要直接开始写 Godot 模型或修改聊天行为。完成检查后，先给出实施清单和风险，再按本计划开始最小可验证实现。
```
