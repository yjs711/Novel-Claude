"""
大纲生命周期管理器 — 2026顶级标准(Goethe+Dante模式)

P2: 大纲回写循环 (Write→Audit→Update)
P3: 伏笔DAG管理
"""
from __future__ import annotations
import json, time, re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

@dataclass
class ArcNode:
    """弧线节点 — 10-15章的剧情循环单元"""
    number: int
    name: str
    chapter_range: list[int]  # [start, end]
    theme: str = ""
    emotion_unit: str = ""     # 情感单元
    cycle_type: str = ""       # 逆袭开端/目标确立/冲突升级/高潮释放/伏笔回收
    climax_chapter: int = 0
    status: str = "planned"    # planned/writing/done

@dataclass
class ForeshadowNode:
    """伏笔DAG节点"""
    id: str
    description: str
    planted_chapter: int
    target_resolve_chapter: int  # 预计回收章节
    resolved_chapter: int = 0    # 实际回收章节
    status: str = "planted"      # planted/progressing/resolved/abandoned
    related_characters: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # 依赖的其他伏笔ID

@dataclass
class ChapterAudit:
    """章节审计结果"""
    chapter: int
    generated_at: float
    word_count: int = 0
    emotional_beat_detected: str = ""
    emotional_deviation: bool = False     # 情感偏离大纲
    foreshadow_planted: list[str] = field(default_factory=list)
    foreshadow_paid: list[str] = field(default_factory=list)
    new_characters: list[str] = field(default_factory=list)
    arc_progress: float = 0.0            # 当前弧完成进度 0-1
    notes: str = ""

