"""
角色状态管理器 — 2026 顶级标准 (NovelForge/Tianming/QMAI)

每个角色维护独立状态表，写前注入→写后自动更新。
灵感来源: 天命 15维事实快照 + NovelForge 状态表 + QMAI 角色认知系统
"""
from __future__ import annotations
import json, time, re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Any

@dataclass
class CharacterState:
    """角色状态快照"""
    id: str
    name: str
    role: str = "supporting"  # protagonist/antagonist/supporting/minor

    # 物理状态
    location: str = ""
    appearance: str = ""
    cultivation_level: str = ""   # 修仙境界
    power_items: list[str] = field(default_factory=list)  # 持有的重要物品

    # 心理状态
    current_goal: str = ""
    emotional_state: str = ""     # 当前情感
    beliefs: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)  # 角色已知的秘密

    # 关系
    relationships: dict[str, str] = field(default_factory=dict)  # {name: "盟友/敌人/暧昧/师徒/..."}

    # 出场记录
    first_appearance: int = 0
    last_appearance: int = 0
    total_appearances: int = 0

    # 元数据
    last_updated: float = field(default_factory=time.time)

class CharacterStateManager:
    """角色状态管理器 — 写前注入上下文, 写后自动检测变化并更新"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self._file = self.project_dir / "character_states.json"
        self.characters: dict[str, CharacterState] = {}
        self.load()

    # ── 持久化 ────────────────────────────────────────────

    def load(self):
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
                for k, v in data.get("characters", {}).items():
                    self.characters[k] = CharacterState(**v)
            except Exception:
                pass

    def save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = {"characters": {k: asdict(v) for k, v in self.characters.items()},
                "meta": {"updated": time.time(), "total": len(self.characters)}}
        self._file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 角色管理 ──────────────────────────────────────────

    def get_or_create(self, name: str, role: str = "supporting") -> CharacterState:
        """按名称查找或创建角色"""
        for c in self.characters.values():
            if c.name == name:
                return c
        cid = f"char_{len(self.characters)+1:03d}"
        cs = CharacterState(id=cid, name=name, role=role)
        self.characters[cid] = cs
        return cs

    def update_from_chapter(self, chapter_num: int, content: str):
        """
        写后自动更新: 从章节正文提取角色变化
        简易关键词规则, P2可升级为LLM提取
        """
        # 检测出场角色
        name_patterns = [
            r'([一-鿿]{2,3})(?:说道|问道|喊道|笑道|冷声道|低声道|淡淡道)',
            r'([一-鿿]{2,3})(?:走了|杀了|飞了|冲了|战了|修炼|突破)',
        ]
        detected_names = set()
        for pat in name_patterns:
            for m in re.finditer(pat, content):
                name = m.group(1)
                if name not in ["一个","所有","什么","怎么","这个","那个","很多","不少"]:
                    detected_names.add(name)

        # 更新出场角色
        for name in list(detected_names)[:10]:  # 取前10个
            cs = self.get_or_create(name)
            if cs.first_appearance == 0 or chapter_num < cs.first_appearance:
                cs.first_appearance = chapter_num
            cs.last_appearance = chapter_num
            cs.total_appearances += 1

            # 检测修炼突破
            for pat in ["突破.*期","晋升.*境","达到.*阶","踏入.*级","渡过.*劫"]:
                if re.search(pat, content) and cs.name in content[max(0, content.index(name)-50):content.index(name)+50]:
                    cs.cultivation_level = "新突破"  # 后续可用LLM精确提取

            # 检测位置变化
            loc_pat = r'([一-鿿]{2,4}(?:城|宗|国|府|阁|山|海|谷|林|楼|殿|宫|峰))'
            locs = re.findall(loc_pat, content)
            if locs and name in content[:200]:
                cs.location = locs[0]

            # 检测情感状态
            from core.emotion_analyzer import EmotionAnalyzer
            name_context = content[max(0, content.index(name)-100):content.index(name)+200] if name in content else content[:300]
            emotion = EmotionAnalyzer.detect(name_context, chapter_num)
            if emotion:
                cs.emotional_state = emotion

            cs.last_updated = time.time()

        self.save()

    def get_injection_context(self, chapter_num: int) -> str:
        """
        生成角色状态上下文（注入写作 prompt）
        只注入近期活跃角色，避免过载
        """
        active = [c for c in self.characters.values()
                  if c.last_appearance >= chapter_num - 5 and c.last_appearance > 0]
        if not active:
            return ""

        parts = ["\n\n【角色状态（最近5章活跃）】"]
        for c in sorted(active, key=lambda x: x.last_appearance, reverse=True)[:8]:
            info = [f"{c.name}"]
            if c.cultivation_level: info.append(f"境界:{c.cultivation_level}")
            if c.location: info.append(f"位置:{c.location}")
            if c.emotional_state: info.append(f"情感:{c.emotional_state}")
            if c.current_goal: info.append(f"目标:{c.current_goal}")
            parts.append(" | ".join(info))

            # 关系
            if c.relationships:
                rels = [f"{k}({v})" for k, v in list(c.relationships.items())[:3]]
                parts.append(f"  关系: {', '.join(rels)}")

        return "\n".join(parts)

    def get_summary(self) -> dict:
        """获取角色系统状态摘要"""
        return {
            "total": len(self.characters),
            "active": sum(1 for c in self.characters.values() if c.total_appearances > 0),
            "protagonists": sum(1 for c in self.characters.values() if c.role == "protagonist"),
            "antagonists": sum(1 for c in self.characters.values() if c.role == "antagonist"),
        }
