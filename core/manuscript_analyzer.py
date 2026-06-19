"""
Novel-Claude Fusion — Manuscript Analyzer

Per-chapter + whole-novel analysis: pacing, POV, chapter distribution,
prose economy, dialogue ratio, sensory balance.

All metrics are zero-token (deterministic regex + counting).
Designed to complement the LLM-based Quality Gate and Editor Agent.

Usage:
  from core.manuscript_analyzer import analyze_manuscript
  report = analyze_manuscript(manuscript_dir)
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from utils.logger import get_logger, log_step

logger = get_logger(__name__)


# ── per-chapter metrics ──────────────────────────────────────────────────────

@dataclass
class ChapterMetrics:
    chapter_num: int
    title: str = ""
    word_count: int = 0             # Chinese characters
    sentence_count: int = 0
    paragraph_count: int = 0
    dialogue_ratio: float = 0.0      # dialogue chars / total chars
    dialogue_tag_variety: int = 0    # unique dialogue tags
    avg_sentence_len: float = 0.0
    sentence_len_variance: float = 0.0
    action_verb_density: float = 0.0 # verbs per 1000 chars
    adverb_density: float = 0.0      # adverbs per 1000 chars
    sensory_words: int = 0           # sight/sound/touch/smell/taste
    pov_markers: int = 0             # perspective shift indicators
    ai_pattern_count: int = 0        # detected AI patterns
    over_explain_count: int = 0      # thematic explanation markers
    urgency_score: float = 0.0       # conflict density proxy


# ── analysis ─────────────────────────────────────────────────────────────────

def _count_chinese(text: str) -> int:
    return len(re.findall(r'[一-鿿]', text))


def _count_sentences(text: str) -> int:
    return len(re.findall(r'[。！？\n]', text))


def _count_paragraphs(text: str) -> int:
    return len(re.findall(r'\n\n+', text)) + 1


def _dialogue_chars(text: str) -> int:
    """Count characters inside Chinese quotes."""
    dialogue = re.findall(r'[""「「](.*?)[""」」]', text)
    return sum(len(re.findall(r'[一-鿿]', d)) for d in dialogue)


def _dialogue_tag_variety(text: str) -> int:
    tags = re.findall(r'(说道|答道|问道|叫道|喊道|笑着说|冷声道|低声道|淡淡道|沉声道|开口|回|问|说|喊|叫|答)', text)
    return len(set(tags))


def _action_verb_density(text: str) -> float:
    verbs = re.findall(r'(冲|撞|击|劈|砍|刺|踢|跳|飞|跑|追|逃|抓|握|推|拉|砸|轰|爆)', text)
    chars = _count_chinese(text)
    return len(verbs) * 1000 / max(chars, 1)


def _adverb_density(text: str) -> float:
    adverbs = re.findall(r'(缓缓|微微|淡淡|轻轻|悄悄|默默|渐渐|慢慢|狠狠|死死|牢牢)', text)
    chars = _count_chinese(text)
    return len(adverbs) * 1000 / max(chars, 1)


def _sensory_words(text: str) -> int:
    """Count sensory descriptors."""
    patterns = [
        r'(看到|看见|望见|注视|凝视|眺|瞄|瞥)',    # sight
        r'(听到|听见|传来|响起|轰鸣|寂静|喧闹)',    # sound
        r'(触|碰|抚|摸|冰凉|滚烫|粗糙|光滑)',      # touch
        r'(闻|嗅|香|臭|腥|焦|甜腻|酸腐|刺鼻)',    # smell
        r'(尝|吞|咽|苦|甜|酸|辣|涩|鲜美|麻辣)',    # taste
    ]
    total = 0
    for p in patterns:
        total += len(re.findall(p, text))
    return total


def _pov_markers(text: str) -> int:
    """Count POV shift indicators."""
    return len(re.findall(r'(视角|镜头|画面|场景).{0,5}(切换|一转|移到|来到|转向)', text))


def _ai_pattern_count(text: str) -> int:
    """Count known AI patterns (simplified subset)."""
    patterns = [
        r'不是.{2,10}而是', r'不仅.{2,10}更是',
        r'嘴角.{0,3}上扬', r'心中.{0,3}一震', r'深吸一口气',
        r'(突然|忽然|顿时|猛地)', r'(不禁|不由得|忍不住)',
    ]
    total = 0
    for p in patterns:
        total += len(re.findall(p, text))
    return total


def _over_explain_count(text: str) -> int:
    """Count over-explanation markers."""
    patterns = [
        r'(让|令|使).{2,8}(明白|意识到|懂得|领悟)',
        r'人生.{2,10}(道理|哲理|真谛)',
        r'(说到底|归根结底|总而言之)',
        r'这.{2,8}(告诉|启示)',
    ]
    total = 0
    for p in patterns:
        total += len(re.findall(p, text))
    return total


def _urgency_score(text: str, word_count: int) -> float:
    """Estimate urgency based on conflict/stakes language density."""
    stakes = len(re.findall(
        r'(必须|不得不|否则|不然|一旦|如果.{0,5}就|再不|快要|就要|将要|即将'
        r'|生死|拼了|豁出去|没时间|赶|快|急)',
        text,
    ))
    decisions = len(re.findall(r'(决定|选择|咬牙|狠心|终于|下定决心|拼死|拼命)', text))
    density = (stakes + decisions) * 1000 / max(word_count, 1)
    return round(min(10, density * 20), 1)


# ── chapter analysis ─────────────────────────────────────────────────────────

def analyze_chapter(text: str, chapter_num: int, title: str = "") -> ChapterMetrics:
    """Analyze a single chapter."""
    wc = _count_chinese(text)
    sc = _count_sentences(text)
    pc = _count_paragraphs(text)
    d_chars = _dialogue_chars(text)

    # Sentence length stats
    sentences = re.split(r'[。！？\n]', text)
    sentences = [s for s in sentences if len(re.findall(r'[一-鿿]', s)) > 3]
    if sentences:
        lengths = [len(re.findall(r'[一-鿿]', s)) for s in sentences]
        avg_sent = sum(lengths) / len(lengths)
        var_sent = sum((l - avg_sent) ** 2 for l in lengths) / len(lengths)
    else:
        avg_sent = 0
        var_sent = 0

    return ChapterMetrics(
        chapter_num=chapter_num,
        title=title,
        word_count=wc,
        sentence_count=sc,
        paragraph_count=pc,
        dialogue_ratio=round(d_chars / max(wc, 1), 3),
        dialogue_tag_variety=_dialogue_tag_variety(text),
        avg_sentence_len=round(avg_sent, 1),
        sentence_len_variance=round(var_sent, 1),
        action_verb_density=round(_action_verb_density(text), 1),
        adverb_density=round(_adverb_density(text), 1),
        sensory_words=_sensory_words(text),
        pov_markers=_pov_markers(text),
        ai_pattern_count=_ai_pattern_count(text),
        over_explain_count=_over_explain_count(text),
        urgency_score=_urgency_score(text, wc),
    )


# ── manuscript-level analysis ────────────────────────────────────────────────

@dataclass
class ManuscriptReport:
    title: str
    total_chapters: int
    total_words: int
    chapters: List[ChapterMetrics] = field(default_factory=list)

    # Aggregate
    avg_chapter_len: float = 0.0
    chapter_len_variance: float = 0.0
    avg_dialogue_ratio: float = 0.0
    avg_urgency: float = 0.0
    avg_adverb_density: float = 0.0
    avg_ai_patterns: float = 0.0
    avg_over_explain: float = 0.0
    total_sensory: int = 0
    total_pov_shifts: int = 0

    # Diagnostics
    pacing_issues: List[str] = field(default_factory=list)
    economy_issues: List[str] = field(default_factory=list)
    diversity_issues: List[str] = field(default_factory=list)
    dead_zones: List[int] = field(default_factory=list)  # chapter numbers

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "total_chapters": self.total_chapters,
            "total_words": self.total_words,
            "avg_chapter_len": self.avg_chapter_len,
            "avg_dialogue_ratio": round(self.avg_dialogue_ratio, 2),
            "avg_urgency": round(self.avg_urgency, 1),
            "avg_adverb_density": round(self.avg_adverb_density, 1),
            "avg_ai_patterns": round(self.avg_ai_patterns, 1),
            "avg_over_explain": round(self.avg_over_explain, 1),
            "pacing_issues": self.pacing_issues,
            "economy_issues": self.economy_issues,
            "diversity_issues": self.diversity_issues,
            "dead_zones": self.dead_zones,
            "chapters": [
                {
                    "num": c.chapter_num, "title": c.title,
                    "words": c.word_count,
                    "dialogue_ratio": c.dialogue_ratio,
                    "avg_sentence_len": c.avg_sentence_len,
                    "action_verb_density": c.action_verb_density,
                    "adverb_density": c.adverb_density,
                    "sensory_words": c.sensory_words,
                    "ai_patterns": c.ai_pattern_count,
                    "over_explain": c.over_explain_count,
                    "urgency": c.urgency_score,
                    "pov_markers": c.pov_markers,
                }
                for c in self.chapters
            ],
        }


def analyze_manuscript(manuscript_dir: str, title: str = "",
                        volume_id: int = None) -> Optional[ManuscriptReport]:
    """
    Analyze an entire manuscript directory.

    Returns ManuscriptReport with per-chapter metrics and aggregate diagnostics,
    or None if no chapters found.
    """
    manuscript = Path(manuscript_dir)
    if not manuscript.exists():
        logger.error("Manuscript dir not found: %s", manuscript_dir)
        return None

    if volume_id:
        vol_dir = manuscript / f"vol_{volume_id:02d}"
        chapter_files = sorted(vol_dir.glob("ch_*_final.md")) if vol_dir.exists() else []
    else:
        chapter_files = sorted(manuscript.rglob("ch_*_final.md"))

    if not chapter_files:
        logger.warning("No chapter files found")
        return None

    log_step("Analyzing manuscript", chapters=len(chapter_files), dir=manuscript_dir)

    chapters = []
    for cf in chapter_files:
        try:
            ch_num = int(cf.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        text = cf.read_text(encoding="utf-8")
        cm = analyze_chapter(text, ch_num, title=cf.stem)
        chapters.append(cm)

    if not chapters:
        return None

    chapters.sort(key=lambda c: c.chapter_num)

    # Aggregates
    total_words = sum(c.word_count for c in chapters)
    n = len(chapters)
    avg_len = total_words / n if n else 0
    len_var = sum((c.word_count - avg_len) ** 2 for c in chapters) / n if n else 0

    report = ManuscriptReport(
        title=title,
        total_chapters=n,
        total_words=total_words,
        chapters=chapters,
        avg_chapter_len=round(avg_len),
        chapter_len_variance=round(len_var),
        avg_dialogue_ratio=sum(c.dialogue_ratio for c in chapters) / n,
        avg_urgency=sum(c.urgency_score for c in chapters) / n,
        avg_adverb_density=sum(c.adverb_density for c in chapters) / n,
        avg_ai_patterns=sum(c.ai_pattern_count for c in chapters) / n,
        avg_over_explain=sum(c.over_explain_count for c in chapters) / n,
        total_sensory=sum(c.sensory_words for c in chapters),
        total_pov_shifts=sum(c.pov_markers for c in chapters),
    )

    # ── Diagnostics ──

    # Pacing: flag chapters with low urgency
    for c in chapters:
        if c.urgency_score < 1.0:
            report.dead_zones.append(c.chapter_num)
            report.pacing_issues.append(
                f"Ch{c.chapter_num}: low urgency ({c.urgency_score}), "
                f"{c.word_count} words, dialogue ratio {c.dialogue_ratio:.0%}"
            )

    # Pacing: sentence length monotony
    if report.chapters:
        sent_vars = [c.sentence_len_variance for c in chapters]
        avg_sent_var = sum(sent_vars) / len(sent_vars)
        if avg_sent_var < 50:
            report.pacing_issues.append(
                f"Low sentence length variation (avg variance={avg_sent_var:.0f}). "
                "Consider varying sentence rhythm."
            )

    # Economy: high adverb density
    for c in chapters:
        if c.adverb_density > 8:
            report.economy_issues.append(
                f"Ch{c.chapter_num}: high adverb density ({c.adverb_density}/1000chars)"
            )

    # Economy: high AI pattern count
    if report.avg_ai_patterns > 10:
        report.economy_issues.append(
            f"High AI pattern density (avg {report.avg_ai_patterns:.0f}/chapter)"
        )

    # Diversity: low dialogue chapters
    low_dialogue = [c for c in chapters if c.dialogue_ratio < 0.05]
    if len(low_dialogue) > n * 0.3:
        report.diversity_issues.append(
            f"{len(low_dialogue)}/{n} chapters have very low dialogue (<5%)"
        )

    # Diversity: low sensory
    if report.total_sensory / max(n, 1) < 3:
        report.diversity_issues.append("Low sensory description density across manuscript")

    logger.success("Analysis complete: %d chapters, %d words, %d issues",
                   n, total_words,
                   len(report.pacing_issues) + len(report.economy_issues) + len(report.diversity_issues))

    return report
