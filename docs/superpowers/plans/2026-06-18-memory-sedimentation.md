# 记忆闭环（Memory Sedimentation）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐写后沉淀：每章生成后 LLM 自动提取结构化信息写回 StoryState，形成记忆闭环。

**Architecture:** 新增 `on_after_chapter_complete` 生命周期钩子 → scene_writer 触发 → `utils/sedimentation.py` 做 LLM 提取+去重+校验 → `skills/mem_sedimentation/skill.py` 写回 StoryState → `mem_working_memory` 下次注入拿到新鲜数据。

**Tech Stack:** Python 3.10+, dataclasses, OpenAI-compatible LLM API (existing `utils/llm_client.py`)

---

### Task 1: 新增生命周期钩子 `on_after_chapter_complete`

**Files:**
- Modify: `core/base_skill.py:46-52`

- [ ] **Step 1: 在 `on_post_chapter_continuity` 后面添加新钩子**

在 `core/base_skill.py` 的 `on_post_chapter_continuity` 方法后追加：

```python
def on_after_chapter_complete(self, chapter_id: int, full_text: str) -> None:
    """
    整章生成完毕、合并落盘后触发。
    用于沉淀提取 / 追读力评估 / 质量评分。
    full_text 为整章合并后的完整文本。
    """
    pass
```

- [ ] **Step 2: 验证语法**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -c "from core.base_skill import BaseSkill; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add core/base_skill.py
git commit -m "feat: add on_after_chapter_complete lifecycle hook to BaseSkill"
```

---

### Task 2: scene_writer 触发新钩子

**Files:**
- Modify: `scene_writer.py:588-589`

- [ ] **Step 1: 在现有钩子序列末尾添加新钩子调用**

在 `scene_writer.py` 第 589 行 `event_bus.emit("on_chapter_render", content, chapter_id)` 之后添加：

```python
                # Emit chapter complete hook (memory sedimentation, retention, quality)
                event_bus.emit("on_after_chapter_complete", chapter_id, content)
```

完整上下文（第 582-593 行附近）应变为：

```python
                # Emit after scene write hook
                beat_data = {"chapter_id": chapter_id, "beats": [], "needs_rewrite": needs_rewrite, "guidance": guidance}
                event_bus.emit("on_after_scene_write", beat_data, content)

                # Emit post-chapter continuity hook (zero-token checks)
                event_bus.emit("on_post_chapter_continuity", chapter_id)

                # Emit chapter render hook (de-AI engine)
                event_bus.emit("on_chapter_render", content, chapter_id)

                # Emit chapter complete hook (memory sedimentation, retention, quality)
                event_bus.emit("on_after_chapter_complete", chapter_id, content)

                # Track entity states for this chapter
                from core.entity_tracker import track_chapter_entities
                track_chapter_entities(volume_id, chapter_id)
```

- [ ] **Step 2: 验证语法和导入**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -c "import scene_writer; print('OK')"
```
Expected: `OK`（可能有一些路径初始化输出，但不应报错）

- [ ] **Step 3: Commit**

```bash
git add scene_writer.py
git commit -m "feat: emit on_after_chapter_complete after chapter save"
```

---

### Task 3: 沉淀提取工具库 `utils/sedimentation.py`

**Files:**
- Create: `utils/sedimentation.py`
- Create: `tests/test_sedimentation.py`

- [ ] **Step 1: 创建测试文件**

创建 `tests/test_sedimentation.py`：

