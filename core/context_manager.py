"""
上下文预算管理器 — 本地模型专用

原则: State in Files, Not in Context
人类大师靠笔记+大纲管理500万字, 本地模型32K窗口必须走同样的路。

基于 CogWriter (ACL 2025) + TokenMizer (2026) + 人类大师方法
"""
from __future__ import annotations
import json, time, re
from pathlib import Path
from typing import Optional

class ContextBudgetManager:
    """上下文预算管理 — 根据场景类型动态分配窗口空间"""

    # 场景类型 → 注入预算 (tokens, 约等于 chars×0.5 for Chinese)
    BUDGETS = {
        "transition": 1500,    # 简单过渡
        "narrative": 1800,     # 普通叙事 (默认)
        "combat": 2500,        # 复杂战斗
        "emotional": 2000,     # 情感高潮
        "exposition": 2000,    # 世界观展开
    }

    @staticmethod
    def detect_scene_type(content: str) -> str:
        """检测场景类型, 用于动态分配预算"""
        scores = {}
        # 战斗检测
        combat_keywords = ["杀","砍","斩","击","轰","爆","斗","战","血","碎","裂"]
        scores["combat"] = sum(1 for w in combat_keywords if w in content)
        # 情感检测
        emotion_keywords = ["哭","泪","笑","痛","爱","恨","怒","悲","喜","拥抱","握住"]
        scores["emotional"] = sum(1 for w in emotion_keywords if w in content)
        # 信息密度检测
        scores["exposition"] = content.count("修炼") + content.count("境界") + content.count("功法")
        # 过渡检测
        if len(content) < 500:
            scores["transition"] = 10

        best = max(scores, key=scores.get)
        if scores[best] > 2:
            return best
        return "narrative"

    @classmethod
    def get_budget(cls, scene_type: str) -> int:
        return cls.BUDGETS.get(scene_type, 1800)

    @classmethod
    def compact_context(cls, components: list[tuple[str, str]], budget: int) -> str:
        """
        按预算截断各组件, 优先保留前面的组件。
        components: [(label, text), ...]
        """
        result = []
        remaining = budget
        for label, text in components:
            if remaining <= 0:
                break
            char_budget = remaining * 2  # tokens→chars 粗略换算
            if len(text) > char_budget:
                text = text[:char_budget] + "..."
            result.append(f"\n\n{label}:\n{text}")
            remaining -= len(text) // 2
        return "".join(result)


class ChapterSummarizer:
    """增量摘要 — 每章写完后压缩, 只保留最近N章全文"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self._file = self.project_dir / "materials" / "chapter_summaries.json"
        self.summaries: list[dict] = []
        self.load()

    def load(self):
        if self._file.exists():
            data = json.loads(self._file.read_text(encoding="utf-8"))
            self.summaries = data.get("summaries", [])

    def save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = {"summaries": self.summaries, "updated": time.time()}
        self._file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def summarize_chapter(self, chapter_num: int, content: str) -> str:
        """压缩章节为简短摘要 (本地模型友好, 用关键词提取而不是LLM)"""
        # 提取关键信息 (轻量级, 不需要LLM)
        chars = len(content)
        # 按句号分段, 取每段首句作为摘要
        sentences = [s.strip() for s in content.replace("！","。").replace("？","。").split("。") if len(s.strip()) > 10]
        key_sentences = sentences[:3]  # 前3句通常是场景建立
        if len(sentences) > 5:
            key_sentences.append(sentences[len(sentences)//2])  # 中间一句
        if len(sentences) > 3:
            key_sentences.append(sentences[-1])  # 最后一句 (通常是钩子)

        summary = "。".join(key_sentences[:5])

        # 检测关键事件
        events = []
        if "突破" in content: events.append("突破")
        if "战斗" in content or "杀" in content: events.append("战斗")
        if "突破" in content or "晋升" in content: events.append("升级")
        if "发现" in content or "得知" in content: events.append("信息获取")
        event_str = "/".join(events) if events else "日常"

        record = {
            "chapter": chapter_num,
            "chars": chars,
            "events": event_str,
            "summary": summary[:200],
        }
        self.summaries.append(record)
        self.save()
        return summary[:200]

    def get_recent_context(self, count: int = 3) -> str:
        """获取最近N章的摘要上下文"""
        recent = self.summaries[-count:] if len(self.summaries) >= count else self.summaries
        parts = []
        for r in recent:
            parts.append(f"第{r['chapter']}章({r['events']}): {r['summary'][:100]}")
        return " | ".join(parts)

    def get_global_summary(self, max_chars: int = 500) -> str:
        """全局摘要 — 每10章压缩一次"""
        if not self.summaries:
            return ""
        total_chars = sum(r["chars"] for r in self.summaries)
        events_count = {}
        for r in self.summaries:
            for e in r["events"].split("/"):
                if e: events_count[e] = events_count.get(e, 0) + 1
        return f"已完成{len(self.summaries)}章, 总计{total_chars:,}字。主要事件: {dict(events_count)}"
