"""
章节后置分析引擎 — 用本地27B对已生成章节做结构审计
伏笔提取/因果链/冲突密度/爽点分布/节奏评估
"""
from __future__ import annotations

import json, re, time
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ForeshadowItem:
    """伏笔条目"""
    description: str          # 伏笔描述（≤20字）
    type: str                 # 类型：人物身世/功法秘密/势力伏笔/感情线/未解之谜/其他
    planted: bool = True      # True=新埋, False=本次回收
    target_chapter: int = 0   # 建议回收章号（新埋时）
    resolved_from: int = 0    # 从哪章埋的（回收时）


@dataclass
class SceneAnalysis:
    """单场景分析"""
    name: str                 # 场景名
    causality: str            # Therefore/But/AndThen/Coincidence
    conflict_level: int       # 1-10
    satisfaction_beat: str    # 爽点类型
    char_count: int           # 出场角色数


@dataclass
class ChapterAnalysis:
    """章节分析结果"""
    chapter_id: str = ""
    # 伏笔
    foreshadows_planted: list[ForeshadowItem] = field(default_factory=list)
    foreshadows_paid: list[ForeshadowItem] = field(default_factory=list)
    # 结构
    scenes: list[SceneAnalysis] = field(default_factory=list)
    causality_chain: str = ""        # 整章因果链概述
    # 节奏
    pacing_curve: str = ""           # 快→慢→快 / 慢→快→爆炸 / 平稳 / 拖沓
    tension_peak_chapter_position: str = ""  # 张力高峰在章的哪个位置
    # 评分
    dialogue_ratio_pct: int = 0      # 对话占比
    satisfaction_density: int = 0    # 爽点密度 (1-10)
    overall_score: int = 0           # 综合评分 (1-100)
    # 元数据
    summary: str = ""                # 一句话摘要
    suggestions: list[str] = field(default_factory=list)  # 改进建议
    raw_response: str = ""           # 模型原始输出（调试用）


# ── Prompt 模板 ──────────────────────────────────────────────────────

ANALYSIS_SYSTEM_PROMPT = """你是专业的网文编辑（"结构审计师"）。你的任务是分析已完成的章节，输出结构化诊断结果。

分析维度：
1. **伏笔管理** — 本章新埋了哪些伏笔？回收了之前的哪些伏笔？
   伏笔类型：人物身世/功法秘密/势力伏笔/感情线/未解之谜/其他
2. **场景因果链** — 按场景拆解，标注每个场景过渡的因果类型：
   - Therefore（前因→后果，强）
   - But（转折/意外，强）
   - AndThen（顺叙/过渡，弱）
   - Coincidence（巧合，危险）
3. **冲突级别** — 每个场景的冲突强度 1-10
4. **爽点密度** — 本章爽点/燃点分布和类型
5. **节奏评估** — 整章节奏曲线 + 张力高峰位置
6. **对话占比** — 估算对话所占百分比

重要规则：
- 描述精炼，每条≤20字
- 诚实评估，不讨好作者
- 如果某维度确实没有发现，写"无"或0"""


def build_analysis_prompt(chapter_text: str, genre: str = "",
                           prev_summary: str = "", chapter_num: int = 0) -> str:
    """构建分析 prompt"""
    # 截取章节内容（27B 不需要完整上下文，8000 字足够分析）
    text = chapter_text[-8000:] if len(chapter_text) > 8000 else chapter_text

    prompt = f"""请分析以下第{chapter_num}章内容，输出 JSON 格式的审计报告。

"""
    if genre:
        prompt += f"小说类型：{genre}\n"
    if prev_summary:
        prompt += f"前情摘要：{prev_summary[:300]}\n"

    prompt += f"""
章节正文：
---
{text}
---

请严格按以下 JSON 格式输出（不要输出其他内容）：

```json
{{
  "summary": "一句话概括本章核心剧情（≤30字）",
  "foreshadows_planted": [
    {{"desc": "伏笔描述", "type": "人物身世", "target_ch": 估计回收章号}}
  ],
  "foreshadows_paid": [
    {{"desc": "回收的伏笔", "type": "类型"}}
  ],
  "scenes": [
    {{"name": "场景名", "causality": "Therefore", "conflict": 7, "beat": "爽点类型", "chars": 3}}
  ],
  "causality_chain": "整章因果链简述",
  "pacing_curve": "快→慢→快",
  "tension_peak": "张力高峰在章末/章中/章首",
  "dialogue_pct": 40,
  "satisfaction_density": 7,
  "overall_score": 75,
  "suggestions": ["改进建议1", "改进建议2"]
}}
```

注意：
- foreshadows_planted：本章新埋的伏笔（如有），每条≤20字
- foreshadows_paid：本章回收的之前伏笔（如有），如果不知道从哪章来的写0
- causality 必须选：Therefore / But / AndThen / Coincidence
- conflict 1-10整数
- satisfaction_density 1-10整数
- overall_score 1-100整数
- 只输出 JSON，不要其他文字"""
    return prompt


