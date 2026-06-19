"""
Novel-Claude Fusion — Narrative Diversity Engine

Addresses StoryScope 2026: 93.2% AI detection via narrative structure alone.
AI stories converge to: protagonist-driven resolution, explicit themes,
linear chronology, clean causal chains, minimal subplots.

Counter-measures based on:
  - "Diverse AI Personas" (Wan & Kalman 2026): multi-persona prompting
  - StoryScope: 30 narrative features achieve 84.8% detection
  - NCP (Narrative Context Protocol): storyform-first constraints

This module detects structural homogenization across chapters and injects
diversity pressure into generation prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


# ── narrative archetypes ─────────────────────────────────────────────────────

@dataclass
class NarrativeShape:
    """A narrative approach / author persona for diversity injection."""
    name: str
    description: str
    prompt_hint: str          # injected into chapter prompt
    structural_markers: List[str]  # what to look for in output


# Diverse persona set (Wan & Kalman 2026 pattern)
NARRATIVE_ARCHETYPES: List[NarrativeShape] = [
    NarrativeShape(
        name="action-driven",
        description="Plot moves through external events and conflicts",
        prompt_hint="Focus on external action. Events drive character decisions, not internal monologue. Show consequences through action, not reflection.",
        structural_markers=["external_conflict", "action_chain", "event_cascade"],
    ),
    NarrativeShape(
        name="character-driven",
        description="Plot moves through internal character decisions and growth",
        prompt_hint="Focus on internal conflict. Characters make difficult choices. Show motivation through action and subtext, not stated reasoning. Resist explaining why.",
        structural_markers=["internal_dilemma", "moral_choice", "character_growth"],
    ),
    NarrativeShape(
        name="mystery-driven",
        description="Plot moves through withheld information and gradual revelation",
        prompt_hint="Withhold information. The reader should wonder, not be told. Reveal through implication and consequence. Leave questions unanswered until they must be resolved.",
        structural_markers=["withheld_info", "gradual_reveal", "unanswered_question"],
    ),
    NarrativeShape(
        name="atmosphere-driven",
        description="Plot moves through world texture, setting, and sensory immersion",
        prompt_hint="Ground the scene in sensory detail. Let the world speak through what characters notice, not what they say. Environment as character. Mood over message.",
        structural_markers=["sensory_immersion", "environmental_storytelling", "mood_first"],
    ),
    NarrativeShape(
        name="relationship-driven",
        description="Plot moves through interpersonal dynamics and unspoken tensions",
        prompt_hint="Focus on what's unsaid between characters. Power dynamics, trust erosion, alliance shifts. Dialogue serves relationship, not plot. Subtext in every exchange.",
        structural_markers=["interpersonal_tension", "power_shift", "subtext_dialogue"],
    ),
]


# ── chapter analysis ─────────────────────────────────────────────────────────

@dataclass
class ChapterFingerprint:
    """Quick structural fingerprint of a chapter's narrative shape."""
    chapter_id: int
    protagonist_resolves: bool       # chapter ends with protagonist action solving problem
    explicit_theme: bool             # narrator/character states theme directly
    philosophical_dialogue: bool     # dialogue contains abstract/philosophical discussion
    single_pov: bool                 # only one perspective throughout
    linear_time: bool                # no flashbacks, no time manipulation
    tidy_ending: bool                # chapter wraps up neatly
    subplot_advance: bool            # at least one subplot advances
    dominant_archetype: str = ""     # closest matching archetype


