"""
Novel-Claude Fusion — Deterministic Continuity Engine.

Ported from Novel-OS continuity_engine.py.
Runs FAST, FREE checks (zero tokens) before LLM validation.
9 checks: dormant threads, overdue threads, unresolved foreshadowing,
absent characters, dead characters, chapter file consistency,
status drift, thin characters, never appeared.

Usage:
    from core.continuity_engine import run_all, summarize, Finding
    findings = run_all(story_state, project_path)
    if any(f.severity == "critical" for f in findings):
        print("FIX THESE FIRST")
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.story_state import StoryState


# Tunables
DORMANT_THREAD_GAP_CHAPTERS = 3
ABSENT_CHARACTER_GAP_CHAPTERS = 5
DEAD_KEYWORDS = ("dead", "killed", "deceased", "died", "死亡", "被杀", "死去", "已死")

# Cache for directory scans (避免每次检查都 iterdir)
_file_cache: dict = {}


# ── Finding ──────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    severity: str  # "critical" | "warning" | "info"
    category: str  # e.g. "dormant_thread"
    message: str
    suggestion: str = ""
    chapter: Optional[int] = None
    entity_id: Optional[str] = None

    def format(self) -> str:
        head = f"[{self.severity.upper()}] {self.category}"
        if self.chapter is not None:
            head += f" (ch{self.chapter})"
        body = f"  {self.message}"
        tail = f"  -> {self.suggestion}" if self.suggestion else ""
        return "\n".join(p for p in (head, body, tail) if p)

    def to_dict(self) -> dict:
        return asdict(self)

    def format_cn(self) -> str:
        """Chinese-localized format."""
        sev_map = {"critical": "严重", "warning": "警告", "info": "提示"}
        cat_map = {
            "dormant_thread": "休眠线索",
            "overdue_thread": "逾期线索",
            "unresolved_foreshadowing": "未回收伏笔",
            "absent_character": "角色缺席",
            "never_appeared": "从未登场",
            "dead_character_state": "已死角色状态异常",
            "missing_chapter_file": "缺失章节文件",
            "status_drift": "状态漂移",
            "thin_character": "角色信息不足",
        }
        sev = sev_map.get(self.severity, self.severity)
        cat = cat_map.get(self.category, self.category)
        head = f"[{sev}] {cat}"
        if self.chapter:
            head += f" 第{self.chapter}章"
        return f"{head}\n  {self.message}\n  → {self.suggestion}"


# ── checks ───────────────────────────────────────────────────────────────────

def _current_chapter(state: "StoryState") -> int:
    drafted = [
        c.number for c in state.chapters.values()
        if c.status in ("drafted", "editing", "edited", "validated", "complete")
    ]
    return max(drafted) if drafted else 0


def check_dormant_threads(state: "StoryState", as_of_chapter: Optional[int] = None) -> List[Finding]:
    cur = as_of_chapter if as_of_chapter is not None else _current_chapter(state)
    if cur == 0:
        return []
    out: List[Finding] = []
    for thread in state.plot_threads.values():
        if thread.status != "active":
            continue
        last_seen = thread.last_updated_chapter or thread.start_chapter or 0
        gap = cur - last_seen
        if gap > DORMANT_THREAD_GAP_CHAPTERS:
            out.append(Finding(
                severity="warning",
                category="dormant_thread",
                message=f"剧情线'{thread.name}'已{gap}章未推进（上次出现: 第{last_seen}章）",
                suggestion="在下一章推动该线索，或标记为已解决/已放弃。",
                chapter=cur,
                entity_id=thread.id,
            ))
    return out


def check_overdue_threads(state: "StoryState", as_of_chapter: Optional[int] = None) -> List[Finding]:
    cur = as_of_chapter if as_of_chapter is not None else _current_chapter(state)
    out: List[Finding] = []
    for thread in state.plot_threads.values():
        if thread.status != "active":
            continue
        target = thread.target_resolution_chapter
        if target and cur > target:
            out.append(Finding(
                severity="critical",
                category="overdue_thread",
                message=f"剧情线'{thread.name}'应在第{target}章收束，当前已到第{cur}章仍未解决",
                suggestion="立即收束、放弃该线，或推迟target_resolution_chapter。",
                chapter=cur,
                entity_id=thread.id,
            ))
    return out


def check_unresolved_foreshadowing(state: "StoryState", as_of_chapter: Optional[int] = None) -> List[Finding]:
    cur = as_of_chapter if as_of_chapter is not None else _current_chapter(state)
    if cur == 0:
        return []
    resolved_all: set = set()
    for ch in state.chapters.values():
        for r in ch.foreshadowing_resolved:
            resolved_all.add(r.strip().lower())
    out: List[Finding] = []
    for ch in sorted(state.chapters.values(), key=lambda c: c.number):
        if ch.number > cur:
            continue
        gap = cur - ch.number
        if gap < DORMANT_THREAD_GAP_CHAPTERS:
            continue
        for fs in ch.foreshadowing_planted:
            key = fs.strip().lower()
            if key in resolved_all:
                continue
            if any(key in r or r in key for r in resolved_all):
                continue
            out.append(Finding(
                severity="warning",
                category="unresolved_foreshadowing",
                message=f"第{ch.number}章埋下的伏笔尚未回收（{gap}章未回收）: {fs[:80]}",
                suggestion="安排回收、暗示或记录为已知。",
                chapter=ch.number,
            ))
    return out


def check_absent_characters(state: "StoryState", as_of_chapter: Optional[int] = None) -> List[Finding]:
    cur = as_of_chapter if as_of_chapter is not None else _current_chapter(state)
    if cur == 0:
        return []
    out: List[Finding] = []
    for char in state.characters.values():
        if char.role in ("minor",):
            continue
        if char.last_appearance_chapter == 0:
            if char.role in ("protagonist", "antagonist"):
                out.append(Finding(
                    severity="warning",
                    category="never_appeared",
                    message=f"{char.full_name}（{char.role}）尚未在任何章节登场",
                    suggestion="尽快引入或降级角色定位。",
                    entity_id=char.id,
                ))
            continue
        gap = cur - char.last_appearance_chapter
        if gap > ABSENT_CHARACTER_GAP_CHAPTERS:
            out.append(Finding(
                severity="warning",
                category="absent_character",
                message=f"{char.full_name}（{char.role}）已{gap}章未登场（最后: 第{char.last_appearance_chapter}章）",
                suggestion="安排重新出场或记录缺席原因。",
                chapter=cur,
                entity_id=char.id,
            ))
    return out


def check_dead_characters_reappearing(state: "StoryState") -> List[Finding]:
    out: List[Finding] = []
    for char in state.characters.values():
        es = (char.emotional_state or "").lower()
        notes = (char.notes or "").lower()
        died_marker = any(k in es or k in notes for k in DEAD_KEYWORDS)
        if not died_marker:
            continue
        out.append(Finding(
            severity="warning",
            category="dead_character_state",
            message=f"{char.full_name}已被标记为死亡，但状态追踪中仍有活跃记录（最后出场: 第{char.last_appearance_chapter}章）",
            suggestion="如为复活/回忆杀，请明确记录；否则将角色状态冻结。",
            entity_id=char.id,
        ))
    return out


def check_required_character_fields(state: "StoryState") -> List[Finding]:
    out: List[Finding] = []
    for char in state.characters.values():
        if char.role in ("protagonist", "antagonist") and not char.internal_desire:
            out.append(Finding(
                severity="info",
                category="thin_character",
                message=f"{char.full_name}（{char.role}）缺少内心欲望(internal_desire)设定",
                suggestion="为主角/反派设定核心价值观和内在驱动力。",
                entity_id=char.id,
            ))
    return out


def _scan_manuscript_files(project_path: Path) -> set:
    """Scan manuscript dirs once, cache results."""
    cache_key = str(project_path)
    if cache_key in _file_cache:
        return _file_cache[cache_key]

    found_files = set()
    manuscript = project_path / "manuscripts"
    if manuscript.exists():
        for vol_dir in manuscript.iterdir():
            if vol_dir.is_dir():
                for f in vol_dir.glob("ch_*_final.md"):
                    try:
                        found_files.add(int(f.stem.split("_")[1]))
                    except (ValueError, IndexError):
                        pass
                for f in vol_dir.glob("ch_*_temp.md"):
                    try:
                        found_files.add(int(f.stem.split("_")[1]))
                    except (ValueError, IndexError):
                        pass
    _file_cache[cache_key] = found_files
    return found_files


def check_chapter_file_consistency(state: "StoryState", project_path: Path) -> List[Finding]:
    """Mismatches between chapter.status and what files exist on disk. Cached scan."""
    out: List[Finding] = []
    found_files = _scan_manuscript_files(project_path)
    for ch in state.chapters.values():
        found = ch.number in found_files
        if ch.status in ("complete", "validated", "edited") and not found:
            out.append(Finding(
                severity="critical",
                category="missing_chapter_file",
                message=f"第{ch.number}章状态为'{ch.status}'，但找不到对应稿件文件",
                suggestion="重新生成该章，或修正状态字段。",
                chapter=ch.number,
            ))
        if ch.status == "planned" and found:
            out.append(Finding(
                severity="info",
                category="status_drift",
                message=f"第{ch.number}章已有稿件文件，但状态仍为'planned'",
                suggestion="将状态更新为'drafted'。",
                chapter=ch.number,
            ))
    return out


# ── runners ──────────────────────────────────────────────────────────────────

ALL_CHECKS = (
    check_dormant_threads,
    check_overdue_threads,
    check_unresolved_foreshadowing,
    check_absent_characters,
    check_dead_characters_reappearing,
    check_required_character_fields,
    check_chapter_file_consistency,
)


def run_all(state: "StoryState", project_path: Optional[Path] = None,
            as_of_chapter: Optional[int] = None) -> List[Finding]:
    """Run every applicable check. project_path enables file-consistency checks."""
    out: List[Finding] = []
    for check in ALL_CHECKS:
        try:
            if check == check_chapter_file_consistency:
                if project_path is not None:
                    out.extend(check(state, project_path))
            elif check in (check_dead_characters_reappearing, check_required_character_fields):
                out.extend(check(state))
            else:
                out.extend(check(state, as_of_chapter))
        except Exception as e:
            out.append(Finding(
                severity="info",
                category="check_error",
                message=f"连续性检查 {check.__name__} 执行出错: {e}",
            ))
    return out


def summarize(findings: List[Finding]) -> str:
    if not findings:
        return "✅ 连续性引擎：未发现问题。"
    by_severity = {"critical": [], "warning": [], "info": []}
    for f in findings:
        by_severity.setdefault(f.severity, []).append(f)
    lines = [
        f"🔍 连续性引擎：发现 {len(findings)} 个问题 "
        f"（严重: {len(by_severity['critical'])}, "
        f"警告: {len(by_severity['warning'])}, "
        f"提示: {len(by_severity['info'])}）\n"
    ]
    for sev in ("critical", "warning", "info"):
        for f in by_severity.get(sev, []):
            lines.append(f.format_cn())
            lines.append("")
    return "\n".join(lines).rstrip()


def to_context_block(findings: List[Finding]) -> str:
    """Render findings as context to inject into Editor/Guardian LLM prompt."""
    if not findings:
        return "确定性预检：未发现问题。\n"
    lines = ["确定性预检发现（请在审稿中核实并处理）：", ""]
    for f in findings:
        head = f"- [{f.severity.upper()}] {f.category}"
        if f.chapter is not None:
            head += f" 第{f.chapter}章"
        lines.append(head + ": " + f.message)
        if f.suggestion:
            lines.append(f"  建议: {f.suggestion}")
    return "\n".join(lines) + "\n"