# ── 解析 ──────────────────────────────────────────────────────────────

def parse_analysis(raw: str, chapter_id: str = "") -> ChapterAnalysis:
    """解析模型输出的 JSON，容错处理"""
    result = ChapterAnalysis(chapter_id=chapter_id, raw_response=raw)

    # 尝试提取 JSON 块
    json_str = raw
    m = re.search(r'```json\s*([\s\S]*?)```', raw)
    if m:
        json_str = m.group(1)
    else:
        # 尝试找第一个 { 到最后一个 }
        m2 = re.search(r'\{[\s\S]*\}', raw)
        if m2:
            json_str = m2.group()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # 容错：尝试修复常见问题
        cleaned = re.sub(r',\s*}', '}', json_str)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            result.summary = "解析失败"
            result.suggestions = ["模型输出格式异常，请重试"]
            return result

    result.summary = data.get("summary", "")[:60]
    result.causality_chain = data.get("causality_chain", "")[:100]
    result.pacing_curve = data.get("pacing_curve", "")[:20]
    result.tension_peak_chapter_position = data.get("tension_peak", "")[:20]
    result.dialogue_ratio_pct = int(data.get("dialogue_pct", 0))
    result.satisfaction_density = int(data.get("satisfaction_density", 0))
    result.overall_score = int(data.get("overall_score", 0))
    result.suggestions = data.get("suggestions", [])[:5]

    # 解析伏笔
    for fp in data.get("foreshadows_planted", []):
        result.foreshadows_planted.append(ForeshadowItem(
            description=fp.get("desc", "")[:30],
            type=fp.get("type", "其他")[:10],
            planted=True,
            target_chapter=int(fp.get("target_ch", 0)),
        ))
    for fp in data.get("foreshadows_paid", []):
        result.foreshadows_paid.append(ForeshadowItem(
            description=fp.get("desc", "")[:30],
            type=fp.get("type", "其他")[:10],
            planted=False,
            resolved_from=int(fp.get("from_ch", fp.get("target_ch", 0))),
        ))

    # 解析场景
    for sc in data.get("scenes", []):
        result.scenes.append(SceneAnalysis(
            name=sc.get("name", "")[:20],
            causality=sc.get("causality", "AndThen")[:15],
            conflict_level=max(1, min(10, int(sc.get("conflict", 5)))),
            satisfaction_beat=sc.get("beat", "")[:15],
            char_count=int(sc.get("chars", 0)),
        ))

    return result


# ── 门控评估（纯确定性，零 token） ───────────────────────────────────

def gate_evaluation(analysis: ChapterAnalysis, min_satisfaction: int = 4,
                    max_coincidence: int = 1) -> dict:
    """确定性门控：不需要模型，纯规则判断"""
    issues = []
    warnings = []

    # 巧合场景过多
    coincidences = [s for s in analysis.scenes if s.causality == "Coincidence"]
    if len(coincidences) > max_coincidence:
        issues.append(f"巧合场景 {len(coincidences)} 个，超过上限 {max_coincidence}")

    # AndThen 连续出现
    for i in range(len(analysis.scenes) - 1):
        if (analysis.scenes[i].causality == "AndThen"
                and analysis.scenes[i+1].causality == "AndThen"):
            warnings.append(f"场景{i+1}→{i+2}连续顺叙，缺乏因果驱动")

    # 爽点密度过低
    if analysis.satisfaction_density < min_satisfaction:
        issues.append(f"爽点密度 {analysis.satisfaction_density}/10，低于阈值 {min_satisfaction}")

    # 对话占比极端
    if analysis.dialogue_ratio_pct > 80:
        warnings.append(f"对话占比 {analysis.dialogue_ratio_pct}%，可能缺乏叙事推进")
    elif analysis.dialogue_ratio_pct < 10:
        warnings.append(f"对话占比 {analysis.dialogue_ratio_pct}%，可能过于叙述")

    # 冲突级别过低
    avg_conflict = (sum(s.conflict_level for s in analysis.scenes)
                    / max(len(analysis.scenes), 1))
    if avg_conflict < 3:
        warnings.append(f"平均冲突级别 {avg_conflict:.1f}，可能缺乏张力")

    passed = len(issues) == 0
    return {
        "passed": passed,
        "issues": issues,
        "warnings": warnings,
        "avg_conflict": round(avg_conflict, 1),
        "coincidence_count": len(coincidences),
        "scene_count": len(analysis.scenes),
    }
