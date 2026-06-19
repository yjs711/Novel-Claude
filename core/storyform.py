"""
Novel-Claude Fusion — 故事结构约束 (Storyform, NCP兼容)

实现 Narrative Context Protocol v1.3.0 的 Dramatica 故事结构 schema。
NCP 由 Dramatica Co. + USC 联合开发 (MIT许可)。

模板来源:
  西方经典: Dramatica.com 官方分析 (Hamlet, Star Wars)
  中国网文: 学术论文(2024-2025) + 作者自述 + 社区拆书 + 万订作者框架
  标注[观察分析]: 基于作品结构反推, 非Dramatica官方认证

Dramatica 动态对规则: OS↔RS对角线, MC↔IC对角线。
  对角线对: Universe↔Mind, Physics↔Psychology
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any


@dataclass
class Throughline:
    """NCP 故事线"""
    domain: str = ""
    concern: str = ""
    problem: str = ""
    solution: str = ""
    description: str = ""

    def to_dict(self): return {k: v for k, v in asdict(self).items() if v}

    @classmethod
    def from_dict(cls, data: dict) -> "Throughline":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StoryDynamics:
    resolve: str = "Change"
    outcome: str = "Success"
    judgement: str = "Good"
    driver: str = "Decision"
    limit: str = "Optionlock"


@dataclass
class Storyform:
    title: str = ""
    version: str = "ncp-1.3.0"
    objective_story: Throughline = field(default_factory=Throughline)
    main_character: Throughline = field(default_factory=Throughline)
    influence_character: Throughline = field(default_factory=Throughline)
    relationship_story: Throughline = field(default_factory=Throughline)
    dynamics: StoryDynamics = field(default_factory=StoryDynamics)
    genre: str = ""
    central_inequity: str = ""
    thematic_argument: str = ""

    def to_dict(self):
        return {
            "title": self.title, "version": self.version, "genre": self.genre,
            "central_inequity": self.central_inequity, "thematic_argument": self.thematic_argument,
            "objective_story": self.objective_story.to_dict(),
            "main_character": self.main_character.to_dict(),
            "influence_character": self.influence_character.to_dict(),
            "relationship_story": self.relationship_story.to_dict(),
            "dynamics": asdict(self.dynamics),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Storyform":
        sf = cls(title=data.get("title", ""), version=data.get("version", "ncp-1.3.0"),
                 genre=data.get("genre", ""),
                 central_inequity=data.get("central_inequity", ""),
                 thematic_argument=data.get("thematic_argument", ""))
        for key in ("objective_story","main_character","influence_character","relationship_story"):
            if key in data: setattr(sf, key, Throughline.from_dict(data[key]))
        if "dynamics" in data:
            sf.dynamics = StoryDynamics(**{k:v for k,v in data["dynamics"].items()
                                           if k in StoryDynamics.__dataclass_fields__})
        return sf

    @classmethod
    def empty(cls, title="", genre=""):
        return cls(title=title, genre=genre, objective_story=Throughline(domain="Physics"),
                   main_character=Throughline(domain="Universe"), dynamics=StoryDynamics())

    def to_writing_context(self) -> str:
        parts = ["\n[Storyform — 叙事结构约束 (NCP)]\n"]
        if self.central_inequity: parts.append(f"核心矛盾: {self.central_inequity}")
        if self.thematic_argument: parts.append(f"主题论证: {self.thematic_argument}")
        d = self.dynamics
        parts.append(f"结构: {d.resolve}型主角, {d.outcome}/{d.judgement} 结局")
        for name, tl in [("客观故事(OS)",self.objective_story),("主角(MC)",self.main_character),
                         ("影响角色(IC)",self.influence_character),("关系故事(RS)",self.relationship_story)]:
            if tl.domain:
                parts.append(f"{name}: {tl.domain}")
                if tl.problem: parts.append(f"  矛盾源: {tl.problem} → 解决方向: {tl.solution}")
                if tl.description: parts.append(f"  {tl.description[:120]}")
        parts.append(f"\n写作约束:\n- 主角在压力下的选择: {d.resolve}")
        if self.influence_character.domain: parts.append(f"- 包含IC的替代视角 ({self.influence_character.domain})")
        parts.append("- 让结构承载含义——不要直接解释主题\n")
        return "\n".join(parts)

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ── 西方经典 (Dramatica官方) ────────────────────────────────────────────

TEMPLATE_HAMLET = Storyform(
    title="复仇悲剧 (哈姆雷特模式)", genre="revenge",
    central_inequity="一桩谋杀已经发生，正义要求复仇——但复仇之路会腐蚀每一个追求它的人。",
    thematic_argument="复仇不是正义——它是一种会蔓延的疾病，直到什么也不剩。",
    objective_story=Throughline(domain="Mind", concern="Memory", problem="Pursuit", solution="Avoid",
        description="宫廷被猜疑、恐惧和复仇的呼声吞噬。OS(Mind)↔RS(Universe)。"),
    main_character=Throughline(domain="Universe", concern="Future", problem="Control", solution="Uncontrolled",
        description="哈姆雷特: 被困在自己没有选择的处境中。MC(Universe)↔IC(Mind)。"),
    influence_character=Throughline(domain="Mind", concern="Subconscious", problem="Avoid", solution="Pursuit",
        description="鬼魂: 一个执着的执念，要求复仇。"),
    relationship_story=Throughline(domain="Universe", concern="Future", problem="Control", solution="Uncontrolled",
        description="哈姆雷特与鬼魂的契约——共同处境驱动的负担。RS(Universe)↔OS(Mind)。"),
    dynamics=StoryDynamics(resolve="Change", outcome="Failure", judgement="Bad", driver="Decision", limit="Timelock"),
)

TEMPLATE_STARWARS = Storyform(
    title="英雄之旅 (星球大战模式)", genre="fantasy",
    central_inequity="一个压迫性的帝国控制着银河系；一小支叛军用可以毁灭世界的力量为自由而战。",
    thematic_argument="真正的力量不来自科技或武力，而来自对超越自身的某种东西的信任。",
    objective_story=Throughline(domain="Physics", concern="Obtaining", problem="Pursuit", solution="Avoid",
        description="叛军联盟vs帝国: 获取死星图纸，摧毁终极武器。OS(Physics)↔RS(Psychology)。"),
    main_character=Throughline(domain="Universe", concern="Future", problem="Control", solution="Uncontrolled",
        description="卢克: 梦想星空的农场男孩，发现自己的命运。MC(Universe)↔IC(Mind)。"),
    influence_character=Throughline(domain="Mind", concern="Subconscious", problem="Avoid", solution="Pursuit",
        description="欧比旺: 对原力的坚定信仰。"),
    relationship_story=Throughline(domain="Psychology", concern="Becoming", problem="Reconsider", solution="Consider",
        description="欧比旺与卢克: 因共同的失去而建立纽带。RS(Psychology)↔OS(Physics)。"),
    dynamics=StoryDynamics(resolve="Change", outcome="Success", judgement="Good", driver="Action", limit="Optionlock"),
)

# ── 中国网文 (观察分析) ─────────────────────────────────────────────────

TEMPLATE_FANREN = Storyform(
    title="凡人流·利己主义逆袭 (凡人修仙传)", genre="修仙",
    central_inequity="在一个资源有限、弱肉强食的修仙世界里，没有天赋的底层少年如何突破阶层天花板。",
    thematic_argument="在丛林法则的世界里，生存高于道德，自我保全是一切的前提。",
    objective_story=Throughline(domain="Physics", concern="Obtaining", problem="Pursuit", solution="Avoid",
        description="资源获取的永恒竞赛。炼气→筑基→结丹→元婴，每级对应明确的社会地位。OS(Physics)↔RS(Psychology)。"),
    main_character=Throughline(domain="Universe", concern="Future", problem="Control", solution="Uncontrolled",
        description="韩立: 底层伪灵根少年→自我驱动的功绩主体→精致的利己主义者。MC(Universe)↔IC(Mind)。"),
    influence_character=Throughline(domain="Mind", concern="Subconscious", problem="Avoid", solution="Pursuit",
        description="修仙世界的丛林法则本身: 不进阶即陨落。这个无处不在的生存压力是真正的'影响角色'。"),
    relationship_story=Throughline(domain="Psychology", concern="Becoming", problem="Reconsider", solution="Consider",
        description="韩立与修仙体系的关系: 若即若离的散修。RS(Psychology)↔OS(Physics)。"),
    dynamics=StoryDynamics(resolve="Steadfast", outcome="Success", judgement="Good", driver="Action", limit="Optionlock"),
)

TEMPLATE_DOUPO = Storyform(
    title="废材逆袭·复仇成帝 (斗破苍穹)", genre="玄幻",
    central_inequity="天才陨落为废材，未婚妻退婚羞辱。一个少年如何在被全世界抛弃后，重新站到巅峰。",
    thematic_argument="莫欺少年穷。真正的强大不是从未跌倒，而是每一次跌倒后都能爬起来。",
    objective_story=Throughline(domain="Physics", concern="Obtaining", problem="Pursuit", solution="Avoid",
        description="游戏副本式空间转换: 乌坦城→魔兽山脉→迦南学院→中州。OS(Physics)↔RS(Psychology)。"),
    main_character=Throughline(domain="Universe", concern="Future", problem="Control", solution="Uncontrolled",
        description="萧炎: 天才→废材→退婚羞辱→药老指导→复仇→斗帝。MC(Universe)↔IC(Mind)。"),
    influence_character=Throughline(domain="Mind", concern="Subconscious", problem="Avoid", solution="Pursuit",
        description="药老(灵魂体): 智者导师角色。以对'炼药'的执念感染主角。"),
    relationship_story=Throughline(domain="Psychology", concern="Becoming", problem="Reconsider", solution="Consider",
        description="萧炎与薰儿/美杜莎/药老的情感连接。RS(Psychology)↔OS(Physics)。"),
    dynamics=StoryDynamics(resolve="Change", outcome="Success", judgement="Good", driver="Action", limit="Optionlock"),
)

TEMPLATE_GUIMI = Storyform(
    title="克苏鲁·扮演法救赎 (诡秘之主)", genre="悬疑",
    central_inequity="在一个被邪神注视的世界里，凡人如何在疯狂与力量之间找到平衡，守护文明的最后光辉。",
    thematic_argument="真正的强大不是掌握力量，而是在力量面前保持人性。扮演法不是伪装，是防止被力量异化的最后防线。",
    objective_story=Throughline(domain="Mind", concern="Subconscious", problem="Pursuit", solution="Avoid",
        description="非凡特性序列体系的争夺。22条途径×10序列=完整的'升级+疯狂'双轨。OS(Mind)↔RS(Universe)。"),
    main_character=Throughline(domain="Psychology", concern="Becoming", problem="Reconsider", solution="Consider",
        description="克莱恩: 现代人穿越→愚者身份的扮演者→塔罗会的创始人。MC(Psychology)↔IC(Physics)。"),
    influence_character=Throughline(domain="Physics", concern="Doing", problem="Avoid", solution="Pursuit",
        description="罗塞尔大帝的日记: 穿越前辈的完整堕落轨迹，用行动警示克莱恩。"),
    relationship_story=Throughline(domain="Universe", concern="Future", problem="Control", solution="Uncontrolled",
        description="塔罗会: 克莱恩与成员们因末日的共同命运而联结。RS(Universe)↔OS(Mind)。"),
    dynamics=StoryDynamics(resolve="Change", outcome="Success", judgement="Bad", driver="Decision", limit="Timelock"),
)

TEMPLATE_DAGENG = Storyform(
    title="案件驱动·信息差升级 (大奉打更人)", genre="都市",
    central_inequity="穿越成古代打更人，用现代刑侦思维在一个有妖有仙的世界里破案求生。",
    thematic_argument="权力的本质不是武力高低，而是信息差。知道的比别人多，就比别人强。",
    objective_story=Throughline(domain="Physics", concern="Doing", problem="Pursuit", solution="Avoid",
        description="案件驱动的主线: 每一个案件揭开一层更大的阴谋。OS(Physics)↔RS(Psychology)。"),
    main_character=Throughline(domain="Universe", concern="Future", problem="Control", solution="Uncontrolled",
        description="许七安: 穿越警察→铜锣→银锣→金锣。现代思维vs古代规则碰撞。MC(Universe)↔IC(Mind)。"),
    influence_character=Throughline(domain="Mind", concern="Subconscious", problem="Avoid", solution="Pursuit",
        description="大奉官场的规则与潜规则: 一个固化但可被现代思维突破的观念体系。"),
    relationship_story=Throughline(domain="Psychology", concern="Becoming", problem="Reconsider", solution="Consider",
        description="许七安与同僚/上级/线人的关系网: 因案件聚合，因利益分化。RS(Psychology)↔OS(Physics)。"),
    dynamics=StoryDynamics(resolve="Steadfast", outcome="Success", judgement="Good", driver="Action", limit="Optionlock"),
)

TEMPLATE_XUEZHONG = Storyform(
    title="珠帘式群像·情义江湖 (雪中悍刀行)", genre="武侠",
    central_inequity="一个被迫扛起北凉重担的世子，在情义与责任、刀剑与权谋之间寻找自我。",
    thematic_argument="真正的江湖不是打打杀杀，是人情世故。最锋利的刀，是用来守护的。",
    objective_story=Throughline(domain="Psychology", concern="Becoming", problem="Reconsider", solution="Consider",
        description="珠帘式叙事: 五大关键人物构成五重镜像，'情义串线'编织成网。OS(Psychology)↔RS(Physics)。"),
    main_character=Throughline(domain="Universe", concern="Future", problem="Control", solution="Uncontrolled",
        description="徐凤年: 纨绔世子→江湖游历→北凉王→陆地神仙。MC(Universe)↔IC(Mind)。"),
    influence_character=Throughline(domain="Mind", concern="Subconscious", problem="Avoid", solution="Pursuit",
        description="李淳罡: 剑道极致的精神图腾。'剑来'二字定义整个时代。"),
    relationship_story=Throughline(domain="Physics", concern="Doing", problem="Pursuit", solution="Avoid",
        description="北凉军/江湖游历: 通过'行动'展开成长。RS(Physics)↔OS(Psychology)。"),
    dynamics=StoryDynamics(resolve="Change", outcome="Success", judgement="Good", driver="Decision", limit="Optionlock"),
)

TEMPLATE_FUHAN = Storyform(
    title="英雄气·渐进式争霸 (覆汉)", genre="历史",
    central_inequity="东汉末年，一个穿越者如何在群雄逐鹿的时代，用'明知不可为而为之'的英雄气改写历史。",
    thematic_argument="时代的风气塑造英雄，而非英雄塑造时代。做对的事，而不是做容易的事。",
    objective_story=Throughline(domain="Physics", concern="Obtaining", problem="Pursuit", solution="Avoid",
        description="渐进式争霸: 县令→刺史→逐鹿中原。空间广阔，群像丰满。OS(Physics)↔RS(Psychology)。"),
    main_character=Throughline(domain="Universe", concern="Future", problem="Control", solution="Uncontrolled",
        description="公孙珣: 穿越者→县令→诸侯→争霸天下。'英雄气'贯穿始终。MC(Universe)↔IC(Mind)。"),
    influence_character=Throughline(domain="Mind", concern="Subconscious", problem="Avoid", solution="Pursuit",
        description="东汉末年的时代精神: '英雄气'——面对强敌明知不可为而为之。"),
    relationship_story=Throughline(domain="Psychology", concern="Becoming", problem="Reconsider", solution="Consider",
        description="公孙珣与曹刘等群雄: 既是敌人也是同代人，共享时代的荣光与悲剧。RS(Psychology)↔OS(Physics)。"),
    dynamics=StoryDynamics(resolve="Change", outcome="Success", judgement="Good", driver="Decision", limit="Timelock"),
)

TEMPLATE_URBAN = Storyform(
    title="都市逆袭·双重身份 (都市爽文)", genre="都市",
    central_inequity="一个拥有特殊能力的普通人，如何在现代都市的权力、财富、情感三重游戏中实现阶层跨越。",
    thematic_argument="真正的强大不是武力碾压，而是在规则之内让所有人都心服口服。",
    objective_story=Throughline(domain="Physics", concern="Obtaining", problem="Pursuit", solution="Avoid",
        description="财富→地位→情感 三重升级循环。都市文最永恒话题。OS(Physics)↔RS(Psychology)。"),
    main_character=Throughline(domain="Universe", concern="Future", problem="Control", solution="Uncontrolled",
        description="主角: 外卖员/实习医生/退役兵王→隐藏身份曝光→阶层跃迁。MC(Universe)↔IC(Mind)。"),
    influence_character=Throughline(domain="Mind", concern="Subconscious", problem="Avoid", solution="Pursuit",
        description="都市丛林法则: 金钱与权力至上的价值体系。"),
    relationship_story=Throughline(domain="Psychology", concern="Becoming", problem="Reconsider", solution="Consider",
        description="情感线: 配偶/恋人/红颜知己的认知转变。RS(Psychology)↔OS(Physics)。"),
    dynamics=StoryDynamics(resolve="Steadfast", outcome="Success", judgement="Good", driver="Action", limit="Optionlock"),
)

STORYFORM_TEMPLATES = {
    "revenge": TEMPLATE_HAMLET,
    "rise_to_power": TEMPLATE_STARWARS,
    "fanren": TEMPLATE_FANREN,
    "doupo": TEMPLATE_DOUPO,
    "guimi": TEMPLATE_GUIMI,
    "dageng": TEMPLATE_DAGENG,
    "xuezhong": TEMPLATE_XUEZHONG,
    "fuhan": TEMPLATE_FUHAN,
    "urban": TEMPLATE_URBAN,
}
