# 记忆闭环（Memory Sedimentation）— 设计方案

> 日期: 2026-06-18 | 状态: 已定稿 | 关联: 追读力系统（后续）→ 质量评分（后续）

## 1. 目标

Novel-Claude 的记忆系统目前只有"写前注入"（`mem_working_memory`），缺少"写后沉淀"。本章生成的数据不回流到 `StoryState`，导致 L1/L2/L3 注入的上下文逐渐过期、一致性漂移。

**记忆闭环**补齐写后沉淀：每章生成后 LLM 自动提取结构化信息写回 `StoryState`，下次写作前 `mem_working_memory` 拿到最新数据。

## 2. 架构

```
写前（mem_working_memory — 已有）
  L1(3章全文) / L2(50章摘要) / L3(世界观+角色+剧情线)
  → 从 StoryState 读取最新数据 → 注入 prompt
        ↓
  场景生成（scene_writer — 已有）
        ↓
写后（mem_sedimentation — 新增）
  extract_light() 每章 → extract_deep() 每10章
  → 解析 + 校验 + 去重 → 写回 StoryState → 保存
        ↓
  下次写前注入拿到新鲜数据 ✅
```

## 3. 改动清单

### 3.1 `core/base_skill.py` — 新增生命周期钩子

```python
def on_after_chapter_complete(self, chapter_id: int, full_text: str) -> None:
    """整章生成完毕、合并落盘后触发。用于沉淀/追读力/质量评分。"""
    pass
```

### 3.2 `scene_writer.py` — 触发新钩子

章节合并落盘后，调用：

```python
from core.event_bus import event_bus
event_bus.emit("on_after_chapter_complete", chapter_id, full_chapter_text)
```

### 3.3 `utils/sedimentation.py` — 沉淀提取工具库（新建）

两个 prompt 模板 + 两个解析函数 + 数据类：

| 函数 | 频率 | 提取内容 |
|------|------|---------|
| `extract_light(full_text, llm)` → `LightExtract` | 每章 | 角色状态变更、角色认知增量、伏笔种/收/推进、剧情推进、新信息披露 |
| `extract_deep(full_text, llm, story_state)` → `DeepExtract` | 每 10 章 | +情绪节拍走势、章末悬念质量、角色弧光评估、节奏诊断、去AI味检测 |

**Prompt 要求**：
- 输出纯 JSON，不做额外描述
- 不确定字段留空，不编造
- 角色状态变更格式：`{char_id: {field: new_value}}`
- 伏笔推进区分"真推进"和"假提及"

**去重**：TF-IDF 余弦相似度（纯 Python，零外部依赖）对候选摘要与已有数据做检测，> 0.85 不写入。后续可升级 BM25。

**校验**：JSON 解析 + 字段 schema 校验，失败则丢弃并记 warning，不阻塞生成。

### 3.4 `skills/mem_sedimentation/skill.py` — 沉淀 Skill（新建）

```python
class MemSedimentationSkill(BaseSkill):
    def on_after_chapter_complete(self, chapter_id, full_text):
        llm = self.context.get_shared("llm_client")
        if not llm:
            return  # 无 LLM 客户端则跳过，不阻塞生成
        
        story_state = self.context.get_shared("story_state")
        
        # 1. 精简提取（始终执行）
        try:
            light = extract_light(full_text, llm)
            if not _is_duplicate(light, story_state):
                _apply_light(light, story_state, chapter_id)
        except Exception as e:
            print(f"[mem_sedimentation] 轻量提取失败(ch{chapter_id}): {e}")
        
        # 2. 深度提取（每10章）
        if chapter_id % 10 == 0:
            try:
                deep = extract_deep(full_text, llm, story_state)
                _apply_deep(deep, story_state, chapter_id)
            except Exception as e:
                print(f"[mem_sedimentation] 深度提取失败(ch{chapter_id}): {e}")
        
        # 3. 持久化
        base_path = Path(self.context.workspace.workspace_root) / ".novel" / "story_state.json"
        save_story_state_sharded(story_state, base_path)
```

### 3.5 `skills/mem_working_memory/skill.py` — 升级记忆注入（已有，修改）

L3 语义记忆注入时新增 `[角色已知信息]` 块，从 `Character.knowledge` 读取：

```python
# 新增：认知状态注入
knowledge = []
for c in main_chars:
    if c.knowledge:
        knowledge.append(f"  {c.full_name}已知: {', '.join(c.knowledge[-10:])}")
if knowledge:
    parts.append("\n[角色已知信息]\n" + "\n".join(knowledge))
```

## 4. 数据模型（LightExtract）

```python
@dataclass
class LightExtract:
    character_state_changes: dict       # {char_id: {field: new_value}}
    character_knowledge_gained: dict    # {char_id: [facts_learned]}
    foreshadowing_planted: list         # [{text, confidence}]
    foreshadowing_resolved: list        # [{text, matched_plant, confidence}]
    foreshadowing_advancements: dict    # {hook_id: {chapter, progress, is_real}}
    plot_advances: list                 # [description]
    new_information: list               # [description]

@dataclass
class DeepExtract:
    emotional_arc_trend: str            # 10章情绪走势描述
    hook_quality_assessment: str        # 章末悬念质量评估
    character_arc_evaluation: dict      # {char_id: {stage, progress, notes}}
    pacing_diagnosis: str               # 节奏诊断（过快/过慢/失衡点）
    deai_concerns: list                 # 累积的AI写作痕迹
```

## 5. 容错设计

| 失败场景 | 处理 |
|---------|------|
| LLM 客户端不可用 | 静默跳过，不阻塞生成 |
| JSON 解析失败 | 丢弃当次提取，记 warning |
| JSON schema 校验失败 | 丢弃当次提取，记 warning |
| 网络超时 | 捕获异常，跳过当次提取 |
| BM25 去重判断相似度 > 0.85 | 跳过该条，不写入 |
| 磁盘写入失败 | 保留 .bak 回滚，记 error |

**核心原则**：沉淀失败永远不影响生成主流程。

## 6. `ChapterState` 字段映射

提取结果写回 `ChapterState` 已有字段：

| 提取字段 | 写入字段 |
|---------|---------|
| `plot_advances` | `ChapterState.plot_advances` |
| `new_information` | `ChapterState.new_information` |
| `foreshadowing_planted` | `ChapterState.foreshadowing_planted` |
| `foreshadowing_resolved` | `ChapterState.foreshadowing_resolved` |
| `character_state_changes` | `Character.{field}` |
| `character_knowledge_gained` | `Character.knowledge` (append) |
| `foreshadowing_advancements` | `PlotThread.milestones` (append) |

## 7. 文件清单

| 文件 | 操作 | 预估行数 |
|------|------|---------|
| `core/base_skill.py` | 修改 | +6 |
| `scene_writer.py` | 修改 | +4 |
| `utils/sedimentation.py` | 新建 | ~250 |
| `skills/mem_sedimentation/skill.py` | 新建 | ~80 |
| `skills/mem_working_memory/skill.py` | 修改 | +15 |
| **合计** | | **~355 行** |

## 8. 验收标准

1. 生成 3 章后，第 4 章 prompt 注入包含前 3 章的沉淀数据
2. 角色位置/情绪变更在第 N+1 章 prompt 中体现
3. 伏笔种下后，在第 N+1 章 prompt 中标记为"未回收"
4. 第 10 章生成后，StoryState 中包含深度提取的情绪走势和节奏诊断
5. 提取失败时生成流程不受影响
6. BM25 去重生效，重复信息不写入
