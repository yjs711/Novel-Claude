"""
mem_fact_summary — 事实摘要算法 Skill (256K优化版)

从 WenShape DynamicContextRetriever 移植。
五级章节检索 + BM25 + 对数距离衰减 + 剧情线垂直追踪。
256K context → 200K token budget for facts.
"""

import math, re, json
from pathlib import Path
from typing import List, Tuple, Optional
from core.base_skill import BaseSkill


def _tokenize(text: str) -> List[str]:
    tokens = []
    chinese_chars = re.findall(r'[一-鿿]+', text)
    for seg in chinese_chars:
        tokens.extend([seg[i:i+2] for i in range(len(seg)-1)])
        tokens.extend(list(seg))
    english_words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    tokens.extend(english_words)
    return [t for t in tokens if len(t) >= 1]


def _calculate_distance_decay(current_chapter: int, introduced_in: int, alpha: float = 0.15) -> float:
    """对数型距离衰减。alpha=0.15 让远距离事实保持更高权重"""
    if alpha <= 0: return 1.0
    dist = abs(current_chapter - introduced_in)
    if dist <= 0: return 1.0
    return 1.0 / (1.0 + alpha * math.log(1 + dist))


class MemFactSummarySkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "事实摘要引擎"
        # 256K优化：五级检索，更多细节保留
        self.full_text_range = (0, 3)        # 最近3章完整
        self.detail_range = (3, 50)          # 3-50章: 详细摘要
        self.medium_range = (50, 150)        # 50-150章: 中等摘要
        self.brief_range = (150, 400)        # 150-400章: 简要
        self.title_range = (400, None)        # 400+章: 标题
        self.max_context_tokens = 200000      # 256K → 200K给事实
        self.plot_thread_vertical_tokens = 30000

    def on_init(self) -> None:
        print(f"  [✓] {self.name} 已就绪 (256K优化: 五级检索, α=0.15, 200K budget)")

    def on_before_scene_write(self, prompt_payload: list, beat_data: dict) -> list:
        chapter_id = beat_data.get("chapter_id") or self.context.current_chapter_id
        story_state = self.context.get_shared("story_state")
        if story_state is None or not story_state.chapters:
            return prompt_payload

        blocks = []

        # 1. 按章节的水平摘要
        blocks.append(self._build_chapter_summary(story_state, chapter_id))

        # 2. 剧情线垂直追踪（关键！不受距离衰减影响）
        blocks.append(self._build_plot_thread_tracking(story_state, chapter_id))

        # 3. 角色弧光追踪
        blocks.append(self._build_character_arc_tracking(story_state, chapter_id))

        context_block = "\n".join(b for b in blocks if b)
        if context_block:
            prompt_payload.append("\n[智能事实摘要 · 256K]\n" + context_block)
        return prompt_payload

    def _build_chapter_summary(self, story_state, current_ch: int) -> str:
        """五级章节水平摘要"""
        blocks = []
        for ch_num, ch in sorted(story_state.chapters.items()):
            if ch_num >= current_ch: continue
            distance = current_ch - ch_num

            if distance <= self.full_text_range[1]:
                tier = "full"
            elif distance <= self.detail_range[1]:
                tier = "detail"
            elif distance <= self.medium_range[1]:
                tier = "medium"
            elif self.brief_range[1] is None or distance <= self.brief_range[1]:
                tier = "brief"
            else:
                tier = "title"

            weight = _calculate_distance_decay(current_ch, ch_num)

            if tier == "full":
                text = f"第{ch_num}章 {ch.title}: {', '.join(ch.plot_advances[:8] or ['略'])}"
                if ch.emotional_beats:
                    text += f" | 情绪: {', '.join(ch.emotional_beats[:3])}"
                if ch.new_information:
                    text += f" | 新信息: {', '.join(ch.new_information[:3])}"
            elif tier == "detail":
                text = f"第{ch_num}章 {ch.title}: {'; '.join(ch.plot_advances[:4] or ['略'])}"
            elif tier == "medium":
                text = f"第{ch_num}章 {ch.title}: {', '.join(ch.plot_advances[:2] or ['略'])}"
            elif tier == "brief":
                text = f"第{ch_num}章 {ch.title}"
            else:
                if weight > 0.2:
                    text = f"第{ch_num}章 {ch.title}"

            blocks.append((weight, text))

        blocks.sort(key=lambda x: -x[0])
        result, tokens = [], 0
        for w, t in blocks:
            if tokens + len(t) > self.max_context_tokens: break
            result.append(t); tokens += len(t)

        return "【章节水平摘要】\n" + "\n".join(result) if result else ""

    def _build_plot_thread_tracking(self, story_state, current_ch: int) -> str:
        """剧情线垂直追踪 — 每条线独立追踪，不受距离衰减"""
        active_threads = [t for t in story_state.plot_threads.values() if t.status == "active"]
        if not active_threads:
            return ""

        lines = ["【剧情线垂直追踪】"]
        total_tokens = 0
        for thread in active_threads:
            thread_line = f"▸ {thread.name} (P{thread.priority}): {thread.description[:80]}"
            # 回溯线索关键节点
            milestones = thread.milestones[-10:] if thread.milestones else []
            if milestones:
                ms_text = " → ".join(m.get("description", "")[:30] for m in milestones[-5:])
                thread_line += f" | 最近节点: {ms_text}"
            # 伏笔状态
            if thread.foreshadowing_planted:
                planted_in = thread.foreshadowing_planted[-5:]
                thread_line += f" | 伏笔在: {planted_in}"
            # 距离上次推进
            gap = current_ch - (thread.last_updated_chapter or thread.start_chapter or 0)
            if gap > 5:
                thread_line += f" | ⚠️ {gap}章未推进"
            if thread.target_resolution_chapter:
                remaining = thread.target_resolution_chapter - current_ch
                thread_line += f" | 预计{remaining}章后收束"

            if total_tokens + len(thread_line) > self.plot_thread_vertical_tokens:
                break
            lines.append(thread_line)
            total_tokens += len(thread_line)

        return "\n".join(lines) if len(lines) > 1 else ""

    def _build_character_arc_tracking(self, story_state, current_ch: int) -> str:
        """角色弧光追踪 — 主要角色的成长轨迹"""
        main_chars = [c for c in story_state.characters.values()
                      if c.role in ("protagonist", "antagonist")]
        if not main_chars:
            return ""

        lines = ["【角色弧光追踪】"]
        for c in main_chars:
            line = f"▸ {c.full_name} ({c.role})"
            if c.internal_desire:
                line += f" | 渴望: {c.internal_desire}"
            if c.arc_stage and c.arc_stage != "beginning":
                line += f" | 弧光: {c.arc_stage}({c.arc_progress}%)"
            if c.emotional_state:
                line += f" | 情绪: {c.emotional_state}"
            if c.current_location:
                line += f" | 位置: {c.current_location}"
            gap = current_ch - c.last_appearance_chapter if c.last_appearance_chapter else 0
            if gap > 10:
                line += f" | ⚠️ {gap}章未登场"
            lines.append(line)

        return "\n".join(lines) if len(lines) > 1 else ""

    def score_facts(self, query: str, facts: List[dict], current_ch: int) -> List[dict]:
        """BM25 + 距离衰减"""
        query_tokens = _tokenize(query)
        if not query_tokens: return facts
        scored = []
        for fact in facts:
            content = fact.get("statement", "")
            content_tokens = _tokenize(content)
            overlap = len(set(query_tokens) & set(content_tokens))
            bm25 = overlap / (1 + len(content_tokens) * 0.1)
            intro_ch = fact.get("introduced_in", current_ch)
            try:
                intro_ch = int(intro_ch) if isinstance(intro_ch, str) else intro_ch
            except (ValueError, TypeError):
                intro_ch = current_ch
            decay = _calculate_distance_decay(current_ch, intro_ch)
            fact["_score"] = bm25 * 0.65 + overlap * 0.35 * decay
            scored.append(fact)
        scored.sort(key=lambda f: -f["_score"])
        return scored
