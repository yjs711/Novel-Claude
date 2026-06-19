"""
Novel-Claude Fusion — Subplot Manager

Manages multi-thread narrative tracking across long-form novels.
Addresses StoryScope 2026 finding: 79% AI stories have no subplots vs 57% human.

Core functions:
  1. Thread health scoring (dormant/active/overdue)
  2. Per-chapter thread allocation (which threads should this chapter advance)
  3. Subplot awareness injection for writing prompts

Works with existing StoryState.PlotThread and ContinuityEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.story_state import StoryState, PlotThread, ChapterState


# ── thread health ────────────────────────────────────────────────────────────

DORMANT_WARN_CHAPTERS = 3     # warn if thread inactive for 3+ chapters
OVERDUE_CRITICAL_CHAPTERS = 5  # critical if thread inactive for 5+ chapters


@dataclass
class ThreadStatus:
    """Runtime health status of a single plot thread."""
    thread_id: str
    thread_name: str
    thread_type: str          # main, subplot, character_arc, mystery
    status: str               # active, resolved, abandoned, foreshadowed
    last_chapter: int         # chapter where last updated
    target_chapter: Optional[int]  # planned resolution chapter
    chapters_dormant: int     # how many chapters since last update
    health: str               # "healthy", "dormant", "overdue", "resolved"
    priority: int


def assess_threads(state: "StoryState", current_chapter: int) -> List[ThreadStatus]:
    """Assess health of all plot threads relative to current chapter."""
    results = []
    for thread in state.plot_threads.values():
        last = thread.last_updated_chapter or thread.start_chapter or 0
        gap = current_chapter - last if last > 0 else current_chapter - (thread.start_chapter or 1)

        if thread.status == "resolved" or thread.status == "abandoned":
            health = "resolved"
        elif thread.target_resolution_chapter and current_chapter > thread.target_resolution_chapter:
            health = "overdue"
        elif thread.status == "active" and gap > OVERDUE_CRITICAL_CHAPTERS:
            health = "overdue"
        elif thread.status == "active" and gap > DORMANT_WARN_CHAPTERS:
            health = "dormant"
        elif thread.status == "active":
            health = "healthy"
        else:
            health = thread.status

        results.append(ThreadStatus(
            thread_id=thread.id,
            thread_name=thread.name,
            thread_type=thread.thread_type or "subplot",
            status=thread.status,
            last_chapter=last,
            target_chapter=thread.target_resolution_chapter,
            chapters_dormant=gap if thread.status == "active" else 0,
            health=health,
            priority=thread.priority or 1,
        ))

    # Sort: overdue first, then dormant, then by priority
    health_order = {"overdue": 0, "dormant": 1, "healthy": 2, "resolved": 3, "abandoned": 3}
    results.sort(key=lambda t: (health_order.get(t.health, 9), -t.priority))
    return results


# ── injection context ────────────────────────────────────────────────────────

def build_subplot_context(state: "StoryState", current_chapter: int,
                          max_threads: int = 5) -> str:
    """
    Build a subplot awareness block for injection into the chapter writing prompt.

    Tells the writer model:
      - Which threads are overdue and MUST be advanced
      - Which threads are dormant and should get attention
      - Which threads are healthy (reference only)
    """
    threads = assess_threads(state, current_chapter)
    if not threads:
        return ""

    parts = ["\n[Subplot Thread Status — Active narrative threads]\n"]

    overdue = [t for t in threads if t.health == "overdue"]
    dormant = [t for t in threads if t.health == "dormant"]
    healthy = [t for t in threads if t.health == "healthy"]

    shown = 0

    if overdue:
        parts.append("  [!] OVERDUE — Must advance in this chapter:")
        for t in overdue[:3]:
            target = f" (target: ch{t.target_chapter})" if t.target_chapter else ""
            parts.append(f"    - [{t.thread_type}] {t.thread_name}: {t.chapters_dormant} chapters dormant{target}")
            shown += 1

    if dormant and shown < max_threads:
        parts.append("  [~] DORMANT — Should get attention soon:")
        for t in dormant[:3]:
            parts.append(f"    - [{t.thread_type}] {t.thread_name}: {t.chapters_dormant} chapters since last update")
            shown += 1

    if healthy and shown < max_threads:
        parts.append("  [OK] ACTIVE — Reference available:")
        for t in healthy[:4]:
            parts.append(f"    - [{t.thread_type}] {t.thread_name} (P{t.priority})")
            shown += 1

    resolved = [t for t in threads if t.health == "resolved"]
    if resolved:
        parts.append(f"  [v] RESOLVED: {len(resolved)} threads completed")

    # Thread balance hint
    active_count = len(overdue) + len(dormant) + len(healthy)
    if active_count <= 1 and current_chapter > 10:
        parts.append("\n  [Hint] Only 1 active thread detected. Consider introducing subplot tension.")

    parts.append("")

    return "\n".join(parts)


# ── chapter-level thread advancement ─────────────────────────────────────────

def get_chapter_threads(chapter: "ChapterState") -> List[str]:
    """Extract which threads were advanced in a chapter from its plot_advances."""
    if not chapter.plot_advances:
        return []
    return [adv for adv in chapter.plot_advances if adv]


def suggest_thread_focus(thread_statuses: List[ThreadStatus],
                         max_focus: int = 3) -> List[str]:
    """
    Suggest which threads the next chapter should focus on.
    Prioritizes overdue threads, then dormant, then cycles through healthy.
    """
    suggestions = []

    # Always include overdue
    overdue = [t for t in thread_statuses if t.health == "overdue"]
    suggestions.extend(t.thread_name for t in overdue[:max_focus])

    # Add dormant if slots remain
    if len(suggestions) < max_focus:
        dormant = [t for t in thread_statuses if t.health == "dormant"]
        remaining = max_focus - len(suggestions)
        suggestions.extend(t.thread_name for t in dormant[:remaining])

    # Add active main thread if still no suggestions
    if not suggestions:
        main = [t for t in thread_statuses if t.thread_type == "main" and t.health == "healthy"]
        suggestions.extend(t.thread_name for t in main[:1])

    return suggestions[:max_focus]
