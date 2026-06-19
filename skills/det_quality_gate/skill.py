"""
det_quality_gate — Multi-Dimensional Quality Gate Skill

Integrates three audit layers after chapter completion:
  Phase 1: Deterministic continuity checks (zero-token, 7 dimensions)
  Phase 2: DeAI detection (8 dimensions, regex-based, from shared_state)
  Phase 3: Editor Agent review (LLM, ReAct multi-turn)

Floor principle: weakest weighted dimension caps overall score.
Thresholds: >=70 PASS, 40-69 REWRITE, <40 BLOCK.
Max 3 rewrite rounds per chapter. On BLOCK, chapter is saved with BLOCKED marker.

Hooks: on_after_chapter_complete
"""

from pathlib import Path
from typing import Optional, List

from core.base_skill import BaseSkill
from core.story_state import StoryState
from core.quality_gate import (
    evaluate, evaluate_quick,
    build_rewrite_context, set_last_result,
    GateResult,
    PASS_THRESHOLD, REWRITE_MIN, MAX_REWRITE_ROUNDS,
)
from core.continuity_engine import run_all, Finding


class DetQualityGateSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "多维质量门控"
        self.rewrite_counts = {}  # {chapter_id: count}

    def on_init(self) -> None:
        print(f"  [OK] {self.name} ready (Continuity+DeAI+Editor -> Gate: "
              f">={PASS_THRESHOLD}PASS/{REWRITE_MIN}-{PASS_THRESHOLD-1}REWRITE/<{REWRITE_MIN}BLOCK, "
              f"max {MAX_REWRITE_ROUNDS} rounds)")

    def on_after_chapter_complete(self, chapter_id: int, full_text: str) -> None:
        """Run full quality gate evaluation after chapter completion."""
        if not full_text or len(full_text.strip()) < 100:
            return

        story_state: Optional[StoryState] = self.context.get_shared("story_state")

        # ── Phase 1: Continuity (zero-token) ──
        findings: List[Finding] = self.context.get_shared("continuity_findings", [])
        if not findings and story_state is not None:
            try:
                pp = Path(self.context.workspace.workspace_root) if hasattr(self.context.workspace, "workspace_root") else Path.cwd()
                findings = run_all(story_state, pp, as_of_chapter=chapter_id)
                self.context.set_shared("continuity_findings", findings)
            except Exception as e:
                print(f"  [!] {self.name}: continuity check failed: {e}")

        # ── Phase 2: DeAI (from shared_state, already computed by gen_deai_engine) ──
        deai_report = self.context.get_shared("deai_report")

        # ── Phase 3: Editor Agent (LLM, expensive) ──
        editor_result = self._run_editor_review(chapter_id, full_text)

        # ── Evaluate ──
        rewrite_round = self.rewrite_counts.get(chapter_id, 1)
        gate_result = evaluate(
            continuity_findings=findings,
            deai_report=deai_report,
            editor_result=editor_result,
            rewrite_round=rewrite_round,
        )

        # Print report
        print(gate_result.format_report(chapter_id))

        # Store result for scene_writer to check
        self.context.set_shared("quality_gate_result", gate_result)
        self.context.set_shared("quality_gate_verdict", gate_result.verdict)
        self.context.set_shared("quality_gate_guidance", gate_result.rewrite_guidance)
        set_last_result(gate_result)

    def check_only(self, chapter_id: int) -> GateResult:
        """
        Quick pre-check (no LLM cost) — continuity + deai only.
        Returns GateResult without editor dimensions.
        """
        findings: List[Finding] = self.context.get_shared("continuity_findings", [])
        deai_report = self.context.get_shared("deai_report")
        return evaluate_quick(
            continuity_findings=findings,
            deai_report=deai_report,
            rewrite_round=self.rewrite_counts.get(chapter_id, 1),
        )

    def record_rewrite(self, chapter_id: int) -> int:
        """Record a rewrite attempt, return new round number."""
        self.rewrite_counts[chapter_id] = self.rewrite_counts.get(chapter_id, 1) + 1
        return self.rewrite_counts[chapter_id]

    def should_block(self, chapter_id: int) -> bool:
        """Check if chapter has exceeded max rewrite rounds."""
        return self.rewrite_counts.get(chapter_id, 1) > MAX_REWRITE_ROUNDS

    def get_rewrite_context(self) -> str:
        """Get rewrite guidance from last gate result."""
        result: Optional[GateResult] = self.context.get_shared("quality_gate_result")
        if result is None:
            return ""
        return build_rewrite_context(result)

    def _run_editor_review(self, chapter_id: int, full_text: str) -> Optional[dict]:
        """Run Editor Agent review with scoring. Returns None if unavailable."""
        try:
            from core.agents.editor_agent import EditorAgent

            # Build beat requirements from outline
            beat_reqs = self._get_beat_requirements(chapter_id)

            editor = EditorAgent(max_iterations=3)
            result = editor.review_with_score(full_text, beat_reqs)
            return result
        except Exception as e:
            print(f"  [!] {self.name}: Editor Agent review failed: {e}")
            return None

    def _get_beat_requirements(self, chapter_id: int) -> str:
        """Try to get chapter outline for editor context."""
        try:
            outline = self.context.get_shared("current_outline")
            if outline:
                title = outline.get("title", f"Chapter {chapter_id}")
                overview = outline.get("overview", outline.get("summary", ""))
                return f"Title: {title}\nOverview: {overview}"
        except Exception:
            pass
        return f"Chapter {chapter_id} — review for quality"