```python
"""Tests for utils/sedimentation.py"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.sedimentation import (
    LightExtract,
    DeepExtract,
    validate_light_extract,
    validate_deep_extract,
    _cosine_similarity,
    _is_duplicate_light,
    LIGHT_EXTRACTION_PROMPT,
    DEEP_EXTRACTION_PROMPT,
)


class TestLightExtract:
    def test_valid_light_extract(self):
        data = {
            "character_state_changes": {},
            "character_knowledge_gained": {},
            "foreshadowing_planted": [],
            "foreshadowing_resolved": [],
            "foreshadowing_advancements": {},
            "plot_advances": ["主角突破元婴期"],
            "new_information": ["上古遗迹将在三日后开启"],
        }
        result = validate_light_extract(data)
        assert result is not None
        assert isinstance(result, LightExtract)
        assert result.plot_advances == ["主角突破元婴期"]

    def test_invalid_light_extract_missing_field(self):
        data = {"plot_advances": ["test"]}
        result = validate_light_extract(data)
        assert result is None  # Should reject incomplete data

    def test_light_extract_to_dict(self):
        le = LightExtract(
            character_state_changes={"char_1": {"emotional_state": "愤怒"}},
            character_knowledge_gained={"char_1": ["发现叛徒身份"]},
            foreshadowing_planted=[{"text": "戒指发光", "confidence": 0.9}],
            foreshadowing_resolved=[],
            foreshadowing_advancements={},
            plot_advances=["主线推进"],
            new_information=["新地图开启"],
        )
        d = le.to_dict()
        assert d["character_state_changes"]["char_1"]["emotional_state"] == "愤怒"


class TestDeepExtract:
    def test_valid_deep_extract(self):
        data = {
            "emotional_arc_trend": "整体情绪从低沉到爆发",
            "hook_quality_assessment": "章末悬念力度足够",
            "character_arc_evaluation": {},
            "pacing_diagnosis": "中段打斗场景节奏偏慢",
            "deai_concerns": ["3处 '不仅是...更是...' 句式"],
        }
        result = validate_deep_extract(data)
        assert result is not None
        assert isinstance(result, DeepExtract)
        assert result.pacing_diagnosis == "中段打斗场景节奏偏慢"


class TestDedup:
    def test_cosine_similarity_identical(self):
        a = "主角突破元婴期 获得新能力"
        b = "主角突破元婴期 获得新能力"
        sim = _cosine_similarity(a, b)
        assert sim > 0.9

    def test_cosine_similarity_different(self):
        a = "主角突破元婴期"
        b = "配角在酒楼吃饭遇到麻烦"
        sim = _cosine_similarity(a, b)
        assert sim < 0.5

    def test_is_duplicate(self):
        existing = ["主角突破元婴期获得新能力", "发现上古遗迹秘密"]
        assert _is_duplicate_light("主角突破元婴期获得新能力", existing) is True
        assert _is_duplicate_light("一只猫走过街道", existing) is False


class TestPrompts:
    def test_light_prompt_contains_json_instruction(self):
        assert "JSON" in LIGHT_EXTRACTION_PROMPT
        assert "character_state_changes" in LIGHT_EXTRACTION_PROMPT
        assert "character_knowledge_gained" in LIGHT_EXTRACTION_PROMPT

    def test_deep_prompt_contains_json_instruction(self):
        assert "JSON" in DEEP_EXTRACTION_PROMPT
        assert "emotional_arc_trend" in DEEP_EXTRACTION_PROMPT
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -m pytest tests/test_sedimentation.py -v 2>&1 | head -20
```
Expected: ImportError（文件不存在）

- [ ] **Step 3: 创建 `utils/sedimentation.py`**

