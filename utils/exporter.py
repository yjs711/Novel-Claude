"""
Novel-Claude Fusion — Manuscript Exporter

Markdown chapters → EPUB / PDF via pandoc.
Zero Python deps beyond stdlib (pandoc must be installed on system).

Usage:
  from utils.exporter import export_manuscript
  export_manuscript(manuscript_dir, "My Novel", format="epub")
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from utils.logger import get_logger, log_step

logger = get_logger(__name__)


def _find_pandoc() -> Optional[str]:
    """Locate pandoc binary. Returns path or None."""
    pandoc = shutil.which("pandoc")
    if pandoc:
        return pandoc
    # Windows common locations
    for loc in [
        r"C:\Program Files\Pandoc\pandoc.exe",
        r"C:\Program Files (x86)\Pandoc\pandoc.exe",
        Path.home() / "AppData" / "Local" / "Pandoc" / "pandoc.exe",
    ]:
        if Path(str(loc)).exists():
            return str(loc)
    return None


def _build_metadata_yaml(title: str, author: str = "", lang: str = "zh",
                         cover: str = "", description: str = "") -> str:
    """Build pandoc metadata YAML block."""
    lines = [
        "---",
        f"title: {title}",
        f"lang: {lang}",
        f"date: {datetime.now().strftime('%Y-%m-%d')}",
    ]
    if author:
        lines.append(f"author: {author}")
    if description:
        lines.append(f"description: {description}")
    if cover and Path(cover).exists():
        lines.append(f"cover-image: {cover}")
    lines.extend([
        "toc: true",
        "toc-depth: 2",
        "numbersections: false",
        f"---\n",
    ])
    return "\n".join(lines)


def export_manuscript(manuscript_dir: str, title: str,
                      output_dir: str = ".", format: str = "epub",
                      author: str = "", cover: str = "",
                      volume_id: int = None) -> Optional[Path]:
    """
    Export manuscript to EPUB or PDF.

    Args:
        manuscript_dir: Path to directory with ch_*_final.md files
        title: Book title
        output_dir: Where to write the output file
        format: "epub" or "pdf"
        author: Author name
        cover: Path to cover image (JPEG/PNG)
        volume_id: Optional volume filter (only export this volume)

    Returns:
        Path to output file, or None if pandoc not found or export failed.
    """
    pandoc = _find_pandoc()
    if not pandoc:
        logger.warning("pandoc not found. Install: https://pandoc.org/installing.html")
        return None

    manuscript = Path(manuscript_dir)
    if not manuscript.exists():
        logger.error("Manuscript dir not found: %s", manuscript_dir)
        return None

    # Find chapter files
    if volume_id:
        vol_dir = manuscript / f"vol_{volume_id:02d}"
        chapters = sorted(vol_dir.glob("ch_*_final.md")) if vol_dir.exists() else []
    else:
        chapters = sorted(manuscript.rglob("ch_*_final.md"))

    if not chapters:
        logger.warning("No chapter files found in %s", manuscript_dir)
        return None

    log_step("Export", title=title, format=format, chapters=len(chapters))

    # Build metadata
    metadata = _build_metadata_yaml(title, author, cover=cover)

    # Output filename
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:50].strip()
    ext = ".epub" if format == "epub" else ".pdf"
    output_path = Path(output_dir) / f"{safe_title}{ext}"

    # Build pandoc command
    cmd = [
        pandoc,
        "--from", "markdown+smart+yaml_metadata_block",
        "--toc", "--toc-depth=2",
        "--top-level-division=chapter",
    ]

    if format == "epub":
        cmd += ["--to", "epub3"]
        cmd += ["--metadata", f"title={title}"]
        if cover and Path(cover).exists():
            cmd += [f"--epub-cover-image={cover}"]
    else:
        # PDF with CJK support
        cmd += [
            "--pdf-engine=xelatex",
            "-V", "mainfont=Noto Serif CJK SC",
            "-V", "geometry:margin=1.2in",
            "-V", "fontsize=11pt",
            "-V", "documentclass=book",
        ]

    cmd += ["-o", str(output_path)]
    cmd += [str(c) for c in chapters]

    logger.info("Running: %s", " ".join(str(c) for c in cmd[:6]) + " ...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error("Pandoc failed: %s", result.stderr[:500])
            return None
    except subprocess.TimeoutExpired:
        logger.error("Pandoc timed out (300s)")
        return None
    except FileNotFoundError:
        logger.error("pandoc not found at %s", pandoc)
        return None

    size_mb = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0
    logger.success("Exported: %s (%.1f MB, %d chapters)", output_path.name, size_mb, len(chapters))
    log_step("Export complete", file=str(output_path), size_mb=round(size_mb, 1))

    return output_path


def export_all_volumes(manuscript_dir: str, title: str,
                       output_dir: str = ".", format: str = "epub",
                       author: str = "", cover: str = "") -> List[Path]:
    """Export each volume as a separate file."""
    manuscript = Path(manuscript_dir)
    vol_dirs = sorted(manuscript.glob("vol_*"))
    results = []
    for vd in vol_dirs:
        try:
            vol_id = int(vd.name.split("_")[1])
        except (IndexError, ValueError):
            continue
        vol_title = f"{title} - 第{vol_id}卷"
        result = export_manuscript(manuscript_dir, vol_title, output_dir,
                                   format, author, cover, volume_id=vol_id)
        if result:
            results.append(result)
    return results


def check_pandoc() -> dict:
    """Check pandoc availability and version."""
    pandoc = _find_pandoc()
    if not pandoc:
        return {"available": False, "install_hint": "https://pandoc.org/installing.html"}

    try:
        result = subprocess.run([pandoc, "--version"], capture_output=True, text=True, timeout=10)
        version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
        return {"available": True, "path": pandoc, "version": version_line}
    except Exception as e:
        return {"available": True, "path": pandoc, "error": str(e)}
