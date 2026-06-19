"""
Novel-Claude Fusion — Genre Knowledge Engine

Structured genre-specific writing knowledge for ideation and generation.
Sources: oh-story-claudecode (MIT), Chinese web novel database writing theory,
commercial writing craft (千均/飞卢方法论).

Architecture:
  Each genre has: 8-node story structure, core mechanics, hook templates,
  golden finger patterns, opening templates, emotional arc.

Usage:
  from core.genre_knowledge import get_genre_knowledge, list_genres
  knowledge = get_genre_knowledge("修仙")
  context = knowledge.to_writing_context()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class GenreKnowledge:
    """Complete genre knowledge package for a single genre."""
    name: str
    aliases: List[str] = field(default_factory=list)

    # Core definition
    core_appeal: str = ""           # 核心卖点
    target_reader: str = ""         # 目标读者
    word_count_range: str = ""      # 典型字数

    # Structure: 8-node template
    structure_nodes: List[Dict[str, str]] = field(default_factory=list)

    # Character archetypes
    protagonist_template: str = ""
    antagonist_layers: str = ""     # 反派分层
    supporting_roles: str = ""      # 配角配置

    # Commercial mechanics
    golden_finger_patterns: List[str] = field(default_factory=list)
    pleasure_point_types: List[str] = field(default_factory=list)
    hook_templates: List[str] = field(default_factory=list)
    opening_templates: List[str] = field(default_factory=list)

    # Emotional arc
    emotional_curve: str = ""       # 情绪曲线类型
    urgency_rhythm: str = ""        # 爽点节奏

    # Pitfalls
    common_mistakes: List[str] = field(default_factory=list)
    reader_drop_points: List[str] = field(default_factory=list)

    def to_writing_context(self) -> str:
        """Build a genre knowledge injection for the writing prompt."""
        parts = [
            f"\n[Genre Knowledge: {self.name}]",
            f"Core appeal: {self.core_appeal}",
        ]

        if self.structure_nodes:
            parts.append("Story structure:")
            for node in self.structure_nodes[:8]:
                parts.append(f"  {node.get('position','')} ({node.get('ratio','')}): "
                           f"{node.get('content','')[:80]} [{node.get('emotion','')}]")

        if self.golden_finger_patterns:
            parts.append(f"Golden finger patterns: {', '.join(self.golden_finger_patterns[:5])}")

        if self.pleasure_point_types:
            parts.append(f"Pleasure points: {', '.join(self.pleasure_point_types[:6])}")

        if self.hook_templates:
            parts.append(f"Chapter hooks: {', '.join(self.hook_templates[:5])}")

        if self.common_mistakes:
            parts.append(f"Avoid: {', '.join(self.common_mistakes[:4])}")

        if self.antagonist_layers:
            parts.append(f"Antagonist layers: {self.antagonist_layers[:200]}")

        parts.append("")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "aliases": self.aliases,
            "core_appeal": self.core_appeal, "target_reader": self.target_reader,
            "structure_nodes": self.structure_nodes,
            "protagonist_template": self.protagonist_template,
            "golden_finger_patterns": self.golden_finger_patterns,
            "pleasure_point_types": self.pleasure_point_types,
            "hook_templates": self.hook_templates,
            "opening_templates": self.opening_templates,
            "common_mistakes": self.common_mistakes,
        }


# ── Genre database ───────────────────────────────────────────────────────────

GENRE_DB: Dict[str, GenreKnowledge] = {}


def _register(g: GenreKnowledge) -> GenreKnowledge:
    GENRE_DB[g.name] = g
    for alias in g.aliases:
        GENRE_DB[alias] = g
    return g


# ── Core genres ──────────────────────────────────────────────────────────────

_register(GenreKnowledge(
    name="修仙",
    aliases=["仙侠", "修真", "凡人流", "xianxia", "cultivation"],
    core_appeal="从凡人到巅峰的力量成长+境界突破的爽感+资源争夺的紧张",
    target_reader="18-35岁男性，追求力量幻想和成长快感",
    word_count_range="200万-500万字",
    structure_nodes=[
        {"position": "1.开篇钩子", "ratio": "5%", "content": "展示主角困境+特殊身份/金手指初现", "emotion": "好奇"},
        {"position": "2.初入修行", "ratio": "10%", "content": "获得功法/拜师/首次突破，展示力量体系规则", "emotion": "期待"},
        {"position": "3.小试牛刀", "ratio": "15%", "content": "第一次越级战斗/打脸同级，建立'此子不可留'印象", "emotion": "爽"},
        {"position": "4.资源争夺", "ratio": "20%", "content": "秘境/拍卖会/宗门大比，争夺修炼资源", "emotion": "紧张+爽交替"},
        {"position": "5.势力碰撞", "ratio": "15%", "content": "卷入宗门/家族/王朝斗争，升级冲突层级", "emotion": "紧张"},
        {"position": "6.大高潮", "ratio": "15%", "content": "当前地图最强敌人决战，主角展示跨越式成长", "emotion": "爽(最高潮)"},
        {"position": "7.换地图过渡", "ratio": "10%", "content": "进入更高级区域/上界，展示更广阔世界观", "emotion": "期待+失落(对比)"},
        {"position": "8.新起点", "ratio": "10%", "content": "在新环境中重新定位，埋下更大伏笔", "emotion": "期待"},
    ],
    protagonist_template="出身平凡但身怀特殊体质/血脉/灵魂；性格坚韧不轻易放弃；有底线但该杀就杀",
    antagonist_layers="小(10-30章): 同辈竞争者→中(50-150章): 宗门/家族对头→大(全篇): 天道/古族/魔主",
    golden_finger_patterns=[
        "重生记忆(知道未来机缘)", "逆天功法(残缺功法实为神级)",
        "特殊体质(万年难遇的XX体)", "古老灵魂/戒指中的老爷爷",
        "系统面板(任务→奖励→升级)", "混沌珠/小世界(随身空间)",
    ],
    pleasure_point_types=[
        "境界突破", "越级反杀", "打脸装逼犯", "秘境夺宝",
        "拍卖会震惊全场", "宗门大比第一", "美女倾心", "收服势力",
    ],
    hook_templates=[
        "突破关头卡住(下一章突破)", "强敌降临(主角如何应对)",
        "发现惊天秘密(上古遗迹/叛徒身份)", "被逼入绝境(主角底牌是什么)",
        "旧敌再现(恩怨升级)", "新地图入口打开",
    ],
    opening_templates=[
        "废材开局: 被测出无灵根→被家族驱逐→意外觉醒",
        "重生开局: 渡劫失败回到少年时→利用记忆抢占先机",
        "穿越开局: 地球人穿越修真界→带着现代思维碾压",
    ],
    emotional_curve="W型：压制→小爆发→更大压制→中爆发→绝境→大爆发",
    urgency_rhythm="3章一小爽(突破/打脸)，10章一中爽(夺宝/比武)，30章一大爽(换地图/灭宗)",
    common_mistakes=[
        "境界升级太快失去期待感", "换地图后失去原有角色关系",
        "力量体系崩溃(后期数值膨胀)", "反派脸谱化无层次",
    ],
    reader_drop_points=["30章没有明确主线", "100章还在一张地图", "女主花瓶化"],
))

_register(GenreKnowledge(
    name="玄幻",
    aliases=["异界", "西方奇幻", "xuanhuan", "fantasy"],
    core_appeal="宏大世界观下的力量探索+种族/势力碰撞+史诗感冒险",
    target_reader="18-35岁男性，喜欢世界观构建和力量体系创新",
    word_count_range="200万-600万字",
    structure_nodes=[
        {"position": "1.世界观初现", "ratio": "5%", "content": "展示独特世界观规则+主角特殊之处", "emotion": "新奇"},
        {"position": "2.力量觉醒", "ratio": "10%", "content": "主角发现/获得独特力量体系入门", "emotion": "期待"},
        {"position": "3.学院/势力入门", "ratio": "15%", "content": "进入学院/佣兵团/魔法塔等组织学习成长", "emotion": "成长爽"},
        {"position": "4.大陆冒险", "ratio": "20%", "content": "游历各族领地/禁地/古战场，揭开世界秘密", "emotion": "探索+战斗"},
        {"position": "5.种族/势力战", "ratio": "15%", "content": "卷入人族vs兽族/光明vs黑暗等大规模冲突", "emotion": "史诗/紧张"},
        {"position": "6.神战级高潮", "ratio": "15%", "content": "对抗神级敌人/上古存在，主角成神/封圣", "emotion": "爽(最高潮)"},
        {"position": "7.位面/诸界", "ratio": "10%", "content": "进入更高位面/神界/混沌，世界观再升级", "emotion": "震撼"},
        {"position": "8.创世/归一", "ratio": "10%", "content": "成为世界主宰/创造新世界，终极收束", "emotion": "满足"},
    ],
    protagonist_template="身世神秘(神裔/异族混血/被选召者)；有强烈探索欲；在力量与责任之间成长",
    antagonist_layers="小(种族内部竞争)→中(异族入侵/教廷阴谋)→大(远古邪神/位面意志)",
    golden_finger_patterns=[
        "多系魔法/全系亲和", "血脉觉醒(神兽/古神血统)",
        "位面交易系统", "远古传承/神格碎片", "契约神兽(龙/凤凰)",
    ],
    pleasure_point_types=[
        "力量突破/血脉觉醒", "收服神兽/神器", "建立势力/领地",
        "各族震惊/认可", "诸神黄昏级大战", "创造新规则/世界",
    ],
    hook_templates=[
        "远古遗迹现世(各方势力汇聚)", "神兽幼崽认主(匹夫无罪怀璧其罪)",
        "异族宣战(主角力挽狂澜)", "神格争夺(成神的唯一机会)",
    ],
    opening_templates=[
        "废物逆袭: 魔法测试零天赋→意外觉醒全系→学院打脸",
        "穿越者: 地球人穿越异界→用现代知识+系统崛起",
        "被驱逐者: 被家族/帝国驱逐→在禁地获得传承→归来复仇",
    ],
    emotional_curve="N型：逐步攀升→中期转折→再度攀升→最终顶峰",
    urgency_rhythm="前期密集小爽(学院/佣兵团)，中期史诗战斗(种族战争)，后期诸界争霸",
    common_mistakes=["世界观过度设定影响叙事节奏", "力量体系复杂到作者自己也记不住", "换地图后原角色消失"],
    reader_drop_points=["世界观复杂到看不懂", "100章没有明确主线", "主角成长太慢"],
))

_register(GenreKnowledge(
    name="都市",
    aliases=["都市文", "都市高武", "神医", "兵王", "urban"],
    core_appeal="现实世界的逆袭幻想+身份反差爽感+人情世故的精准拿捏",
    target_reader="18-40岁男女，追求现实代入感和身份反转快感",
    word_count_range="100万-300万字",
    structure_nodes=[
        {"position": "1.身份揭露", "ratio": "5%", "content": "主角特殊身份/能力初现，与现实处境形成反差", "emotion": "好奇"},
        {"position": "2.第一次打脸", "ratio": "10%", "content": "用能力解决第一个现实问题，震惊周围人", "emotion": "爽"},
        {"position": "3.势力建立", "ratio": "15%", "content": "收服小弟/建立公司/购入资产，现实资源积累", "emotion": "成长爽"},
        {"position": "4.上层碰撞", "ratio": "20%", "content": "触碰更高层级势力(家族/财团/地下世界)，冲突升级", "emotion": "紧张+爽交替"},
        {"position": "5.身份危机", "ratio": "15%", "content": "真实身份被质疑/威胁曝光，关键时刻反杀", "emotion": "紧张"},
        {"position": "6.终极对决", "ratio": "15%", "content": "与最大反派(敌对家族/幕后黑手)决战", "emotion": "爽(最高潮)"},
        {"position": "7.身份登顶", "ratio": "10%", "content": "地位稳固/财富自由/抱得美人归", "emotion": "满足"},
        {"position": "8.新目标", "ratio": "10%", "content": "国际舞台/更高追求，暗示续集", "emotion": "期待"},
    ],
    protagonist_template="有特殊背景/能力但在普通环境中；性格低调但触及底线时果断出手；重情义",
    antagonist_layers="小(装逼路人/情敌)→中(家族对手/商业敌人)→大(国际势力/隐秘组织)",
    golden_finger_patterns=[
        "战神归来(退役特种兵/杀手)", "神医传承(失传医术/透视眼)",
        "重生都市(带记忆创业投资)", "系统加持(神豪/抽奖系统)",
        "修仙归来(渡劫失败回到都市)", "鉴宝/赌石能力",
    ],
    pleasure_point_types=[
        "身份暴露/震惊全场", "扮猪吃虎成功", "打脸富二代/装逼犯",
        "拍卖会一掷千金", "美女倒追/修罗场", "以弱胜强(商业/武力)",
    ],
    hook_templates=[
        "真实身份即将暴露", "旧敌寻仇(牵扯更大势力)",
        "身边人被威胁/绑架", "发现惊天商业机密",
        "系统发布紧急任务", "国际势力介入",
    ],
    opening_templates=[
        "归来开局: 战场/监狱/山上下来的第一天→遇到当年故人→展示变化",
        "重生开局: 回到大学/高中时代→用记忆抢占先机→第一次惊艳全场",
        "身份隐藏: 表面外卖小哥/保安→实际是退役兵王/隐世高手→被迫展现实力",
    ],
    emotional_curve="W型：低调压抑→意外打脸→更大麻烦→实力碾压→身份危机→终极翻盘",
    urgency_rhythm="每5-10章一个小高潮(打脸/收服/财富增长)，每50章一个大高潮(身份揭露/势力对决)",
    common_mistakes=["女主过多导致关系混乱", "金钱数值膨胀失去实感", "武力体系崩坏(后期修仙化)"],
    reader_drop_points=["太憋屈不爽", "女主花瓶化", "重复套路疲劳"],
))


# ── API ──────────────────────────────────────────────────────────────────────

def get_genre_knowledge(genre_name: str) -> Optional[GenreKnowledge]:
    """Get knowledge for a genre by name or alias."""
    return GENRE_DB.get(genre_name) or GENRE_DB.get(genre_name.lower())


def list_genres() -> List[str]:
    """List all available genre names."""
    seen = set()
    result = []
    for g in GENRE_DB.values():
        if g.name not in seen:
            result.append(g.name)
            seen.add(g.name)
    return sorted(result)


def match_genre(query: str) -> Optional[GenreKnowledge]:
    """Fuzzy match a genre from user input."""
    query_lower = query.lower()
    for name, g in GENRE_DB.items():
        if query_lower in name.lower() or name.lower() in query_lower:
            return g
    return None


def get_commercial_methods() -> str:
    """Get universal commercial writing methods (all-genre)."""
    return """
[Commercial Writing Methods]

Core loop: 设定目标→遇到阻碍→获得资源/能力→突破→展示成果→新目标
Pleasure point rhythm: 3章小爽(解决小麻烦/获得小资源) → 10章中爽(打脸/突破) → 30章大爽(灭敌/换地图)

Golden finger design principles:
- Must have cost/limitation (unlimited power = no tension)
- Must drive plot (golden finger = conflict engine, not convenience device)
- Must evolve (upgradeable, discoverable new features)

Reader retention pillars: Upgrade → Resource scarcity → Goal hierarchy → Mystery unraveling
Emotional curve: Suppress → Release → Bigger suppress → Bigger release (W-pattern)
Chapter hooks: Information gap (what happens next?) + Emotional investment (must see outcome)
"""
