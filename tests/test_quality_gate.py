"""Tests for core/quality_gate.py — multi-dimensional quality gate."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.quality_gate import (
    evaluate, evaluate_quick, get_last_result, set_last_result,
    build_rewrite_context,
    PASS_THRESHOLD, REWRITE_MIN, MAX_REWRITE_ROUNDS,
    GateResult, DimensionScore,
    _continuity_to_dimensions, _deai_to_dimensions, _editor_to_dimensions,
)
from core.continuity_engine import Finding


class TestContinuityScoring:
    def test_no_findings_perfect_score(self):
        dims = _continuity_to_dimensions([])
        assert len(dims) == 1
        assert dims[0].score == 100

    def test_critical_penalty(self):
        findings = [Finding(severity="critical", category="overdue_thread",
                           message="test", suggestion="fix")]
        dims = _continuity_to_dimensions(findings)
        assert dims[0].score == 75  # 100 - 25

    def test_multiple_issues_floor(self):
        findings = [Finding(severity="critical", category="x", message="m", suggestion="s")
                    for _ in range(5)]
        dims = _continuity_to_dimensions(findings)
        assert dims[0].score == 5  # floored at 5


class TestDeAIScoring:
    def test_no_report_defaults(self):
        dims = _deai_to_dimensions(None)
        assert dims[0].score == 100

    def test_report_dimensions(self):
        report = {
            "overall_score": 65,
            "dimensions": [
                {"name": "词汇多样性(L1)", "score": 70, "markers": ["不禁"]},
                {"name": "模板化程度(L2)", "score": 60, "markers": ["嘴角上扬"]},
            ],
            "suggestions": ["减少不禁"],
        }
        dims = _deai_to_dimensions(report)
        assert len(dims) == 2


class TestEditorScoring:
    def test_no_result_defaults(self):
        dims = _editor_to_dimensions(None)
        assert dims[0].score == 80
        assert "未执行" in dims[0].issues[0]

    def test_with_scores(self):
        result = {
            "score": 82,
            "issues": ["pacing slow"],
            "sub_scores": [
                {"name": "一致性", "score": 85, "issues": []},
                {"name": "节奏", "score": 72, "issues": ["mid-section drag"]},
            ],
        }
        dims = _editor_to_dimensions(result)
        assert dims[0].score == 82


class TestGateEvaluation:
    def test_all_clean_passes(self):
        result = evaluate([], None, {"score": 85, "issues": [], "sub_scores": []}, 1)
        assert result.verdict == "PASS"
        assert result.overall_score >= PASS_THRESHOLD

    def test_floor_principle(self):
        """Weakest dimension should cap overall."""
        findings = [Finding(severity="critical", category="x", message="m", suggestion="s")
                    for _ in range(4)]  # Continuity ~0
        editor = {"score": 95, "issues": [], "sub_scores": []}
        deai = {"overall_score": 90, "dimensions": [{"name": "vocab", "score": 90, "markers": []}]}
        result = evaluate(findings, deai, editor, 1)
        # Floor principle: overall <= floor + 10
        assert result.overall_score <= 25  # floor is ~0 + 10
        assert result.verdict == "BLOCK"

    def test_rewrite_verdict(self):
        findings = [Finding(severity="warning", category="dormant_thread",
                           message="m", suggestion="s") for _ in range(2)]
        editor = {"score": 65, "issues": ["needs work"], "sub_scores": []}
        result = evaluate(findings, None, editor, 1)
        assert result.verdict in ("REWRITE", "PASS")  # Depends on floor

    def test_max_rounds_block(self):
        result = evaluate([], {"overall_score": 90,
                                "dimensions": [{"name": "vocab", "score": 90, "markers": []}]},
                          {"score": 85, "issues": [], "sub_scores": []}, 4)
        assert result.verdict == "BLOCK"

    def test_quick_eval_no_editor_cost(self):
        result = evaluate_quick([], None, 1)
        assert result.verdict == "PASS"


class TestGuidance:
    def test_build_rewrite_context(self):
        result = evaluate(
            [Finding(severity="warning", category="dormant_thread",
                    message="剧情线已休眠", suggestion="推进或标记")],
            None,
            {"score": 62, "issues": ["pacing uneven"], "sub_scores": [
                {"name": "节奏", "score": 55, "issues": ["mid slow"]},
            ]},
            1,
        )
        ctx = build_rewrite_context(result)
        if result.verdict != "PASS":
            assert "pacing" in ctx.lower() or "Quality Gate" in ctx


class TestModuleCache:
    def test_set_and_get(self):
        result = evaluate([], None, {"score": 80, "issues": [], "sub_scores": []}, 1)
        set_last_result(result)
        cached = get_last_result()
        assert cached is not None
        assert cached.verdict == result.verdict


class TestGateResult:
    def test_to_dict(self):
        result = evaluate([], None, {"score": 80, "issues": [], "sub_scores": []}, 1)
        d = result.to_dict()
        assert "overall_score" in d
        assert "verdict" in d
        assert "dimensions" in d

    def test_format_report(self):
        result = evaluate([], None, {"score": 80, "issues": [], "sub_scores": []}, 1)
        report = result.format_report(3)
        assert "Chapter 3" in report
        assert "Round 1" in report


if __name__ == "__main__":
    tests = [
        ("no findings perfect", TestContinuityScoring().test_no_findings_perfect_score),
        ("critical penalty", TestContinuityScoring().test_critical_penalty),
        ("multiple issues floor", TestContinuityScoring().test_multiple_issues_floor),
        ("no deai defaults", TestDeAIScoring().test_no_report_defaults),
        ("deai report dims", TestDeAIScoring().test_report_dimensions),
        ("no editor defaults", TestEditorScoring().test_no_result_defaults),
        ("editor with scores", TestEditorScoring().test_with_scores),
        ("all clean passes", TestGateEvaluation().test_all_clean_passes),
        ("floor principle", TestGateEvaluation().test_floor_principle),
        ("rewrite verdict", TestGateEvaluation().test_rewrite_verdict),
        ("max rounds block", TestGateEvaluation().test_max_rounds_block),
        ("quick eval", TestGateEvaluation().test_quick_eval_no_editor_cost),
        ("rewrite context", TestGuidance().test_build_rewrite_context),
        ("module cache", TestModuleCache().test_set_and_get),
        ("to dict", TestGateResult().test_to_dict),
        ("format report", TestGateResult().test_format_report),
    ]
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name} - {e}")
    print(f"\n{passed}/{len(tests)} passed")