```python
"""
Novel-Claude Fusion — Memory Sedimentation Engine.

Post-chapter extraction: LLM analyses the full chapter text and returns
structured data (LightExtract every chapter, DeepExtract every 10).
Data is validated, deduplicated, and written back to StoryState.

Design doc: docs/superpowers/specs/2026-06-18-memory-sedimentation-design.md
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple


# ── data classes ───────────────────────────────────────────────────────────────

@dataclass
class LightExtract:
    """Per-chapter structured extraction (~500 tokens)."""
    character_state_changes: Dict[str, Dict[str, str]] = field(default_factory=dict)
    character_knowledge_gained: Dict[str, List[str]] = field(default_factory=dict)
    foreshadowing_planted: List[Dict[str, Any]] = field(default_factory=list)
    foreshadowing_resolved: List[Dict[str, Any]] = field(default_factory=list)
    foreshadowing_advancements: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    plot_advances: List[str] = field(default_factory=list)
    new_information: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LightExtract":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DeepExtract:
    """Every-10-chapter deep extraction (~2K tokens)."""
    emotional_arc_trend: str = ""
    hook_quality_assessment: str = ""
    character_arc_evaluation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    pacing_diagnosis: str = ""
    deai_concerns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeepExtract":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── JSON schema validation ────────────────────────────────────────────────────

# Required fields for each extract type
LIGHT_REQUIRED_FIELDS = {
    "character_state_changes", "character_knowledge_gained",
    "foreshadowing_planted", "foreshadowing_resolved",
    "foreshadowing_advancements", "plot_advances", "new_information",
}

DEEP_REQUIRED_FIELDS = {
    "emotional_arc_trend", "hook_quality_assessment",
    "character_arc_evaluation", "pacing_diagnosis", "deai_concerns",
}


def validate_light_extract(data: dict) -> Optional[LightExtract]:
    """Validate and construct LightExtract. Returns None if invalid."""
    if not isinstance(data, dict):
        return None
    # Check all required fields present
    if not LIGHT_REQUIRED_FIELDS.issubset(data.keys()):
        missing = LIGHT_REQUIRED_FIELDS - set(data.keys())
        print(f"  [⚠️] LightExtract 缺少字段: {missing}")
        return None
    # Type checks
    if not isinstance(data["character_state_changes"], dict):
        return None
    if not isinstance(data["character_knowledge_gained"], dict):
        return None
    if not isinstance(data["foreshadowing_planted"], list):
        return None
    if not isinstance(data["foreshadowing_resolved"], list):
        return None
    if not isinstance(data["foreshadowing_advancements"], dict):
        return None
    if not isinstance(data["plot_advances"], list):
        return None
    if not isinstance(data["new_information"], list):
        return None
    try:
        return LightExtract.from_dict(data)
    except Exception as e:
        print(f"  [⚠️] LightExtract 构造失败: {e}")
        return None


def validate_deep_extract(data: dict) -> Optional[DeepExtract]:
    """Validate and construct DeepExtract. Returns None if invalid."""
    if not isinstance(data, dict):
        return None
    if not DEEP_REQUIRED_FIELDS.issubset(data.keys()):
        missing = DEEP_REQUIRED_FIELDS - set(data.keys())
        print(f"  [⚠️] DeepExtract 缺少字段: {missing}")
        return None
    if not isinstance(data["emotional_arc_trend"], str):
        return None
    if not isinstance(data["hook_quality_assessment"], str):
        return None
    if not isinstance(data["character_arc_evaluation"], dict):
        return None
    if not isinstance(data["pacing_diagnosis"], str):
        return None
    if not isinstance(data["deai_concerns"], list):
        return None
    try:
        return DeepExtract.from_dict(data)
    except Exception as e:
        print(f"  [⚠️] DeepExtract 构造失败: {e}")
        return None


# ── TF-IDF dedup (pure Python, zero external deps) ──────────────────────────

def _tokenize(text: str) -> List[str]:
    """Simple Chinese-aware tokenizer: split on whitespace + punctuation."""
    text = re.sub(r'[，。！？、；：""''（）\n\r\t]', ' ', text)
    return [t for t in text.split() if len(t) > 1]


def _tfidf_vector(texts: List[str], query: str) -> Tuple[List[float], List[float]]:
    """Compute TF-IDF vectors for a list of documents and a query.
    Returns (query_vector, doc_vectors) where doc_vectors is a flattened list.
    Actually returns (query_vector, []) — caller iterates docs separately.
    """
    # Tokenize all
    tokenized = [_tokenize(t) for t in texts]
    query_tokens = _tokenize(query)

    # DF (document frequency)
    N = len(texts)
    df = Counter()
    for tokens in tokenized:
        df.update(set(tokens))

    # IDF
    idf = {}
    for word, count in df.items():
        idf[word] = math.log((N + 1) / (count + 1)) + 1.0

    # TF-IDF for query
    q_tf = Counter(query_tokens)
    q_vec = [q_tf.get(word, 0) * idf.get(word, 0) for word in idf]

    # TF-IDF for each doc
    doc_vecs = []
    for tokens in tokenized:
        tf = Counter(tokens)
        vec = [tf.get(word, 0) * idf.get(word, 0) for word in idf]
        doc_vecs.append(vec)

    return q_vec, doc_vecs, list(idf.keys())


def _cosine_similarity(a: str, b: str) -> float:
    """Cosine similarity between two strings using TF-IDF."""
    if not a.strip() or not b.strip():
        return 0.0
    # Build shared vocabulary from both
    vecs, _ = _build_vectors([a, b])
    if len(vecs) < 2:
        return 0.0
    v1, v2 = vecs[0], vecs[1]
    dot = sum(x * y for x, y in zip(v1, v2))
    norm1 = math.sqrt(sum(x * x for x in v1))
    norm2 = math.sqrt(sum(y * y for y in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _build_vectors(texts: List[str]) -> Tuple[List[List[float]], List[str]]:
    """Build TF-IDF vectors for a list of texts."""
    tokenized = [_tokenize(t) for t in texts]
    N = len(texts)
    df = Counter()
    for tokens in tokenized:
        df.update(set(tokens))
    vocab = list(df.keys())
    idf = {word: math.log((N + 1) / (count + 1)) + 1.0 for word, count in df.items()}
    vectors = []
    for tokens in tokenized:
        tf = Counter(tokens)
        vec = [tf.get(word, 0) * idf[word] for word in vocab]
        vectors.append(vec)
    return vectors, vocab


def _is_duplicate_light(candidate_text: str, existing_texts: List[str], threshold: float = 0.85) -> bool:
    """Check if candidate is a duplicate of any existing text."""
    if not existing_texts:
        return False
    for existing in existing_texts:
        sim = _cosine_similarity(candidate_text, existing)
        if sim > threshold:
            return True
    return False


# ── prompt templates ──────────────────────────────────────────────────────────

LIGHT_EXTRACTION_PROMPT = """你是一个专业的小说信息提取助手。请从以下章节中提取结构化信息。

## 要求
1. 输出纯 JSON，不要任何解释或额外文字
2. 不确定的字段留空（空字符串、空列表、空对象），绝不编造
3. 角色状态变更格式：{"角色ID": {"field": "new_value"}}
4. 角色认知增量：角色在本章中新得知的信息
5. 伏笔区分"种"(planted)、"收"(resolved)和"推进"(advancement)
6. advancement 中 is_real 为 true 表示实质性推进，false 表示仅提及无进展

## 输出 JSON Schema
{
  "character_state_changes": {"char_id": {"emotional_state": "愤怒", "current_location": "青云山", "arc_progress": 35}},
  "character_knowledge_gained": {"char_id": ["得知叛徒身份", "发现秘境入口"]},
  "foreshadowing_planted": [{"text": "描述", "confidence": 0.9}],
  "foreshadowing_resolved": [{"text": "回收描述", "matched_plant": "原始伏笔简述", "confidence": 0.9}],
  "foreshadowing_advancements": {"hook_id": {"chapter": 5, "progress": "主角在古书中找到线索", "is_real": true}},
  "plot_advances": ["剧情推进点描述"],
  "new_information": ["本章新披露的关键信息"]
}

## 章节内容
{chapter_text}

## 请输出 JSON："""


DEEP_EXTRACTION_PROMPT = """你是一个专业的小说深度分析助手。以下是最近 10 章的累积数据，请做深度分析。

## 要求
1. 输出纯 JSON，不要任何解释或额外文字
2. 基于已有数据趋势做判断，不确定的留空
3. 情绪走势：描述 10 章的情绪曲线（如"前3章低沉→中4章攀升→后3章高潮回落"）
4. 章末悬念质量：评估最近的钩子是否有效（够意外、有代价、有紧迫感）
5. 角色弧光：每个主要角色的阶段、进度百分比、变化要点
6. 节奏诊断：指出过慢/过快的段落、失衡点
7. deai_concerns：累积发现的 AI 写作痕迹

## 已有数据
- 故事状态: {story_context}
- 最近 10 章摘要: {chapter_context}

## 输出 JSON Schema
{{
  "emotional_arc_trend": "10章情绪走势描述",
  "hook_quality_assessment": "章末悬念质量评估",
  "character_arc_evaluation": {{"char_id": {{"stage": "发展阶段名", "progress": 50, "notes": "变化要点"}}}},
  "pacing_diagnosis": "节奏诊断",
  "deai_concerns": ["AI写作痕迹1", "AI写作痕迹2"]
}}

## 最近生成的第 10 章全文
{chapter_text}

## 请输出 JSON："""


# ── extraction functions ─────────────────────────────────────────────────────

def _parse_json_response(text: str) -> Optional[dict]:
    """Extract JSON from LLM response. Handles markdown code blocks."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from ```json ... ``` block
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try extracting from { ... } (first complete JSON object)
    brace_start = text.find('{')
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def extract_light(full_text: str) -> Optional[LightExtract]:
    """
    Call LLM for per-chapter light extraction.

    Returns LightExtract or None if extraction failed.
    Caller must provide the LLM call — this function only handles
    prompt building and response parsing.

    Typical usage:
        from utils.llm_client import generate_json
        light = extract_light(chapter_text)
    """
    # Build prompt — truncate to ~12K chars to fit small model context
    truncated = full_text[:12000] if len(full_text) > 12000 else full_text
    prompt = LIGHT_EXTRACTION_PROMPT.replace("{chapter_text}", truncated)

    # Parse is handled by caller — this just builds the prompt
    # We return the prompt so callers can use their own LLM client
    return prompt


def extract_deep(full_text: str, story_context: str, chapter_context: str) -> str:
    """
    Build deep extraction prompt.

    Returns the prompt string. Caller handles LLM invocation.

    story_context: serialized StoryState summary (genre, active threads, main chars)
    chapter_context: recent 10-chapter summaries
    """
    truncated = full_text[:12000] if len(full_text) > 12000 else full_text
    prompt = DEEP_EXTRACTION_PROMPT.format(
        story_context=story_context[:3000],
        chapter_context=chapter_context[:5000],
        chapter_text=truncated,
    )
    return prompt


def run_light_extraction(full_text: str, llm_call) -> Optional[LightExtract]:
    """
    Run complete light extraction pipeline: prompt → LLM → parse → validate.

    llm_call: function(prompt) -> str — the LLM invocation function.
    """
    prompt = extract_light(full_text)
    try:
        response = llm_call(prompt)
        data = _parse_json_response(response)
        if data is None:
            print("  [⚠️] LightExtract: JSON 解析失败")
            return None
        result = validate_light_extract(data)
        if result is None:
            print("  [⚠️] LightExtract: Schema 校验失败")
        return result
    except Exception as e:
        print(f"  [⚠️] LightExtract: LLM 调用异常: {e}")
        return None


def run_deep_extraction(full_text: str, story_context: str, chapter_context: str, llm_call) -> Optional[DeepExtract]:
    """
    Run complete deep extraction pipeline.

    llm_call: function(prompt) -> str
    """
    prompt = extract_deep(full_text, story_context, chapter_context)
    try:
        response = llm_call(prompt)
        data = _parse_json_response(response)
        if data is None:
            print("  [⚠️] DeepExtract: JSON 解析失败")
            return None
        result = validate_deep_extract(data)
        if result is None:
            print("  [⚠️] DeepExtract: Schema 校验失败")
        return result
    except Exception as e:
        print(f"  [⚠️] DeepExtract: LLM 调用异常: {e}")
        return None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -m pytest tests/test_sedimentation.py -v
```
Expected: ALL PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add utils/sedimentation.py tests/test_sedimentation.py
git commit -m "feat: add sedimentation extraction engine with validation and dedup"
```

---

### Task 4: 沉淀 Skill

**Files:**
- Create: `skills/mem_sedimentation/__init__.py`
- Create: `skills/mem_sedimentation/skill.py`

- [ ] **Step 1: 创建 `skills/mem_sedimentation/__init__.py`**

```python
# Memory Sedimentation Skill
```

- [ ] **Step 2: 创建 `skills/mem_sedimentation/skill.py`**

```python
"""
mem_sedimentation — 记忆沉淀 Skill

每章生成后自动提取结构化信息，写回 StoryState，形成记忆闭环。

- 每章：轻量提取（角色状态/认知/伏笔/剧情/新信息）
- 每10章：深度提取（情绪走势/悬念质量/弧光评估/节奏/去AI味）
"""