def fingerprint_chapter(text: str, chapter_id: int) -> ChapterFingerprint:
    """
    Quick structural fingerprint of a chapter.
    Uses regex patterns — fast, zero-token, approximate.
    """
    import re

    # Protagonist resolves: "主角+主动动词+解决/完成/etc" at chapter end
    last_500 = text[-500:] if len(text) > 500 else text
    last_200 = text[-200:] if len(text) > 200 else text
    protagonist_resolves = bool(re.search(
        r'(他|她|林\w|萧\w|叶\w|楚\w|苏\w|秦\w)'
        r'(终于|最终|成功|完成|解决|打败|突破|达到|踏入)',
        last_500,
    ))

    # Explicit theme: "X让Y明白/意识到/懂得 道理/真谛/意义"
    explicit_theme = bool(re.search(
        r'(让|令|使).{2,8}(明白|意识到|懂得|领悟).{0,20}(道理|真意|含义|真谛)',
        text,
    ))

    # Philosophical dialogue: long dialogue with abstract terms
    philosophical_dialogue = bool(re.search(
        r'[""「].{20,}(人生|命运|世间|这世上|力量|权利|正义|真理|自由|爱).{20,}[""」]',
        text,
    ))

    # Single POV: check for POV switch markers
    pov_markers = len(re.findall(r'(视角切换|另一边|与此同时.{0,5}在|场景转换)', text))
    single_pov = pov_markers <= 1

    # Linear time: check for flashback markers
    flashback_markers = len(re.findall(
        r'(回想|回忆|当年|曾经|那是.{2,5}年前|那时候|从前)',
        text,
    ))
    linear_time = flashback_markers <= 1

    # Tidy ending: chapter ends with resolution/summary sentence
    tidy_ending = bool(re.search(
        r'(就这样|至此|从此|于是).{0,20}(。|！|？|\n)',
        last_200,
    ))

    # Subplot advance: check for thread advancement markers
    subplot_advance = len(re.findall(
        r'(与此同时|另一边|与此同|镜头转|场景切换)',
        text,
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


# ── diversity scoring ────────────────────────────────────────────────────────

def diversity_score(fingerprints: List[ChapterFingerprint]) -> Tuple[int, List[str]]:
    """
    Score the narrative diversity of recent chapters (0-100).
    High score = diverse, low score = homogenized (AI-typical).

    Returns (score, suggestions).
    """
    if len(fingerprints) < 2:
        return 100, ["需要更多章节才能评估多样性"]

    issues = []
    score = 100

    # Check 1: protagonist_resolves in all chapters -> -20
    if all(f.protagonist_resolves for f in fingerprints):
        score -= 20
        issues.append("连续章节均为'主角驱动解决'模式 (StoryScope: 69% AI vs 46% human)")

    # Check 2: explicit_theme in majority -> -15
    if sum(1 for f in fingerprints if f.explicit_theme) > len(fingerprints) * 0.5:
        score -= 15
        issues.append("章节频繁出现'主题直接陈述' (StoryScope: 77% AI vs 52% human)")

    # Check 3: philosophical_dialogue in all -> -10
    if all(f.philosophical_dialogue for f in fingerprints):
        score -= 10
        issues.append("所有章节含哲学讨论对话 (StoryScope: 59% AI vs 34% human)")

    # Check 4: all single_pov -> -10
    if all(f.single_pov for f in fingerprints):
        score -= 10
        issues.append("全部单一视角，缺乏多视角切换")

    # Check 5: all linear_time -> -10
    if all(f.linear_time for f in fingerprints):
        score -= 10
        issues.append("全部线性时间线，缺乏闪回/时间操作 (StoryScope: AI overwhelming linear)")

    # Check 6: all tidy_ending -> -10
    if all(f.tidy_ending for f in fingerprints):
        score -= 10
        issues.append("所有章末为整洁收束，缺乏悬念/未解 (StoryScope: AI defaults to tidy endings)")

    # Check 7: no subplot advances -> -15
    if not any(f.subplot_advance for f in fingerprints):
        score -= 15
        issues.append("无支线推进 (StoryScope: 79% AI stories lack subplots)")

    return max(score, 10), issues


# ── diversity injection ──────────────────────────────────────────────────────

def suggest_archetype(fingerprints: List[ChapterFingerprint]) -> str:
    """
    Suggest a narrative archetype for the next chapter to diversify.
    Picks the archetype least represented in recent chapters.
    """
    if not fingerprints:
        return NARRATIVE_ARCHETYPES[0].prompt_hint

    # Find the most common problematic pattern
    patterns = {
        "action-driven": sum(1 for f in fingerprints if f.protagonist_resolves),
        "mystery-driven": sum(1 for f in fingerprints if not f.tidy_ending),
        "relationship-driven": sum(1 for f in fingerprints if not f.philosophical_dialogue),
        "atmosphere-driven": sum(1 for f in fingerprints if not f.explicit_theme),
        "character-driven": sum(1 for f in fingerprints if not f.single_pov),
    }

    # Pick the least-used archetype
    least_used = min(patterns, key=patterns.get)
    for archetype in NARRATIVE_ARCHETYPES:
        if archetype.name == least_used:
            return archetype.prompt_hint
    return NARRATIVE_ARCHETYPES[0].prompt_hint


def build_diversity_context(fingerprints: List[ChapterFingerprint]) -> str:
    """
    Build a diversity injection block for the chapter writing prompt.
    If recent chapters show homogenization, inject counter-pressure.
    """
    score, issues = diversity_score(fingerprints)

    if score >= 80:
        return ""  # diverse enough, no injection needed

    hint = suggest_archetype(fingerprints)
    parts = [
        "\n[Narrative Diversity — Counter-homogenization]\n",
        f"Diversity Score: {score}/100 (low = AI-typical pattern). Issues:",
    ]
    for issue in issues[:3]:
        parts.append(f"  - {issue}")
    parts.append(f"\nSuggested approach for this chapter:\n  {hint}")
    parts.append("")

    return "\n".join(parts)