class OutlineManager:
    """大纲生命周期管理器"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self._audit_file = self.project_dir / "outline_audit.json"
        self._foreshadow_file = self.project_dir / "foreshadow_dag.json"
        self.audits: dict[int, ChapterAudit] = {}
        self.foreshadows: dict[str, ForeshadowNode] = {}
        self.load()

    # ── 持久化 ─────────────────────────────────────────────

    def load(self):
        if self._audit_file.exists():
            data = json.loads(self._audit_file.read_text(encoding="utf-8"))
            for k, v in data.get("audits", {}).items():
                self.audits[int(k)] = ChapterAudit(**v)
        if self._foreshadow_file.exists():
            data = json.loads(self._foreshadow_file.read_text(encoding="utf-8"))
            for k, v in data.get("nodes", {}).items():
                self.foreshadows[k] = ForeshadowNode(**v)

    def save(self):
        self._audit_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "audits": {str(k): asdict(v) for k, v in self.audits.items()},
            "meta": {"updated": time.time()}
        }
        self._audit_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        fs_data = {"nodes": {k: asdict(v) for k, v in self.foreshadows.items()}}
        self._foreshadow_file.write_text(json.dumps(fs_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 大纲回写循环 (P2) ──────────────────────────────────

    def audit_chapter(self, chapter_num: int, content: str, outline: dict) -> ChapterAudit:
        """
        章节写后审计: 检测实际输出与大纲的偏离。
        基于 NovelForge 2026 质量门 + InkOS 章节意图编译模式。
        """
        from core.emotion_analyzer import EmotionAnalyzer

        audit = ChapterAudit(chapter=chapter_num, generated_at=time.time(), word_count=len(content))

        # 1. 情感检测
        detected = EmotionAnalyzer.detect(content, chapter_num)
        audit.emotional_beat_detected = detected or "未知"

        # 2. 对比大纲期望情感
        expected = self._get_expected_emotion(outline, chapter_num)
        if detected and expected and detected != expected:
            audit.emotional_deviation = True
            audit.notes += f"情感偏离: 期望{expected}, 实际{detected}. "

        # 3. 伏笔检测 (简易关键词)
        foreshadow_keywords = ["秘密","隐藏","暗中","不为人知","日后","后来才知道","多年以后","才发现"]
        for kw in foreshadow_keywords:
            if kw in content:
                fid = f"fs_{chapter_num:04d}_{len(self.foreshadows)+1:03d}"
                node = ForeshadowNode(id=fid, description=f"ch{chapter_num}: {kw}...",
                                      planted_chapter=chapter_num, target_resolve_chapter=chapter_num+30)
                self.foreshadows[fid] = node
                audit.foreshadow_planted.append(fid)

        # 4. 计算弧进度
        arc_progress = self._calc_arc_progress(outline, chapter_num)
        audit.arc_progress = arc_progress

        self.audits[chapter_num] = audit
        self.save()
        return audit

    def _get_expected_emotion(self, outline: dict, chapter_num: int) -> Optional[str]:
        """从大纲中查找期望的情感基调"""
        for vol in outline.get("volumes", []):
            for arc in vol.get("arcs", []):
                cr = arc.get("chapter_range", [0, 0])
                if cr[0] <= chapter_num <= cr[1]:
                    return arc.get("emotion_unit")
            for ch in vol.get("chapters_list", []):
                if ch.get("number") == chapter_num and ch.get("emotional_beat"):
                    return ch["emotional_beat"]
        return None

    def _calc_arc_progress(self, outline: dict, chapter_num: int) -> float:
        """计算当前弧的完成进度"""
        for vol in outline.get("volumes", []):
            for arc in vol.get("arcs", []):
                cr = arc.get("chapter_range", [0, 0])
                if cr[0] <= chapter_num <= cr[1]:
                    total = cr[1] - cr[0] + 1
                    done = chapter_num - cr[0] + 1
                    return done / total if total > 0 else 0
        return 0.0

    def get_audit_summary(self, chapter_num: int) -> str:
        """生成章节审计摘要文本（可注入到下一章写作提示）"""
        audit = self.audits.get(chapter_num)
        if not audit:
            return ""

        parts = [f"【第{chapter_num}章审计】"]
        parts.append(f"字数: {audit.word_count} | 情感: {audit.emotional_beat_detected}")
        if audit.emotional_deviation:
            parts.append(f"⚠️ {audit.notes}")
        if audit.foreshadow_planted:
            parts.append(f"📌 新埋伏笔: {len(audit.foreshadow_planted)}个")
        if audit.foreshadow_paid:
            parts.append(f"✅ 回收伏笔: {len(audit.foreshadow_paid)}个")
        parts.append(f"弧进度: {audit.arc_progress:.0%}")
        return "\n".join(parts)

    # ── 伏笔DAG (P3) ──────────────────────────────────────

    def add_foreshadow(self, node: ForeshadowNode):
        self.foreshadows[node.id] = node

    def resolve_foreshadow(self, fid: str, chapter_num: int):
        """回收伏笔"""
        if fid in self.foreshadows:
            self.foreshadows[fid].status = "resolved"
            self.foreshadows[fid].resolved_chapter = chapter_num

    def get_overdue_foreshadows(self, current_chapter: int) -> list[ForeshadowNode]:
        """获取超期未回收的伏笔"""
        overdue = []
        for node in self.foreshadows.values():
            if (node.status == "planted"
                    and node.target_resolve_chapter < current_chapter
                    and current_chapter - node.target_resolve_chapter > 10):
                overdue.append(node)
        return overdue

    def get_foreshadow_dag(self) -> dict:
        """导出伏笔DAG数据(用于可视化)"""
        nodes = []
        links = []
        for n in self.foreshadows.values():
            nodes.append({"id": n.id, "label": n.description[:30],
                          "planted": n.planted_chapter, "target": n.target_resolve_chapter,
                          "status": n.status, "resolved": n.resolved_chapter})
            for dep in n.dependencies:
                links.append({"source": dep, "target": n.id})
        return {"nodes": nodes, "links": links}

    def get_unresolved_count(self) -> int:
        return sum(1 for n in self.foreshadows.values() if n.status == "planted")
