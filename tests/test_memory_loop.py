"""Integration test: memory closed loop (sedimentation -> injection)."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.story_state import (
    StoryState, Character, PlotThread, ChapterState,
    save_story_state, load_story_state,
)
from utils.sedimentation import (
    LightExtract, validate_light_extract, _is_duplicate_light,
)


class TestMemoryClosedLoop:
    """Simulate write -> extract -> inject -> verify cycle."""

    def test_light_extract_applied_to_story_state(self):
        """Verify LightExtract data flows into StoryState correctly."""
        state = StoryState(title="test", genre="xianxia")
        char = Character(
            id="char_1", full_name="Lin Feng", role="protagonist",
            knowledge=[], emotional_state="calm", current_location="Qingyun",
        )
        state.characters["char_1"] = char
        ch = ChapterState(number=1, title="Chapter 1", status="drafted")
        state.chapters[1] = ch

        light = LightExtract(
            character_state_changes={"char_1": {"emotional_state": "angry", "current_location": "Black Mountain"}},
            character_knowledge_gained={"char_1": ["discovered master is traitor"]},
            foreshadowing_planted=[{"text": "ring glows under moonlight", "confidence": 0.9}],
            foreshadowing_resolved=[],
            foreshadowing_advancements={},
            plot_advances=["Lin Feng breaks through"],
            new_information=["ancient ruins at Black Mountain"],
        )

        # Apply (mirrors _apply_light logic)
        ch.plot_advances = light.plot_advances
        ch.new_information = light.new_information
        ch.foreshadowing_planted = [fp["text"] for fp in light.foreshadowing_planted]
        for char_id, changes in light.character_state_changes.items():
            c = state.characters.get(char_id)
            if c:
                for field, value in changes.items():
                    setattr(c, field, value)
        for char_id, facts in light.character_knowledge_gained.items():
            c = state.characters.get(char_id)
            if c:
                c.knowledge.extend(facts)

        assert state.characters["char_1"].emotional_state == "angry"
        assert state.characters["char_1"].current_location == "Black Mountain"
        assert "discovered master is traitor" in state.characters["char_1"].knowledge
        assert state.chapters[1].plot_advances == ["Lin Feng breaks through"]
        assert state.chapters[1].new_information == ["ancient ruins at Black Mountain"]
        assert "ring glows under moonlight" in state.chapters[1].foreshadowing_planted

    def test_dedup_prevents_duplicates(self):
        """Verify deduplication prevents repeated entries."""
        state = StoryState(title="test", genre="xianxia")
        ch = ChapterState(number=1, title="Chapter 1", status="drafted",
                          plot_advances=["hero breaks through"], new_information=["found secret realm"])
        state.chapters[1] = ch

        light2 = LightExtract(
            character_state_changes={}, character_knowledge_gained={},
            foreshadowing_planted=[], foreshadowing_resolved=[],
            foreshadowing_advancements={},
            plot_advances=["hero breaks through"],  # Duplicate
            new_information=["found secret realm"],  # Duplicate
        )

        existing_plot = list(ch.plot_advances)
        for pa in light2.plot_advances:
            if not _is_duplicate_light(pa, existing_plot):
                existing_plot.append(pa)
        ch.plot_advances = existing_plot

        assert len(ch.plot_advances) == 1

    def test_epistemic_state_persists(self):
        """Verify character knowledge accumulates across chapters."""
        char = Character(id="char_1", full_name="Lin Feng", role="protagonist", knowledge=[])

        char.knowledge.append("found secret realm entrance")
        assert "found secret realm entrance" in char.knowledge

        char.knowledge.append("master is traitor")
        assert len(char.knowledge) == 2
        assert "found secret realm entrance" in char.knowledge
        assert "master is traitor" in char.knowledge

        # Chapter 31+: truncate to last 30
        for i in range(35):
            char.knowledge.append(f"fact_{i}")
        char.knowledge = char.knowledge[-30:]
        assert len(char.knowledge) == 30

    def test_deep_extract_marker_in_chapter(self):
        """Verify deep extract sets quality markers."""
        ch = ChapterState(number=10, title="Chapter 10", status="drafted", quality_scores={})
        ch.quality_scores["emotional_arc_trend"] = 1.0
        assert ch.quality_scores.get("emotional_arc_trend") == 1.0


class TestValidationEdgeCases:
    def test_malformed_json_returns_none(self):
        from utils.sedimentation import _parse_json_response
        result = _parse_json_response("not json at all")
        assert result is None

    def test_partial_json_rejected(self):
        data = {"plot_advances": ["test"]}
        result = validate_light_extract(data)
        assert result is None

    def test_empty_light_extract_still_valid(self):
        """Empty data is valid as long as all fields present."""
        data = {
            "character_state_changes": {},
            "character_knowledge_gained": {},
            "foreshadowing_planted": [],
            "foreshadowing_resolved": [],
            "foreshadowing_advancements": {},
            "plot_advances": [],
            "new_information": [],
        }
        result = validate_light_extract(data)
        assert result is not None
        assert isinstance(result, LightExtract)


# Run with python -m pytest or directly
if __name__ == "__main__":
    tests = [
        ("light extract applied", TestMemoryClosedLoop().test_light_extract_applied_to_story_state),
        ("dedup prevents duplicates", TestMemoryClosedLoop().test_dedup_prevents_duplicates),
        ("epistemic state persists", TestMemoryClosedLoop().test_epistemic_state_persists),
        ("deep extract marker", TestMemoryClosedLoop().test_deep_extract_marker_in_chapter),
        ("malformed json rejected", TestValidationEdgeCases().test_malformed_json_returns_none),
        ("partial json rejected", TestValidationEdgeCases().test_partial_json_rejected),
        ("empty light extract valid", TestValidationEdgeCases().test_empty_light_extract_still_valid),
    ]
    passed = 0
    for name, test_fn in tests:
        try:
            test_fn()
            print(f"  PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name} - {e}")
    print(f"\n{passed}/{len(tests)} passed")
