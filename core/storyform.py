"""
Novel-Claude Fusion — 故事结构约束 (Storyform, NCP兼容)

实现 Narrative Context Protocol v1.3.0 的 Dramatica 故事结构 schema。
NCP 是由 Dramatica Co. + USC 联合开发的开放标准 (MIT许可)，
用于在多智能体叙事系统中传输和保存作者意图。

模板基于已验证的 Dramatica 官方示例:
  《哈姆雷特》(复仇/悲剧) 和 《星球大战》(英雄之旅/凯旋)。

来源: Dramatica.com 官方文档, NCP v1.3.0 schema,
  Narrative First 分析 (Hamlet, Star Wars: A New Hope)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any


@dataclass
class Throughline:
    """NCP 故事线 — 从四个视角之一看核心矛盾"""
    domain: str = ""          # Universe(处境) | Physics(行动) | Psychology(心理) | Mind(观念)
    concern: str = ""         # 该线的剧情目标
    problem: str = ""         # 矛盾的根源
    solution: str = ""        # 解决方向
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}

    @classmethod
    def from_dict(cls, data: dict) -> "Throughline":
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class StoryDynamics:
    """NCP 故事动力 — 叙事论证如何收束"""
    resolve: str = "Change"     # Change(角色改变) | Steadfast(角色坚守)
    outcome: str = "Success"    # Success(成功) | Failure(失败)
    judgement: str = "Good"     # Good(好结局) | Bad(坏结局)
    driver: str = "Decision"    # Decision(决策驱动) | Action(行动驱动)
    limit: str = "Optionlock"   # Optionlock(选择用尽) | Timelock(时间耗尽)


@dataclass
class Storyform:
    """NCP兼容故事结构 — 故事在论证什么"""
    title: str = ""
    version: str = "ncp-1.3.0"
    objective_story: Throughline = field(default_factory=Throughline)
    main_character: Throughline = field(default_factory=Throughline)
    influence_character: Throughline = field(default_factory=Throughline)
    relationship_story: Throughline = field(default_factory=Throughline)
    dynamics: StoryDynamics = field(default_factory=StoryDynamics)
    genre: str = ""
    central_inequity: str = ""     # "什么矛盾驱动整个故事?"
    thematic_argument: str = ""    # "故事在论证什么?"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title, "version": self.version,
            "genre": self.genre,
            "central_inequity": self.central_inequity,
            "thematic_argument": self.thematic_argument,
            "objective_story": self.objective_story.to_dict(),
            "main_character": self.main_character.to_dict(),
            "influence_character": self.influence_character.to_dict(),
            "relationship_story": self.relationship_story.to_dict(),
            "dynamics": asdict(self.dynamics),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Storyform":
        sf = cls(
            title=data.get("title", ""),
            version=data.get("version", "ncp-1.3.0"),
            genre=data.get("genre", ""),
            central_inequity=data.get("central_inequity", ""),
            thematic_argument=data.get("thematic_argument", ""),
        )
        for key in ("objective_story","main_character","influence_character","relationship_story"):
            if key in data:
                setattr(sf, key, Throughline.from_dict(data[key]))
        if "dynamics" in data:
            sf.dynamics = StoryDynamics(**{k:v for k,v in data["dynamics"].items()
                                           if k in StoryDynamics.__dataclass_fields__})
        return sf

    @classmethod
    def empty(cls, title: str = "", genre: str = "") -> "Storyform":
        return cls(title=title, genre=genre,
                   objective_story=Throughline(domain="Physics"),
                   main_character=Throughline(domain="Universe"),
                   dynamics=StoryDynamics())

    def to_writing_context(self) -> str:
        """构建注入章节prompt的结构约束块"""
        parts = ["\n[Storyform — 叙事结构约束 (NCP)]\n"]
        if self.central_inequity:
            parts.append(f"核心矛盾: {self.central_inequity}")
        if self.thematic_argument:
            parts.append(f"主题论证: {self.thematic_argument}")
        d = self.dynamics
        parts.append(f"结构: {d.resolve}型主角, {d.outcome}/{d.judgement} 结局")
        for name, tl in [
            ("客观故事(OS)", self.objective_story),
            ("主角(MC)", self.main_character),
            ("影响角色(IC)", self.influence_character),
            ("关系故事(RS)", self.relationship_story),
        ]:
            if tl.domain:
                parts.append(f"{name}: {tl.domain}")
                if tl.problem:
                    parts.append(f"  矛盾源: {tl.problem} → 解决方向: {tl.solution}")
                if tl.description:
                    parts.append(f"  {tl.description[:120]}")
        parts.append("")
        parts.append("写作约束:")
        parts.append(f"- 主角在压力下的选择: {d.resolve}")
        if self.influence_character.domain:
            parts.append(f"- 包含IC的替代视角 ({self.influence_character.domain})")
        parts.append("- 让结构承载含义——不要直接解释主题")
        parts.append("")
        return "\n".join(parts)

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ── 已验证模板 (Dramatica 官方示例) ──────────────────────────────────────
# 来源: Dramatica.com, Narrative First 分析
# 哈姆雷特 = 复仇/悲剧。星球大战 = 英雄之旅/凯旋。
# Dramatica 动态对规则: OS-RS必须是对角线, MC-IC必须是对角线。
#   对角线对: Universe↔Mind, Physics↔Psychology

TEMPLATE_HAMLET = Storyform(
    title="复仇悲剧 (哈姆雷特模式)",
    genre="revenge",
    central_inequity="一桩谋杀已经发生，正义要求复仇——但复仇之路会腐蚀每一个追求它的人。",
    thematic_argument="复仇不是正义——它是一种会蔓延的疾病，直到什么也不剩。",
    objective_story=Throughline(
        domain="Mind", concern="Memory",
        problem="Pursuit", solution="Avoid",
        description="宫廷被猜疑、恐惧和复仇的呼声吞噬。OS(Mind)↔RS(Universe)动态对。",
    ),
    main_character=Throughline(
        domain="Universe", concern="Future",
        problem="Control", solution="Uncontrolled",
        description="哈姆雷特: 被困在自己没有选择的处境中。'在我这样的处境下是什么感觉?' MC(Universe)↔IC(Mind)。",
    ),
    influence_character=Throughline(
        domain="Mind", concern="Subconscious",
        problem="Avoid", solution="Pursuit",
        description="鬼魂: 一个执着的执念，要求复仇。以其坚定的态度挑战哈姆雷特的犹豫。",
    ),
    relationship_story=Throughline(
        domain="Universe", concern="Future",
        problem="Control", solution="Uncontrolled",
        description="哈姆雷特与鬼魂的契约——一种共同处境驱动的负担。RS(Universe)↔OS(Mind)动态对。",
    ),
    dynamics=StoryDynamics(resolve="Change", outcome="Failure", judgement="Bad",
                           driver="Decision", limit="Timelock"),
)

TEMPLATE_STARWARS = Storyform(
    title="英雄之旅 (星球大战模式)",
    genre="fantasy",
    central_inequity="一个压迫性的帝国控制着银河系；一小支叛军用可以毁灭世界的力量为自由而战。",
    thematic_argument="真正的力量不来自科技或武力，而来自对超越自身的某种东西的信任。",
    objective_story=Throughline(
        domain="Physics", concern="Obtaining",
        problem="Pursuit", solution="Avoid",
        description="叛军联盟vs帝国: 获取死星图纸，摧毁终极武器。OS(Physics)↔RS(Psychology)。",
    ),
    main_character=Throughline(
        domain="Universe", concern="Future",
        problem="Control", solution="Uncontrolled",
        description="卢克: 梦想星空的农场男孩，发现自己的命运。'在我这样的处境下是什么感觉?' MC(Universe)↔IC(Mind)。",
    ),
    influence_character=Throughline(
        domain="Mind", concern="Subconscious",
        problem="Avoid", solution="Pursuit",
        description="欧比旺: 对原力的坚定信仰。一种挑战卢克物质世界观的固定观念。",
    ),
    relationship_story=Throughline(
        domain="Psychology", concern="Becoming",
        problem="Reconsider", solution="Consider",
        description="欧比旺与卢克: 因共同的失去而建立纽带。'我们到底是谁? 我们该如何行动?' RS(Psychology)↔OS(Physics)。",
    ),
    dynamics=StoryDynamics(resolve="Change", outcome="Success", judgement="Good",
                           driver="Action", limit="Optionlock"),
)

STORYFORM_TEMPLATES = {
    "revenge": TEMPLATE_HAMLET,
    "rise_to_power": TEMPLATE_STARWARS,
}