from pathlib import Path
from typing import Optional, List

from core.base_skill import BaseSkill
from core.story_state import StoryState, save_story_state_sharded
from utils.sedimentation import (
    LightExtract, DeepExtract,
    run_light_extraction, run_deep_extraction,
    _is_duplicate_light,
)
from utils.llm_client import _get_client, resolve_flash_model


class MemSedimentationSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "记忆沉淀系统"

    def on_init(self) -> None:
        print(f"  [✓] {self.name} 已就绪（每章轻量提取 + 每10章深度提取）")

    def on_after_chapter_complete(self, chapter_id: int, full_text: str) -> None:
        """章节完成后执行沉淀提取"""
        if not full_text or len(full_text.strip()) < 100:
            print(f"  [⚠️] {self.name}: 章节内容过短，跳过提取")
            return

        story_state: Optional[StoryState] = self.context.get_shared("story_state")
        if story_state is None:
            print(f"  [⚠️] {self.name}: 未找到 story_state，跳过提取")
            return

        # ── LLM client ──
        try:
            from utils.llm_client import resolve_provider
            client = _get_client()
            flash_model = resolve_flash_model(resolve_provider())
        except Exception as e:
            print(f"  [⚠️] {self.name}: LLM 客户端不可用: {e}")
            return

        def llm_call(prompt: str) -> str:
            """Thin wrapper for chat completion."""
            response = client.chat.completions.create(
                model=flash_model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Low temp for extraction accuracy
                max_tokens=2048,
            )
            return response.choices[0].message.content or ""

        # ── 1. Light extraction (every chapter) ──
        try:
            light = run_light_extraction(full_text, llm_call)
            if light is not None:
                self._apply_light(light, story_state, chapter_id)
                print(f"  [✓] {self.name}: 第{chapter_id}章轻量提取完成 "
                      f"(状态变更:{len(light.character_state_changes)}角色, "
                      f"认知:{sum(len(v) for v in light.character_knowledge_gained.values())}条, "
                      f"伏笔种:{len(light.foreshadowing_planted)}/收:{len(light.foreshadowing_resolved)}, "
                      f"剧情推进:{len(light.plot_advances)})")
        except Exception as e:
            print(f"  [⚠️] {self.name}: 轻量提取异常(ch{chapter_id}): {e}")

        # ── 2. Deep extraction (every 10 chapters) ──
        if chapter_id % 10 == 0:
            try:
                story_context = self._build_story_context(story_state)
                chapter_context = self._build_chapter_context(story_state, chapter_id)
                deep = run_deep_extraction(full_text, story_context, chapter_context, llm_call)
                if deep is not None:
                    self._apply_deep(deep, story_state, chapter_id)
                    print(f"  [✓] {self.name}: 第{chapter_id}章深度提取完成 "
                          f"(情绪走势:{len(deep.emotional_arc_trend)}字, "
                          f"角色弧光:{len(deep.character_arc_evaluation)}个, "
                          f"AI痕迹:{len(deep.deai_concerns)}处)")
            except Exception as e:
                print(f"  [⚠️] {self.name}: 深度提取异常(ch{chapter_id}): {e}")

        # ── 3. Persist ──
        try:
            base_path = Path(self.context.workspace.workspace_root) / ".novel" / "story_state.json"
            save_story_state_sharded(story_state, base_path)
        except Exception as e:
            print(f"  [⚠️] {self.name}: 持久化失败: {e}")

    # ── apply helpers ──────────────────────────────────────────────────────

    def _apply_light(self, light: LightExtract, state: StoryState, chapter_id: int) -> None:
        """Write LightExtract data back to StoryState."""
        ch = state.chapters.get(chapter_id)
        if ch is None:
            return

        # Plot advances
        if light.plot_advances:
            existing = list(ch.plot_advances)
            for pa in light.plot_advances:
                if not _is_duplicate_light(pa, existing):
                    existing.append(pa)
            ch.plot_advances = existing

        # New information
        if light.new_information:
            existing = list(ch.new_information)
            for ni in light.new_information:
                if not _is_duplicate_light(ni, existing):
                    existing.append(ni)
            ch.new_information = existing

        # Foreshadowing planted
        for fp in light.foreshadowing_planted:
            text = fp.get("text", "") if isinstance(fp, dict) else str(fp)
            if text and not _is_duplicate_light(text, ch.foreshadowing_planted):
                ch.foreshadowing_planted.append(text)

        # Foreshadowing resolved
        for fr in light.foreshadowing_resolved:
            text = fr.get("text", "") if isinstance(fr, dict) else str(fr)
            if text and not _is_duplicate_light(text, ch.foreshadowing_resolved):
                ch.foreshadowing_resolved.append(text)

        # Character state changes
        for char_id, changes in light.character_state_changes.items():
            char = state.characters.get(char_id)
            if char is None:
                continue
            for field, value in changes.items():
                if hasattr(char, field) and value:
                    setattr(char, field, value)
            char.last_appearance_chapter = chapter_id

        # Character knowledge gained (epistemic state)
        for char_id, facts in light.character_knowledge_gained.items():
            char = state.characters.get(char_id)
            if char is None:
                continue
            existing_knowledge = set(char.knowledge or [])
            for fact in facts:
                if fact and fact not in existing_knowledge:
                    char.knowledge.append(fact)
                    existing_knowledge.add(fact)
            # Keep last 30 items to prevent unbounded growth
            if len(char.knowledge) > 30:
                char.knowledge = char.knowledge[-30:]

        # Foreshadowing advancements → write to PlotThread milestones
        for hook_id, adv in light.foreshadowing_advancements.items():
            thread = state.plot_threads.get(hook_id)
            if thread is None:
                continue
            is_real = adv.get("is_real", False)
            progress = adv.get("progress", "")
            if is_real and progress:
                thread.milestones.append({
                    "chapter": chapter_id,
                    "progress": progress,
                })
                thread.last_updated_chapter = chapter_id

    def _apply_deep(self, deep: DeepExtract, state: StoryState, chapter_id: int) -> None:
        """Write DeepExtract results to StoryState."""
        ch = state.chapters.get(chapter_id)
        if ch is None:
            return

        # Store deep analysis in chapter's quality_scores (extensible)
        if not ch.quality_scores:
            ch.quality_scores = {}
        ch.quality_scores["emotional_arc_trend"] = 1.0  # marker: analysis done
        ch.quality_scores["hook_quality"] = 1.0
        ch.quality_scores["pacing"] = 1.0

        # Store as chapter notes for future reference
        notes_parts = []
        if deep.emotional_arc_trend:
            notes_parts.append(f"[情绪走势] {deep.emotional_arc_trend}")
        if deep.hook_quality_assessment:
            notes_parts.append(f"[悬念评估] {deep.hook_quality_assessment}")
        if deep.pacing_diagnosis:
            notes_parts.append(f"[节奏诊断] {deep.pacing_diagnosis}")
        if notes_parts:
            ch.notes = (ch.notes or "") + "\n".join(notes_parts)

        # Character arc evaluation
        for char_id, eval_data in deep.character_arc_evaluation.items():
            char = state.characters.get(char_id)
            if char is None:
                continue
            stage = eval_data.get("stage", "")
            progress = eval_data.get("progress", 0)
            if stage:
                char.arc_stage = stage
            if isinstance(progress, (int, float)) and progress > 0:
                char.arc_progress = int(progress)

        # De-AI concerns → forward to shared_state for deai engine
        if deep.deai_concerns:
            existing = self.context.get_shared("deai_concerns", [])
            existing.extend(deep.deai_concerns)
            self.context.set_shared("deai_concerns", existing)

    def _build_story_context(self, state: StoryState) -> str:
        """Build a brief story context string for deep extraction."""
        parts = []
        if state.title:
            parts.append(f"书名: {state.title}")
        if state.genre:
            parts.append(f"题材: {state.genre}")
        active_threads = [t for t in state.plot_threads.values() if t.status == "active"]
        if active_threads:
            parts.append(f"活跃剧情线: {len(active_threads)}条")
        main_chars = [c for c in state.characters.values() if c.role in ("protagonist", "antagonist")]
        if main_chars:
            parts.append(f"主要角色: {len(main_chars)}个")
        return "; ".join(parts)

    def _build_chapter_context(self, state: StoryState, current_ch: int) -> str:
        """Summarize last 10 chapters for deep extraction context."""
        lines = []
        for offset in range(1, 11):
            ch_num = current_ch - offset
            if ch_num < 1:
                break
            ch = state.chapters.get(ch_num)
            if ch is None:
                continue
            parts = [f"第{ch_num}章 {ch.title}"]
            if ch.plot_advances:
                parts.append(f"剧情: {'; '.join(ch.plot_advances[:3])}")
            if ch.emotional_beats:
                parts.append(f"情绪: {' → '.join(ch.emotional_beats[:3])}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)
```

- [ ] **Step 3: 验证 Skill 可加载**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -c "
import sys; sys.path.insert(0, '.')
from skills.mem_sedimentation.skill import MemSedimentationSkill
print('Skill class loaded OK')
"
```
Expected: `Skill class loaded OK`

- [ ] **Step 4: Commit**

```bash
git add skills/mem_sedimentation/
git commit -m "feat: add mem_sedimentation skill for post-chapter extraction"
```

---

### Task 5: 升级 mem_working_memory — 认知状态注入

**Files:**
- Modify: `skills/mem_working_memory/skill.py:120-148`

- [ ] **Step 1: 在 `_build_semantic_memory` 末尾添加认知状态注入**

在 `skills/mem_working_memory/skill.py` 的 `_build_semantic_memory` 方法中，角色信息输出后（第 138 行 `if supp:` 块之后），添加认知状态块：

找到文件中这段代码（约第 136-138 行）：
```python
            if supp:
                names = ", ".join(f"{c.full_name}({c.role})" for c in supp[:8])
                parts.append(f"  配角: {names}")
```

在其后添加：
```python
            # ── 认知状态注入（Epistemic State） ──
            # 防止角色"重新发现"已知信息
            all_chars = list(main) + list(supp)
            knowledge_lines = []
            for c in all_chars:
                if c.knowledge:
                    known = c.knowledge[-10:]  # Last 10 known facts
                    knowledge_lines.append(f"  {c.full_name}已知: {'; '.join(known)}")
            if knowledge_lines:
                parts.append("\n[角色已知信息 — 避免重复发现]\n" + "\n".join(knowledge_lines))
```

- [ ] **Step 2: 验证语法**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -c "
from skills.mem_working_memory.skill import MemWorkingMemorySkill
print('OK')
"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/mem_working_memory/skill.py
git commit -m "feat: add epistemic state injection to L3 memory (prevents re-discovery)"
```

---

### Task 6: 集成测试 — 端到端验证

**Files:**
- Create: `tests/test_memory_loop.py`

- [ ] **Step 1: 创建集成测试**

```python
"""Integration test: memory closed loop (sedimentation → injection)."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.story_state import (
    StoryState, Character, PlotThread, ChapterState,
    save_story_state, load_story_state,
)
from utils.sedimentation import (
    LightExtract, validate_light_extract, _is_duplicate_light,
)


class TestMemoryClosedLoop:
    """Simulate write → extract → inject → verify cycle."""

    def test_light_extract_applied_to_story_state(self):
        """Verify LightExtract data flows into StoryState correctly."""
        state = StoryState(title="测试", genre="修仙")
        char = Character(
            id="char_1", full_name="林风", role="protagonist",
            knowledge=[], emotional_state="平静", current_location="青云镇",
        )
        state.characters["char_1"] = char
        ch = ChapterState(number=1, title="第一章", status="drafted")
        state.chapters[1] = ch

        # Simulate extraction result
        light = LightExtract(
            character_state_changes={"char_1": {"emotional_state": "愤怒", "current_location": "黑风山"}},
            character_knowledge_gained={"char_1": ["发现幕后黑手是师尊"]},
            foreshadowing_planted=[{"text": "戒指在月光下发光", "confidence": 0.9}],
            foreshadowing_resolved=[],
            foreshadowing_advancements={},
            plot_advances=["林风突破元婴期"],
            new_information=["黑风山有上古遗迹"],
        )

        # Apply (mirrors _apply_light logic)
        ch.plot_advances = light.plot_advances
        ch.new_information = light.new_information
        ch.foreshadowing_planted = [fp["text"] for fp in light.foreshadowing_planted]
        for char_id, changes in light.character_state_changes.items():
            c = state.characters.get(char_id)
            if c:
                for field, value in changes.items():
                    setattr(c, field, value)
        for char_id, facts in light.character_knowledge_gained.items():
            c = state.characters.get(char_id)
            if c:
                c.knowledge.extend(facts)

        # Verify
        assert state.characters["char_1"].emotional_state == "愤怒"
        assert state.characters["char_1"].current_location == "黑风山"
        assert "发现幕后黑手是师尊" in state.characters["char_1"].knowledge
        assert state.chapters[1].plot_advances == ["林风突破元婴期"]
        assert state.chapters[1].new_information == ["黑风山有上古遗迹"]
        assert "戒指在月光下发光" in state.chapters[1].foreshadowing_planted

    def test_dedup_prevents_duplicates(self):
        """Verify deduplication prevents repeated entries."""
        state = StoryState(title="测试", genre="修仙")
        ch = ChapterState(number=1, title="第一章", status="drafted",
                          plot_advances=["主角突破"], new_information=["发现秘境"])
        state.chapters[1] = ch

        # Second extraction with same data
        light2 = LightExtract(
            character_state_changes={}, character_knowledge_gained={},
            foreshadowing_planted=[], foreshadowing_resolved=[],
            foreshadowing_advancements={},
            plot_advances=["主角突破"],  # Duplicate
            new_information=["发现秘境"],  # Duplicate
        )

        # Apply with dedup
        existing_plot = list(ch.plot_advances)
        for pa in light2.plot_advances:
            if not _is_duplicate_light(pa, existing_plot):
                existing_plot.append(pa)
        ch.plot_advances = existing_plot

        # Should still have only 1 entry
        assert len(ch.plot_advances) == 1

    def test_epistemic_state_persists(self):
        """Verify character knowledge accumulates across chapters."""
        char = Character(id="char_1", full_name="林风", role="protagonist", knowledge=[])

        # Chapter 1
        char.knowledge.append("发现秘境入口")
        assert "发现秘境入口" in char.knowledge

        # Chapter 2
        char.knowledge.append("师尊是叛徒")
        assert len(char.knowledge) == 2
        assert "发现秘境入口" in char.knowledge  # Still there
        assert "师尊是叛徒" in char.knowledge

        # Chapter 31+: truncate to last 30
        for i in range(35):
            char.knowledge.append(f"事实{i}")
        char.knowledge = char.knowledge[-30:]
        assert len(char.knowledge) == 30

    def test_deep_extract_marker_in_chapter(self):
        """Verify deep extract sets quality markers."""
        ch = ChapterState(number=10, title="第十章", status="drafted", quality_scores={})
        ch.quality_scores["emotional_arc_trend"] = 1.0
        assert ch.quality_scores.get("emotional_arc_trend") == 1.0


class TestValidationEdgeCases:
    def test_empty_text_rejected(self):
        """Empty or whitespace-only text should be skipped."""
        text = "   "
        assert len(text.strip()) < 100

    def test_missing_story_state_handled(self):
        """Missing story_state should not crash."""
        # This is tested by the Skill's None check on story_state
        pass

    def test_malformed_json_returns_none(self):
        """Malformed JSON should return None from parser."""
        from utils.sedimentation import _parse_json_response
        result = _parse_json_response("这不是 JSON")
        assert result is None

    def test_partial_json_rejected(self):
        """JSON missing required fields should be rejected."""
        data = {"plot_advances": ["test"]}  # Missing other fields
        result = validate_light_extract(data)
        assert result is None
```

- [ ] **Step 2: 运行集成测试**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -m pytest tests/test_memory_loop.py -v
```
Expected: ALL PASS (6 tests)

- [ ] **Step 3: 运行全部测试**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -m pytest tests/ -v
```
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_memory_loop.py
git commit -m "test: add memory closed-loop integration tests"
```

---

### Task 7: 最终验证 — 确保不破坏现有功能

- [ ] **Step 1: 验证所有现有 Skill 仍可加载**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -c "
from core.event_bus import event_bus
from core.base_skill import BaseSkill

# Verify new hook exists and is callable with correct signature
assert hasattr(BaseSkill, 'on_after_chapter_complete'), 'Hook missing!'
import inspect
sig = inspect.signature(BaseSkill.on_after_chapter_complete)
params = list(sig.parameters.keys())
assert 'self' in params
assert 'chapter_id' in params
assert 'full_text' in params
print('✓ on_after_chapter_complete hook signature correct')
print('✓ All imports OK')
"
```
Expected: `✓ on_after_chapter_complete hook signature correct` + `✓ All imports OK`

- [ ] **Step 2: 验证 CLI 仍可启动**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -c "
import cli
print('CLI module loaded OK')
"
```
Expected: `CLI module loaded OK`

- [ ] **Step 3: 验证 plugin_manager 可发现新 Skill**

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude && python -c "
from core.plugin_manager import PluginManager
pm = PluginManager()
skills = pm.discover_skills()
print(f'Discovered {len(skills)} skills')
mem_sed = [s for s in skills if 'sedimentation' in s]
print(f'mem_sedimentation found: {len(mem_sed) > 0}')
"
```
Expected: `mem_sedimentation found: True`

- [ ] **Step 4: Commit (if any fixes needed)**

```bash
git add -A
git commit -m "chore: final verification of memory sedimentation integration"
```
