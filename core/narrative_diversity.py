"""
Novel-Claude Fusion — Narrative Diversity Engine

Detects structural homogenization across chapters using StoryScope 2026
verified markers (Russell et al., 61,608 stories, 304 features).

Source: StoryScope (arXiv 2604.03136) — 93.2% AI detection via narrative
structure alone. 30 features achieve 84.8% detection.

This module does NOT inject unverified archetype hints. It only detects
structural patterns and reports a diversity score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import re


@dataclass
class ChapterFingerprint:
    """Structural fingerprint based on StoryScope 2026 verified markers."""
    chapter_id: int
    protagonist_resolves: bool       # ch ends with protagonist action solving problem
    explicit_theme: bool             # narrator/character states theme directly
    philosophical_dialogue: bool     # dialogue contains abstract/philosophical discussion
    single_pov: bool                 # only one perspective throughout
    linear_time: bool                # no flashbacks, no time manipulation
    tidy_ending: bool                # chapter wraps up neatly
    subplot_advance: bool            # at least one subplot advances


def fingerprint_chapter(text: str, chapter_id: int) -> ChapterFingerprint:
    """Quick structural fingerprint (zero-token, regex-based)."""
    last_500 = text[-500:] if len(text) > 500 else text
    last_200 = text[-200:] if len(text) > 200 else text

    protagonist_resolves = bool(re.search(
        r'(他|她|林\w|萧\w|叶\w|楚\w|苏\w|秦\w)'
        r'(终于|最终|成功|完成|解决|打败|突破|达到|踏入)',
        last_500,
    ))
    explicit_theme = bool(re.search(
        r'(让|令|使).{2,8}(明白|意识到|懂得|领悟).{0,20}(道理|真意|含义|真谛)',
        text,
    ))
    philosophical_dialogue = bool(re.search(
        r'[""「].{20,}(人生|命运|世间|这世上|力量|权利|正义|真理|自由|爱).{20,}[""」]',
        text,
    ))
    pov_markers = len(re.findall(r'(视角切换|另一边|与此同时.{0,5}在|场景转换)', text))
    single_pov = pov_markers <= 1
    flashback_markers = len(re.findall(
        r'(回想|回忆|当年|曾经|那是.{2,5}年前|那时候|从前)', text,
    ))
    linear_time = flashback_markers <= 1
    tidy_ending = bool(re.search(
        r'(就这样|至此|从此|于是).{0,20}(。|！|？|\n)', last_200,
    ))
    subplot_advance = len(re.findall(
        r'(与此同时|另一边|与此同|镜头转|场景切换)', text,
    )) >= 1

    return ChapterFingerprint(
        chapter_id=chapter_id,
        protagonist_resolves=protagonist_resolves,
        explicit_theme=explicit_theme,
        philosophical_dialogue=philosophical_dialogue,
        single_pov=single_pov,
        linear_time=linear_time,
        tidy_ending=tidy_ending,
        subplot_advance=subplot_advance,
    )


def diversity_score(fingerprints: List[ChapterFingerprint]) -> Tuple[int, List[str]]:
    """
    Score narrative diversity (0-100). High = diverse, Low = homogenized.
    Data points from StoryScope 2026 (Russell et al., 61,608 stories).
    Scoring weights: heuristic, proportional to AI-vs-human gap size.
    """
    if len(fingerprints) < 2:
        return 100, ["Need more chapters to assess diversity"]

    issues = []
    score = 100

    # StoryScope: 69% AI vs 46% human — gap=23pp → weight=-20
    if all(f.protagonist_resolves for f in fingerprints):
        score -= 20
        issues.append("All chapters: protagonist-driven resolution (StoryScope: 69% AI vs 46% human)")

    # StoryScope: 77% AI vs 52% human — gap=25pp → weight=-15
    if sum(1 for f in fingerprints if f.explicit_theme) > len(fingerprints) * 0.5:
        score -= 15
        issues.append("Majority chapters: explicit theme statements (StoryScope: 77% AI vs 52% human)")

    # StoryScope: 59% AI vs 34% human — gap=25pp → weight=-10 (less frequent)
    if all(f.philosophical_dialogue for f in fingerprints):
        score -= 10
        issues.append("All chapters: philosophical dialogue (StoryScope: 59% AI vs 34% human)")

    # StoryScope: AI overwhelmingly single-POV, linear, tidy
    if all(f.single_pov for f in fingerprints):
        score -= 10
        issues.append("All single POV, no perspective shifts")

    if all(f.linear_time for f in fingerprints):
        score -= 10
        issues.append("All linear timeline, no flashbacks (StoryScope: AI overwhelmingly linear)")

    if all(f.tidy_ending for f in fingerprints):
        score -= 10
        issues.append("All tidy chapter endings (StoryScope: AI defaults to tidy endings)")

    # StoryScope: 79% AI stories lack subplots
    if not any(f.subplot_advance for f in fingerprints):
        score -= 15
        issues.append("No subplot advancement (StoryScope: 79% AI stories lack subplots)")

    return max(score, 10), issues
