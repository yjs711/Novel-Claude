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
    if not LIGHT_REQUIRED_FIELDS.issubset(data.keys()):
        missing = LIGHT_REQUIRED_FIELDS - set(data.keys())
        print(f"  [!] LightExtract 缺少字段: {missing}")
        return None
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
        print(f"  [!] LightExtract 构造失败: {e}")
        return None


def validate_deep_extract(data: dict) -> Optional[DeepExtract]:
    """Validate and construct DeepExtract. Returns None if invalid."""
    if not isinstance(data, dict):
        return None
    if not DEEP_REQUIRED_FIELDS.issubset(data.keys()):
        missing = DEEP_REQUIRED_FIELDS - set(data.keys())
        print(f"  [!] DeepExtract 缺少字段: {missing}")
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
        print(f"  [!] DeepExtract 构造失败: {e}")
        return None


# ── TF-IDF dedup (pure Python, zero external deps) ──────────────────────────

def _tokenize(text: str) -> List[str]:
    """Simple Chinese-aware tokenizer: split on whitespace + punctuation."""
    text = re.sub(r'[，。！？、；：""''（）\n\r\t]', ' ', text)
    return [t for t in text.split() if len(t) > 1]


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


def _cosine_similarity(a: str, b: str) -> float:
    """Cosine similarity between two strings using TF-IDF."""
    if not a.strip() or not b.strip():
        return 0.0
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


def extract_light(full_text: str) -> str:
    """Build light extraction prompt. Returns the prompt string."""
    truncated = full_text[:12000] if len(full_text) > 12000 else full_text
    return LIGHT_EXTRACTION_PROMPT.replace("{chapter_text}", truncated)


def extract_deep(full_text: str, story_context: str, chapter_context: str) -> str:
    """Build deep extraction prompt. Returns the prompt string."""
    truncated = full_text[:12000] if len(full_text) > 12000 else full_text
    return DEEP_EXTRACTION_PROMPT.format(
        story_context=story_context[:3000],
        chapter_context=chapter_context[:5000],
        chapter_text=truncated,
    )


def run_light_extraction(full_text: str, llm_call) -> Optional[LightExtract]:
    """Run complete light extraction pipeline: prompt → LLM → parse → validate."""
    prompt = extract_light(full_text)
    try:
        response = llm_call(prompt)
        data = _parse_json_response(response)
        if data is None:
            print("  [!] LightExtract: JSON 解析失败")
            return None
        result = validate_light_extract(data)
        if result is None:
            print("  [!] LightExtract: Schema 校验失败")
        return result
    except Exception as e:
        print(f"  [!] LightExtract: LLM 调用异常: {e}")
        return None


def run_deep_extraction(full_text: str, story_context: str, chapter_context: str, llm_call) -> Optional[DeepExtract]:
    """Run complete deep extraction pipeline."""
    prompt = extract_deep(full_text, story_context, chapter_context)
    try:
        response = llm_call(prompt)
        data = _parse_json_response(response)
        if data is None:
            print("  [!] DeepExtract: JSON 解析失败")
            return None
        result = validate_deep_extract(data)
        if result is None:
            print("  [!] DeepExtract: Schema 校验失败")
        return result
    except Exception as e:
        print(f"  [!] DeepExtract: LLM 调用异常: {e}")
        return None
