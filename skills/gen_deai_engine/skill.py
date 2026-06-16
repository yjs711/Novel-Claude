"""
gen_deai_engine — 去AI味引擎 Skill

从 StoryForge anti-ai-adapter.ts 移植。
on_chapter_render() 执行去AI味检测：高频词统计 + 五维评分。
"""

import re
from core.base_skill import BaseSkill

# ── 高频AI词汇 ───────────────────────────────────────────────────────────────
# Ported from StoryForge anti-ai-adapter.ts extractHighFreqWords()

AI_FATIGUE_WORDS = [
    "不禁", "缓缓", "竟然", "顿时", "一丝", "微微",
    "嘴角微微上扬", "心中一震", "不由得", "仿佛",
    "似乎", "忽然", "突然", "一瞬间",
    "眼神中闪过一丝", "深吸一口气", "喃喃自语",
    "不禁倒吸一口凉气", "瞳孔骤然收缩",
    "目光深邃", "神色复杂",
]

AI_OVERUSED_PATTERNS = [
    (r"他(不禁|不由得|忍不住)", "意志力表达过频"),
    (r"(缓缓|慢慢|渐渐)地", "过程描写过频"),
    (r"嘴角.*上扬", "微表情模板化"),
    (r"心中.*震", "内心反应模板化"),
    (r"仿佛.*一般", "比喻句式过频"),
    (r"似乎[^，]{0,10}", "模糊表达过频"),
    (r"(突然|忽然|一瞬间)", "突发转折过频"),
    (r"眼神.*闪过一丝", "眼神描写模板化"),
    (r"深吸一口气", "准备动作模板化"),
    (r"喃喃自语[^。]", "自言自语过频"),
]


class GenDeaiEngineSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "去AI味引擎"
        self.threshold = 5  # 同一词出现超过此次数才报警

    def on_init(self) -> None:
        print(f"  [✓] {self.name} 已就绪（{len(AI_FATIGUE_WORDS)}个疲劳词, {len(AI_OVERUSED_PATTERNS)}个模板模式）")

    def on_chapter_render(self, full_text: str, chapter_id: int) -> str:
        """渲染前去AI味检测，结果写入 shared_state"""
        report = self.analyze(full_text)
        self.context.set_shared("deai_report", report)
        self._print_report(report, chapter_id)
        return full_text

    def analyze(self, text: str) -> dict:
        """分析文本，返回五维评分。"""
        # 1. 高频词检测
        word_counts = {}
        for word in AI_FATIGUE_WORDS:
            count = text.count(word)
            if count > 0:
                word_counts[word] = count

        flagged_words = {w: c for w, c in word_counts.items() if c >= self.threshold}

        # 2. 模板模式检测
        pattern_counts = {}
        for pattern, label in AI_OVERUSED_PATTERNS:
            matches = len(re.findall(pattern, text))
            if matches > 0:
                pattern_counts[label] = matches

        flagged_patterns = {p: c for p, c in pattern_counts.items() if c >= self.threshold}

        # 3. 句式多样性（粗略：句长标准差）
        sentences = re.split(r'[。！？\n]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
        if len(sentences) >= 3:
            lengths = [len(s) for s in sentences]
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            syntax_score = min(100, max(10, 100 - variance * 0.5))
        else:
            syntax_score = 50

        # 4. 对话标签多样性
        dialogue_tags = re.findall(r'([^说说道答道问道叫道喊道])', text)
        unique_tags = len(set(dialogue_tags)) if dialogue_tags else 0
        dialogue_score = min(100, unique_tags * 10)

        # 5. 综合打分
        vocab_score = 100 - len(flagged_words) * 5
        pattern_score = 100 - len(flagged_patterns) * 8

        dimensions = [
            {"name": "词汇多样性", "score": max(10, vocab_score), "markers": list(flagged_words.keys())},
            {"name": "句式变化", "score": max(10, int(syntax_score)), "markers": []},
            {"name": "模板化程度", "score": max(10, pattern_score), "markers": list(flagged_patterns.keys())},
            {"name": "对话自然度", "score": max(10, dialogue_score), "markers": []},
            {"name": "整体AI味", "score": max(10, int((vocab_score + syntax_score + pattern_score + dialogue_score * 2) / 5)), "markers": []},
        ]

        overall = dimensions[-1]["score"]

        return {
            "overall_score": overall,
            "dimensions": dimensions,
            "flagged_words": flagged_words,
            "flagged_patterns": flagged_patterns,
            "suggestions": self._generate_suggestions(flagged_words, flagged_patterns),
        }

    def _generate_suggestions(self, flagged_words: dict, flagged_patterns: dict) -> list:
        suggestions = []
        if flagged_words:
            top_words = sorted(flagged_words.items(), key=lambda x: -x[1])[:3]
            suggestions.append(f"减少使用: {', '.join(w for w, _ in top_words)}（各出现{sum(c for _, c in top_words)}次）")
        if flagged_patterns:
            suggestions.append(f"增加句式多样性，避免模板化表达: {', '.join(list(flagged_patterns.keys())[:3])}")
        if not suggestions:
            suggestions.append("本章去AI味表现良好")
        return suggestions

    def _print_report(self, report: dict, chapter_id: int):
        overall = report["overall_score"]
        emoji = "🟢" if overall >= 80 else "🟡" if overall >= 60 else "🔴"
        print(f"\n{emoji} 去AI味检测 第{chapter_id}章: {overall}/100")
        for dim in report["dimensions"]:
            bar = "█" * (dim["score"] // 10) + "░" * (10 - dim["score"] // 10)
            print(f"  {dim['name']:8s} {bar} {dim['score']}")
        if report["suggestions"]:
            for s in report["suggestions"]:
                print(f"  → {s}")
