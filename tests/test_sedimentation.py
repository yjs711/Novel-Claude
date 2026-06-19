"""Tests for utils/sedimentation.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.sedimentation import (
    LightExtract, DeepExtract,
    validate_light_extract, validate_deep_extract,
    _cosine_similarity, _is_duplicate_light,
    LIGHT_EXTRACTION_PROMPT, DEEP_EXTRACTION_PROMPT, _parse_json_response,
)


class TestLightExtract:
    def test_valid_light_extract(self):
        data = {
            "character_state_changes": {},
            "character_knowledge_gained": {},
            "foreshadowing_planted": [],
            "foreshadowing_resolved": [],
            "foreshadowing_advancements": {},
            "plot_advances": ["主角突破元婴期"],
            "new_information": ["上古遗迹将在三日后开启"],
        }
        result = validate_light_extract(data)
        assert result is not None
        assert isinstance(result, LightExtract)
        assert result.plot_advances == ["主角突破元婴期"]

    def test_invalid_light_extract_missing_field(self):
        data = {"plot_advances": ["test"]}
        result = validate_light_extract(data)
        assert result is None

    def test_light_extract_to_dict(self):
        le = LightExtract(
            character_state_changes={"char_1": {"emotional_state": "愤怒"}},
            character_knowledge_gained={"char_1": ["发现叛徒身份"]},
            foreshadowing_planted=[{"text": "戒指发光", "confidence": 0.9}],
            foreshadowing_resolved=[],
            foreshadowing_advancements={},
            plot_advances=["主线推进"],
            new_information=["新地图开启"],
        )
        d = le.to_dict()
        assert d["character_state_changes"]["char_1"]["emotional_state"] == "愤怒"


class TestDeepExtract:
    def test_valid_deep_extract(self):
        data = {
            "emotional_arc_trend": "从低沉到爆发",
            "hook_quality_assessment": "悬念力度足够",
            "character_arc_evaluation": {},
            "pacing_diagnosis": "中段偏慢",
            "deai_concerns": ["句式重复"],
        }
        result = validate_deep_extract(data)
        assert result is not None
        assert isinstance(result, DeepExtract)


class TestDedup:
    def test_cosine_similarity_identical(self):
        a = "主角突破元婴期获得新能力"
        b = "主角突破元婴期获得新能力"
        sim = _cosine_similarity(a, b)
        assert sim > 0.9

    def test_cosine_similarity_different(self):
        a = "主角突破元婴期"
        b = "配角在酒楼吃饭"
        sim = _cosine_similarity(a, b)
        assert sim < 0.5

    def test_is_duplicate(self):
        existing = ["主角突破元婴期获得新能力", "发现上古遗迹秘密"]
        assert _is_duplicate_light("主角突破元婴期获得新能力", existing) is True
        assert _is_duplicate_light("一只猫走过街道", existing) is False


class TestPrompts:
    def test_light_prompt_contains_json_instruction(self):
        assert "JSON" in LIGHT_EXTRACTION_PROMPT
        assert "character_state_changes" in LIGHT_EXTRACTION_PROMPT

    def test_deep_prompt_contains_json_instruction(self):
        assert "JSON" in DEEP_EXTRACTION_PROMPT
        assert "emotional_arc_trend" in DEEP_EXTRACTION_PROMPT


class TestJsonParsing:
    def test_malformed_json_returns_none(self):
        result = _parse_json_response("这不是 JSON")
        assert result is None

    def test_partial_json_rejected(self):
        data = {"plot_advances": ["test"]}
        result = validate_light_extract(data)
        assert result is None


if __name__ == "__main__":
    passed = 0; failed = 0
    tests = [
        ("valid light extract", TestLightExtract().test_valid_light_extract),
        ("missing fields rejected", TestLightExtract().test_invalid_light_extract_missing_field),
        ("to_dict roundtrip", TestLightExtract().test_light_extract_to_dict),
        ("valid deep extract", TestDeepExtract().test_valid_deep_extract),
        ("cosine identical", TestDedup().test_cosine_similarity_identical),
        ("cosine different", TestDedup().test_cosine_similarity_different),
        ("duplicate detection", TestDedup().test_is_duplicate),
        ("light prompt JSON", TestPrompts().test_light_prompt_contains_json_instruction),
        ("deep prompt JSON", TestPrompts().test_deep_prompt_contains_json_instruction),
        ("malformed JSON rejected", TestJsonParsing().test_malformed_json_returns_none),
        ("partial JSON rejected", TestJsonParsing().test_partial_json_rejected),
    ]
    for name, fn in tests:
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
    print(f"\nTOTAL: {passed}P/{failed}F {'FAILURES' if failed else 'ALL PASS'}")
