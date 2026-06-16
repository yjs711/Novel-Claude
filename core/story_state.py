"""
Novel-Claude Fusion — StoryState unified data model.

Ported from Novel-OS state_manager.py.
Provides Character, PlotThread, ChapterState, StyleProfile, TimelineEvent dataclasses
plus atomic JSON persistence with .bak rollback.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any


# ── dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class Character:
    """Represents a character in the story."""
    id: str
    full_name: str
    role: str = "supporting"  # protagonist, antagonist, supporting, minor
    age: Optional[int] = None
    physical_description: str = ""
    internal_desire: str = ""
    external_goal: str = ""
    fear: str = ""
    weakness: str = ""
    strength: str = ""
    secret: str = ""
    arc_stage: str = "beginning"
    arc_progress: int = 0
    relationships: Dict[str, str] = field(default_factory=dict)
    knowledge: List[str] = field(default_factory=list)
    possessions: List[str] = field(default_factory=list)
    current_location: str = ""
    emotional_state: str = ""
    last_appearance_chapter: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Character":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PlotThread:
    """Represents a plot thread or storyline."""
    id: str
    name: str
    description: str
    thread_type: str = "main"  # main, subplot, character_arc, mystery
    status: str = "active"  # active, resolved, abandoned, foreshadowed
    priority: int = 1
    start_chapter: int = 0
    target_resolution_chapter: Optional[int] = None
    related_characters: List[str] = field(default_factory=list)
    related_threads: List[str] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    foreshadowing_planted: List[int] = field(default_factory=list)
    last_updated_chapter: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlotThread":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ChapterState:
    """Represents the state of a single chapter."""
    number: int
    title: str = ""
    status: str = "planned"  # planned, drafting, drafted, editing, edited, validated, complete
    pov_character: str = ""
    location: str = ""
    time: str = ""
    word_count: int = 0
    target_word_count: int = 7000  # Novel-Claude default
    scenes: List[Dict[str, Any]] = field(default_factory=list)
    plot_advances: List[str] = field(default_factory=list)
    character_development: Dict[str, str] = field(default_factory=dict)
    emotional_beats: List[str] = field(default_factory=list)
    new_information: List[str] = field(default_factory=list)
    foreshadowing_planted: List[str] = field(default_factory=list)
    foreshadowing_resolved: List[str] = field(default_factory=list)
    hooks_start: List[str] = field(default_factory=list)
    hooks_end: List[str] = field(default_factory=list)
    continuity_checks: Dict[str, Any] = field(default_factory=dict)
    quality_scores: Dict[str, float] = field(default_factory=dict)
    last_modified: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StyleProfile:
    """Defines the writing style."""
    name: str = "default"
    description: str = ""
    tone: str = "neutral"
    point_of_view: str = "third_limited"
    tense: str = "past"
    prose_style: str = "balanced"
    avg_sentence_length: int = 15
    vocabulary_level: str = "moderate"
    dialogue_ratio: float = 0.3
    description_ratio: float = 0.3
    internal_monologue_ratio: float = 0.2
    paragraph_max_sentences: int = 5
    chapter_target_words: int = 7000
    scene_break_marker: str = "***"
    dialect_notes: str = ""
    genre_conventions: List[str] = field(default_factory=list)
    forbidden_words: List[str] = field(default_factory=list)
    preferred_words: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StyleProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TimelineEvent:
    """An event on the story timeline."""
    id: str
    description: str
    chapter: int
    day: Optional[int] = None
    time: Optional[str] = None
    location: str = ""
    characters_present: List[str] = field(default_factory=list)
    event_type: str = "scene"
    significance: str = "minor"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineEvent":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── StoryState container ────────────────────────────────────────────────────

@dataclass
class StoryState:
    """Central state container. Serialized as JSON."""
    title: str = ""
    genre: str = ""
    created: str = ""
    version: str = "1.0"

    characters: Dict[str, Character] = field(default_factory=dict)
    plot_threads: Dict[str, PlotThread] = field(default_factory=dict)
    chapters: Dict[int, ChapterState] = field(default_factory=dict)
    timeline: List[TimelineEvent] = field(default_factory=list)
    style_profile: StyleProfile = field(default_factory=StyleProfile)
    session_log: List[Dict[str, Any]] = field(default_factory=list)
    last_saved: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "genre": self.genre,
            "created": self.created,
            "version": self.version,
            "characters": {k: v.to_dict() for k, v in self.characters.items()},
            "plot_threads": {k: v.to_dict() for k, v in self.plot_threads.items()},
            "chapters": {str(k): v.to_dict() for k, v in self.chapters.items()},
            "timeline": [e.to_dict() for e in self.timeline],
            "style_profile": self.style_profile.to_dict(),
            "session_log": self.session_log,
            "last_saved": self.last_saved,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryState":
        state = cls(
            title=data.get("title", ""),
            genre=data.get("genre", ""),
            created=data.get("created", ""),
            version=data.get("version", "1.0"),
            session_log=data.get("session_log", []),
            last_saved=data.get("last_saved", ""),
        )
        for k, v in data.get("characters", {}).items():
            state.characters[k] = Character.from_dict(v)
        for k, v in data.get("plot_threads", {}).items():
            state.plot_threads[k] = PlotThread.from_dict(v)
        for k, v in data.get("chapters", {}).items():
            state.chapters[int(k)] = ChapterState.from_dict(v)
        for e in data.get("timeline", []):
            state.timeline.append(TimelineEvent.from_dict(e))
        if "style_profile" in data:
            state.style_profile = StyleProfile.from_dict(data["style_profile"])
        return state

    def log_action(self, action: str, details: Optional[Dict] = None):
        self.session_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details or {},
        })


# ── persistence ─────────────────────────────────────────────────────────────

def load_story_state(path: Path) -> StoryState:
    """Load StoryState from JSON file."""
    if not path.exists():
        return StoryState(created=datetime.now().isoformat())
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return StoryState.from_dict(data)


def save_story_state(state: StoryState, path: Path) -> None:
    """Atomic save with .bak rollback."""
    state.last_saved = datetime.now().isoformat()
    temp_path = path.with_suffix(".tmp")
    bak_path = path.with_suffix(".bak")

    # Write to temp
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)

    # Atomic replace
    if os.name == "nt":
        # Windows: os.replace works if target doesn't exist or we delete it first
        if path.exists():
            try:
                os.replace(str(path), str(bak_path))
            except OSError:
                pass  # backup is best-effort
        os.replace(str(temp_path), str(path))
    else:
        os.replace(str(temp_path), str(path))


def current_chapter(state: StoryState) -> int:
    """The highest-numbered chapter that is at least drafted; 0 if none."""
    drafted = [
        c.number for c in state.chapters.values()
        if c.status in ("drafted", "editing", "edited", "validated", "complete")
    ]
    return max(drafted) if drafted else 0


# ── volume-sharded persistence (500万字优化) ──────────────────────────────

CHAPTERS_PER_VOLUME = 70  # 每卷约70章，500万字 ≈ 7卷


def _vol_path(base: Path, vol: int) -> Path:
    return base.parent / f"{base.stem}_vol_{vol:02d}{base.suffix}"


def load_story_state_sharded(base_path: Path) -> StoryState:
    """按卷分片加载。base_path 是主文件（元数据+角色+剧情线）。"""
    if not base_path.exists():
        return StoryState(created=datetime.now().isoformat())

    with open(base_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 从分片文件加载章节
    vol = 1
    while True:
        vp = _vol_path(base_path, vol)
        if not vp.exists():
            break
        with open(vp, "r", encoding="utf-8") as f:
            vol_data = json.load(f)
        for k, v in vol_data.get("chapters", {}).items():
            data.setdefault("chapters", {})[k] = v
        vol += 1

    return StoryState.from_dict(data)


def save_story_state_sharded(state: StoryState, base_path: Path) -> None:
    """按卷分片保存。主文件存元数据，每70章一个分片文件。"""
    state.last_saved = datetime.now().isoformat()

    # 分组章节
    volumes: dict = {}
    for ch_num, ch in state.chapters.items():
        vol_idx = ((ch_num - 1) // CHAPTERS_PER_VOLUME) + 1
        if vol_idx not in volumes:
            volumes[vol_idx] = {}
        volumes[vol_idx][str(ch_num)] = ch.to_dict()

    # 保存主文件（不含章节）
    main_data = {
        "title": state.title, "genre": state.genre,
        "created": state.created, "version": state.version,
        "characters": {k: v.to_dict() for k, v in state.characters.items()},
        "plot_threads": {k: v.to_dict() for k, v in state.plot_threads.items()},
        "chapters": {},  # 章节存分片
        "timeline": [e.to_dict() for e in state.timeline],
        "style_profile": state.style_profile.to_dict(),
        "session_log": state.session_log,
        "last_saved": state.last_saved,
        "_shard_volumes": list(volumes.keys()),
    }
    _atomic_write(main_data, base_path)

    # 保存各卷分片
    for vol_idx, ch_data in volumes.items():
        vp = _vol_path(base_path, vol_idx)
        _atomic_write({"chapters": ch_data}, vp)


def _atomic_write(data: dict, path: Path) -> None:
    """原子写入"""
    temp_path = path.with_suffix(".tmp")
    bak_path = path.with_suffix(".bak")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if path.exists():
        try:
            os.replace(str(path), str(bak_path))
        except OSError:
            pass
    os.replace(str(temp_path), str(path))
