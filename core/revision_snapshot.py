"""
Novel-Claude Fusion — Revision Snapshot System

Save chapter snapshots + difflib HTML comparison.
Lightweight version control for manuscript revisions.

Usage:
  snap = save_snapshot(manuscript_dir, label="before gate rewrite")
  html = diff_snapshots(snap1, snap2, chapter_num=5)
"""

from __future__ import annotations

import difflib
import json
import os
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

from utils.logger import get_logger, log_step

logger = get_logger(__name__)

SNAPSHOT_DIR = Path(os.path.expanduser("~/.novel_claude_snapshots"))
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Snapshot:
    """A point-in-time capture of manuscript state."""
    id: str                    # timestamp-based: 20260619_112000
    label: str                 # user label: "before gate rewrite"
    created: str               # ISO timestamp
    chapter_count: int
    total_words: int
    chapters: Dict[int, str] = field(default_factory=dict)  # {num: content}
    path: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "created": self.created,
            "chapter_count": self.chapter_count, "total_words": self.total_words,
        }


def save_snapshot(manuscript_dir: str, label: str = "",
                  volume_id: int = None) -> Optional[Snapshot]:
    """
    Save a snapshot of the current manuscript state.

    Snapshot stored as JSON files in ~/.novel_claude_snapshots/
    """
    manuscript = Path(manuscript_dir)
    if not manuscript.exists():
        logger.error("Manuscript dir not found: %s", manuscript_dir)
        return None

    if volume_id:
        vol_dir = manuscript / f"vol_{volume_id:02d}"
        chapter_files = sorted(vol_dir.glob("ch_*_final.md")) if vol_dir.exists() else []
    else:
        chapter_files = sorted(manuscript.rglob("ch_*_final.md"))

    if not chapter_files:
        logger.warning("No chapter files to snapshot")
        return None

    snap_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    chapters = {}
    total_words = 0

    for cf in chapter_files:
        try:
            ch_num = int(cf.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        content = cf.read_text(encoding="utf-8")
        chapters[ch_num] = content
        total_words += len(content)

    snap = Snapshot(
        id=snap_id,
        label=label or f"Snapshot {snap_id}",
        created=datetime.now().isoformat(),
        chapter_count=len(chapters),
        total_words=total_words,
        chapters=chapters,
    )

    # Save to disk
    snap_path = SNAPSHOT_DIR / f"snapshot_{snap_id}.json"
    snap.path = str(snap_path)

    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump({
            "id": snap.id, "label": snap.label, "created": snap.created,
            "chapter_count": snap.chapter_count, "total_words": snap.total_words,
            "chapters": {str(k): v for k, v in chapters.items()},
        }, f, ensure_ascii=False)

    log_step("Snapshot saved", id=snap_id, label=label, chapters=len(chapters),
             words=total_words)
    logger.success("Snapshot %s: %d chapters, %d chars", snap_id, len(chapters), total_words)
    return snap


def load_snapshot(snapshot_id: str) -> Optional[Snapshot]:
    """Load a previously saved snapshot."""
    snap_path = SNAPSHOT_DIR / f"snapshot_{snapshot_id}.json"
    if not snap_path.exists():
        return None

    with open(snap_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chapters = {int(k): v for k, v in data.get("chapters", {}).items()}
    return Snapshot(
        id=data["id"], label=data.get("label", ""),
        created=data.get("created", ""),
        chapter_count=data.get("chapter_count", len(chapters)),
        total_words=data.get("total_words", sum(len(v) for v in chapters.values())),
        chapters=chapters, path=str(snap_path),
    )


def list_snapshots() -> List[dict]:
    """List all saved snapshots."""
    snaps = []
    for f in sorted(SNAPSHOT_DIR.glob("snapshot_*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            snaps.append({
                "id": data["id"], "label": data.get("label", ""),
                "created": data.get("created", ""),
                "chapter_count": data.get("chapter_count", 0),
                "total_words": data.get("total_words", 0),
            })
        except Exception:
            pass
    return snaps


def diff_snapshots(snap1_id: str, snap2_id: str, chapter_num: int,
                   output_format: str = "html") -> Optional[str]:
    """
    Compare a chapter between two snapshots.

    Args:
        snap1_id, snap2_id: Snapshot IDs
        chapter_num: Which chapter to compare
        output_format: "html" (color-coded) or "unified" (patch-style)

    Returns:
        HTML diff string, unified diff string, or None if snapshots not found.
    """
    snap1 = load_snapshot(snap1_id)
    snap2 = load_snapshot(snap2_id)
    if not snap1 or not snap2:
        return None

    text1 = snap1.chapters.get(chapter_num, "")
    text2 = snap2.chapters.get(chapter_num, "")

    if not text1 and not text2:
        return None

    lines1 = text1.splitlines(keepends=True)
    lines2 = text2.splitlines(keepends=True)

    if output_format == "html":
        differ = difflib.HtmlDiff(wrapcolumn=80)
        return differ.make_file(
            lines1, lines2,
            fromdesc=f"{snap1.label} (ch{chapter_num})",
            todesc=f"{snap2.label} (ch{chapter_num})",
        )
    else:
        diff = difflib.unified_diff(
            lines1, lines2,
            fromfile=f"{snap1.label}_ch{chapter_num}",
            tofile=f"{snap2.label}_ch{chapter_num}",
        )
        return "".join(diff)


def delete_snapshot(snapshot_id: str) -> bool:
    """Delete a snapshot."""
    snap_path = SNAPSHOT_DIR / f"snapshot_{snapshot_id}.json"
    if snap_path.exists():
        snap_path.unlink()
        logger.info("Deleted snapshot %s", snapshot_id)
        return True
    return False
