"""
Novel-Claude Fusion — Quality Gate Engine.

Unified chapter quality evaluation combining:
  Phase 1: Deterministic continuity checks (zero-token, 7 dimensions)
  Phase 2: DeAI detection (8 dimensions, regex-based)
  Phase 3: Editor Agent review (LLM, ReAct multi-turn)

Floor principle: weakest dimension caps overall score.
Thresholds: >=70 PASS, 40-69 REWRITE, <40 BLOCK.
Max 3 rewrite rounds per chapter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from core.continuity_engine import Finding


# ── Gate thresholds ───────────────────────────────────────────────────────────

PASS_THRESHOLD = 70      # >=70: chapter approved
REWRITE_MIN = 40         # 40-69: rewrite with guidance
BLOCK_THRESHOLD = 40     # <40: hard block
MAX_REWRITE_ROUNDS = 3   # max rewrite attempts per chapter


@dataclass
class DimensionScore:
    """Single quality dimension score."""
    name: str
    score: int            # 0-100
    weight: float         # 0.0-1.0
    issues: List[str] = field(default_factory=list)
    markers: List[str] = field(default_factory=list)


@dataclass
class GateResult:
    """Complete quality gate evaluation result."""
    overall_score: int          # 0-100, floor-limited
    dimensions: List[DimensionScore]
    verdict: str                # "PASS" | "REWRITE" | "BLOCK"
    rewrite_guidance: str       # consolidated guidance for rewrite
    rewrite_round: int          # current round number
    continuity_critical: int    # count of critical continuity findings
    continuity_warnings: int    # count of warning continuity findings

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "dimensions": [
                {"name": d.name, "score": d.score, "weight": d.weight,
                 "issues": d.issues, "markers": d.markers}
                for d in self.dimensions
            ],
            "verdict": self.verdict,
            "rewrite_guidance": self.rewrite_guidance,
            "rewrite_round": self.rewrite_round,
            "continuity_critical": self.continuity_critical,
            "continuity_warnings": self.continuity_warnings,
        }

    def format_report(self, chapter_id: int) -> str:
        """Human-readable quality report."""
        emoji = {"PASS": "[OK]", "REWRITE": "[REWRITE]", "BLOCK": "[BLOCKED]"}.get(self.verdict, "[?]")
        lines = [
            f"\n{'='*60}",
            f"{emoji} Quality Gate Report — Chapter {chapter_id} (Round {self.rewrite_round})",
            f"  Overall: {self.overall_score}/100 (threshold: {PASS_THRESHOLD})",
            f"  Continuity: {self.continuity_critical} critical, {self.continuity_warnings} warnings",
            f"  Verdict: {self.verdict}",
            "",
        ]
        for d in self.dimensions:
            bar = "#" * (d["score"] // 10) + "-" * (10 - d["score"] // 10) if isinstance(d, dict) else "#" * (d.score // 10) + "-" * (10 - d.score // 10)
            name = d["name"] if isinstance(d, dict) else d.name
            score = d["score"] if isinstance(d, dict) else d.score
            issues = d.get("issues", []) if isinstance(d, dict) else d.issues
            lines.append(f"  {name:20s} {bar} {score}")
            for issue in issues[:3]:
                lines.append(f"    [!] {issue}")
            lines.append("")
        if self.rewrite_guidance:
            lines.append(f"  Guidance: {self.rewrite_guidance[:200]}")
        lines.append(f"{'='*60}\n")
        return "\n".join(lines)


# ── Dimension builders ────────────────────────────────────────────────────────

def _continuity_to_dimensions(findings: List[Finding]) -> List[DimensionScore]:
    """Convert continuity findings to scored dimensions."""
    if not findings:
        return [DimensionScore(name="连续性(Continuity)", score=100, weight=0.25)]

    critical = [f for f in findings if f.severity == "critical"]
    warnings = [f for f in findings if f.severity == "warning"]
    infos = [f for f in findings if f.severity == "info"]

    # Each critical costs 25 points, each warning costs 8, each info costs 2
    penalty = len(critical) * 25 + len(warnings) * 8 + len(infos) * 2
    score = max(5, 100 - penalty)

    issues = [f.format_cn() for f in critical + warnings[:5]]
    markers = [f.category for f in findings]

    return [DimensionScore(
        name="连续性(Continuity)",
        score=score,
        weight=0.25,
        issues=issues,
        markers=markers,
    )]


def _deai_to_dimensions(deai_report: Optional[dict]) -> List[DimensionScore]:
    """Convert DeAI report to scored dimensions."""
    if deai_report is None:
        return [DimensionScore(name="去AI味(DeAI)", score=100, weight=0.25)]

    dims = []
    for d in deai_report.get("dimensions", []):
        dims.append(DimensionScore(
            name=f"DeAI-{d['name']}",
            score=d["score"],
            weight=0.25 / max(len(deai_report.get("dimensions", [])), 1),
            issues=[f"{m}" for m in d.get("markers", [])[:3]],
            markers=d.get("markers", []),
        ))
    return dims if dims else [DimensionScore(name="去AI味(DeAI)", score=100, weight=0.25)]


def _diversity_to_dimension(fingerprints: list = None) -> DimensionScore:
    """Narrative diversity check (StoryScope 2026 anti-homogenization)."""
    if not fingerprints:
        return DimensionScore(name="叙事多样性(Diversity)", score=100, weight=0.10)

    from core.narrative_diversity import diversity_score
    score, issues = diversity_score(fingerprints)
    return DimensionScore(
        name="叙事多样性(Diversity)",
        score=score,
        weight=0.10,
        issues=issues,
        markers=[f"{len(fingerprints)} chapters analyzed"],
    )


def _editor_to_dimensions(editor_result: Optional[dict]) -> List[DimensionScore]:
    """Convert Editor Agent result to scored dimensions."""
    if editor_result is None:
        return [DimensionScore(name="编辑审稿(Editor)", score=80, weight=0.30, issues=["编辑审稿未执行"])]

    dims = []
    dims.append(DimensionScore(
        name="编辑审稿(Editor)",
        score=editor_result.get("score", 75),
        weight=0.30,
        issues=editor_result.get("issues", []),
    ))

    # Sub-dimensions from editor
    for sub in editor_result.get("sub_scores", []):
        dims.append(DimensionScore(
            name=f"Editor-{sub.get('name', '?')}",
            score=sub.get("score", 75),
            weight=0.0,  # sub-dimensions don't contribute to overall weight
            issues=sub.get("issues", []),
        ))

    return dims


# ── Gate evaluation ──────────────────────────────────────────────────────────

def evaluate(
    continuity_findings: List[Finding],
    deai_report: Optional[dict] = None,
    editor_result: Optional[dict] = None,
    rewrite_round: int = 1,
    diversity_fingerprints: list = None,
) -> GateResult:
    """
    Evaluate chapter quality across all dimensions.

    Returns GateResult with floor-limited overall score and verdict.
    """
    all_dims: List[DimensionScore] = []
    all_dims.extend(_continuity_to_dimensions(continuity_findings))
    all_dims.extend(_deai_to_dimensions(deai_report))
    all_dims.extend(_editor_to_dimensions(editor_result))
    all_dims.append(_diversity_to_dimension(diversity_fingerprints))

    # Floor principle: overall is limited by the weakest weighted dimension
    weighted_dims = [d for d in all_dims if d.weight > 0]
    if weighted_dims:
        floor_score = min(d.score for d in weighted_dims)
        weighted_avg = sum(d.score * d.weight for d in weighted_dims) / sum(d.weight for d in weighted_dims)
        # Floor applies: overall = min(weighted_avg, floor_score + 10)
        overall = int(min(weighted_avg, floor_score + 10))
    else:
        overall = 50

    # Verdict
    if rewrite_round > MAX_REWRITE_ROUNDS:
        verdict = "BLOCK"
    elif overall >= PASS_THRESHOLD:
        verdict = "PASS"
    elif overall >= REWRITE_MIN:
        verdict = "REWRITE"
    else:
        verdict = "BLOCK"

    # Build consolidated guidance for rewrite
    guidance_parts = []
    critical_count = 0
    warning_count = 0

    for f in continuity_findings:
        if f.severity == "critical":
            critical_count += 1
            guidance_parts.append(f"[连续性] {f.message} → {f.suggestion}")
        elif f.severity == "warning":
            warning_count += 1

    for d in all_dims:
        for issue in d.issues[:2]:
            if issue not in guidance_parts:
                guidance_parts.append(f"[{d.name}] {issue}")

    if deai_report and deai_report.get("suggestions"):
        for s in deai_report["suggestions"][:2]:
            guidance_parts.append(f"[DeAI] {s}")

    return GateResult(
        overall_score=overall,
        dimensions=all_dims,
        verdict=verdict,
        rewrite_guidance="; ".join(guidance_parts) if guidance_parts else "无重大问题",
        rewrite_round=rewrite_round,
        continuity_critical=critical_count,
        continuity_warnings=warning_count,
    )


# ── Quick evaluation (no Editor LLM call) ────────────────────────────────────

def evaluate_quick(
    continuity_findings: List[Finding],
    deai_report: Optional[dict] = None,
    rewrite_round: int = 1,
) -> GateResult:
    """
    Fast evaluation without Editor Agent (no LLM cost).
    Used as pre-check before deciding whether to invoke the Editor.
    """
    return evaluate(
        continuity_findings=continuity_findings,
        deai_report=deai_report,
        editor_result={"score": 80, "issues": [], "sub_scores": []},  # placeholder
        rewrite_round=rewrite_round,
    )


# ── Guidance aggregation for rewrite prompt ───────────────────────────────────

# Module-level cache for the last gate result (set by skill, read by scene_writer)
_last_gate_result: Optional[GateResult] = None


def get_last_result() -> Optional[GateResult]:
    """Get the last quality gate result (for scene_writer integration)."""
    return _last_gate_result


def set_last_result(result: GateResult) -> None:
    """Store the last quality gate result."""
    global _last_gate_result
    _last_gate_result = result

def build_rewrite_context(gate_result: GateResult) -> str:
    """Build a rewrite guidance block to inject into the next generation prompt."""
    if gate_result.verdict == "PASS":
        return ""

    parts = ["\n[Quality Gate Rewrite Guidance — Please address these issues]\n"]
    for d in gate_result.dimensions:
        if d.weight > 0 and d.score < 70:
            parts.append(f"\n{d.name} (Score: {d.score}/100):")
            for issue in d.issues[:5]:
                parts.append(f"  - {issue}")
    parts.append(f"\nOverall: {gate_result.overall_score}/100")
    parts.append(f"Round: {gate_result.rewrite_round}/{MAX_REWRITE_ROUNDS}")
    return "\n".join(parts)
