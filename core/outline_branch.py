"""
大纲分支与级联修改 — 辰东模式: "大纲是方向不是枷锁"

支持中途改剧情, 自动检测下游影响, 但不自动改写(人类决策优先)

用法:
    engine = OutlineBranchEngine(project_dir)
    engine.branch("alternative_ending")  # 创建分支
    impact = engine.check_impact(42, {"title": "新标题", ...})  # 检测改第42章的影响
    engine.apply_change(42, new_data, cascade=True)  # 应用修改, 标记下游需要复查
"""
from __future__ import annotations
import json, time, copy, hashlib
from pathlib import Path
from typing import Optional

class OutlineBranchEngine:
    """大纲分支与级联修改引擎"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self._outline_file = self.project_dir / "大纲.json"
        self._versions_dir = self.project_dir / "outline_versions"
        self._versions_dir.mkdir(parents=True, exist_ok=True)

    # ── 版本管理 ──────────────────────────────────────────

    def save_version(self, label: str = ""):
        """保存当前大纲版本（修改前自动调用）"""
        if not self._outline_file.exists():
            return None
        data = json.loads(self._outline_file.read_text(encoding="utf-8"))
        h = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:8]
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = f"{ts}_{h}_{label or 'snapshot'}.json"
        vp = self._versions_dir / fname
        vp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(vp)

    def list_versions(self) -> list[dict]:
        """列出所有保存的版本"""
        versions = []
        for vp in sorted(self._versions_dir.glob("*.json"), reverse=True):
            parts = vp.stem.split("_", 2)
            versions.append({
                "file": vp.name,
                "time": parts[0] + "_" + parts[1] if len(parts) >= 2 else "?",
                "hash": parts[1] if len(parts) >= 2 else "?",
                "label": parts[2] if len(parts) >= 3 else "",
            })
        return versions

    def restore_version(self, filename: str) -> bool:
        """恢复到指定版本"""
        vp = self._versions_dir / filename
        if not vp.exists():
            return False
        self.save_version("before_restore")
        data = json.loads(vp.read_text(encoding="utf-8"))
        self._outline_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    # ── 分支 ──────────────────────────────────────────────

    def branch(self, branch_name: str):
        """创建命名分支（不修改主分支）"""
        self.save_version(f"branch_point_{branch_name}")
        if not self._outline_file.exists():
            return None
        data = json.loads(self._outline_file.read_text(encoding="utf-8"))
        bp = self._versions_dir / f"branch_{branch_name}.json"
        bp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(bp)

    def switch_branch(self, branch_name: str) -> bool:
        """切换到命名分支"""
        bp = self._versions_dir / f"branch_{branch_name}.json"
        if not bp.exists():
            return False
        self.save_version("before_switch")
        data = json.loads(bp.read_text(encoding="utf-8"))
        self._outline_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    def list_branches(self) -> list[str]:
        return [p.stem.replace("branch_", "") for p in self._versions_dir.glob("branch_*.json")]

    # ── 级联影响检测 ────────────────────────────────────

    def check_impact(self, changed_chapter: int, changes: dict) -> dict:
        """
        检测修改第N章大纲会对后续章节产生什么影响。
        不自动修改，只返回影响报告供人类决策。

        changes: {"title": "新标题", "emotional_beat": "愤怒", "summary": "新概要", ...}
        """
        if not self._outline_file.exists():
            return {"error": "无大纲文件"}

        data = json.loads(self._outline_file.read_text(encoding="utf-8"))
        impacted = []
        warnings = []

        for vol in data.get("volumes", []):
            for arc in vol.get("arcs", []):
                cr = arc.get("chapter_range", [0, 0])
                if cr[0] <= changed_chapter <= cr[1]:
                    # 检查弧内后续章节
                    for ch in vol.get("chapters_list", []):
                        if ch["number"] > changed_chapter and ch["number"] <= cr[1]:
                            # 检测影响
                            if changes.get("emotional_beat") and ch.get("emotional_beat") == changes.get("emotional_beat"):
                                impacted.append({
                                    "chapter": ch["number"],
                                    "title": ch.get("title", ""),
                                    "reason": f"情感基调继承自第{changed_chapter}章",
                                    "suggest": "检查是否需要调整情感过渡",
                                })
                            # 伏笔影响
                            if ch.get("foreshadowing", {}).get("planted"):
                                for fs in ch["foreshadowing"]["planted"]:
                                    warnings.append(f"第{changed_chapter}章改动可能影响第{ch['number']}章的伏笔: {fs}")

        # 弧级影响
        for vol in data.get("volumes", []):
            for arc in vol.get("arcs", []):
                cr = arc.get("chapter_range", [0, 0])
                if changed_chapter in cr:
                    impacted.append({
                        "type": "arc",
                        "name": arc.get("name", ""),
                        "range": cr,
                        "reason": f"第{changed_chapter}章属于此弧, 修改可能影响弧的完整性",
                    })

        return {
            "changed_chapter": changed_chapter,
            "changes": changes,
            "impacted_chapters": len(impacted),
            "impacted_details": impacted[:10],
            "warnings": warnings[:5],
            "suggestion": "建议检查上述章节, 确认是否需要调整。选择「应用修改」将标记这些章节为「需复查」。",
        }

    def apply_change(self, changed_chapter: int, new_data: dict, cascade: bool = False):
        """
        应用大纲修改。如果 cascade=True, 标记下游章节为「需复查」。
        """
        self.save_version(f"before_ch{changed_chapter}_change")
        data = json.loads(self._outline_file.read_text(encoding="utf-8"))

        # 更新目标章节
        for vol in data.get("volumes", []):
            for ch in vol.get("chapters_list", []):
                if ch["number"] == changed_chapter:
                    for k, v in new_data.items():
                        if k in ch: ch[k] = v
                    ch["_last_modified"] = time.strftime("%Y-%m-%d %H:%M")

        # 级联标记
        if cascade:
            impact = self.check_impact(changed_chapter, new_data)
            for item in impact.get("impacted_details", []):
                if "chapter" in item:
                    cn = item["chapter"]
                    for vol in data.get("volumes", []):
                        for ch in vol.get("chapters_list", []):
                            if ch["number"] == cn:
                                ch["_needs_review"] = True
                                ch["_review_reason"] = item.get("reason", "")
                                ch.setdefault("status", "planned")

        self._outline_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 检查是否需要保存为分支
        arc_names = [a.get("name","") for v in data.get("volumes",[]) for a in v.get("arcs",[])
                     if a.get("chapter_range",[0,0])[0]<=changed_chapter<=a.get("chapter_range",[0,0])[1]]
        if arc_names:
            self.branch(f"auto_ch{changed_chapter}_{arc_names[0]}")

        return impact if cascade else None

    def list_review_needed(self) -> list[dict]:
        """列出所有标记为「需复查」的章节"""
        if not self._outline_file.exists():
            return []
        data = json.loads(self._outline_file.read_text(encoding="utf-8"))
        needs_review = []
        for vol in data.get("volumes", []):
            for ch in vol.get("chapters_list", []):
                if ch.get("_needs_review"):
                    needs_review.append({
                        "chapter": ch["number"],
                        "title": ch.get("title", ""),
                        "reason": ch.get("_review_reason", ""),
                    })
        return needs_review
