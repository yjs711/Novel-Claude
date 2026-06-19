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


# ── Extended genres ──────────────────────────────────────────────────────────

_register(GenreKnowledge(
    name="重生复仇",
    aliases=["重生", "复仇", "revenge", "rebirth"],
    core_appeal="前世惨死→重生利用信息差逐一复仇→反转打脸的极致爽感",
    target_reader="18-35岁男女，追求智商碾压和正义伸张",
    word_count_range="80万-200万字",
    structure_nodes=[
        {"position": "1.前世惨死", "ratio": "5%", "content": "展示前世被背叛/陷害的真相", "emotion": "震惊/愤怒"},
        {"position": "2.重生认知", "ratio": "5%", "content": "梳理记忆确定复仇目标，前世今生对比", "emotion": "期待"},
        {"position": "3.信息差碾压", "ratio": "15%", "content": "利用前世记忆抢占先机，第一次打脸", "emotion": "爽"},
        {"position": "4.逐层复仇", "ratio": "25%", "content": "从小反派开始逐一瓦解，揭开更大阴谋", "emotion": "爽→悬念交替"},
        {"position": "5.多重阻碍", "ratio": "15%", "content": "中期反扑+信任危机+前世未知的变数出现", "emotion": "紧张"},
        {"position": "6.终极对决", "ratio": "15%", "content": "与最大仇敌决战，前世今生因果了结", "emotion": "爽(最高潮)"},
        {"position": "7.报应清算", "ratio": "10%", "content": "所有仇人逐一得到报应", "emotion": "爽(宣泄)"},
        {"position": "8.新生活", "ratio": "10%", "content": "选择原谅或放下，开启新人生", "emotion": "治愈/释然"},
    ],
    protagonist_template="前世天真善良→重生后腹黑果决；金手指=前世记忆；核心矛盾=复仇过程中是否变成和仇人一样的人",
    antagonist_layers="小反派(3-10章) → 中反派(20-50章) → 大反派(全书)，层级嵌套",
    golden_finger_patterns=["前世完整记忆", "关键事件预知", "人际关系的重新利用", "隐藏资源的前知"],
    pleasure_point_types=["信息差碾压", "打脸前世仇人", "挽救前世遗憾", "被误解后真相大白", "布局收网"],
    hook_templates=["前世未知的真相碎片浮现", "仇人提前发现主角异常", "前世盟友今生成敌", "蝴蝶效应改变关键事件"],
    opening_templates=["临死回忆: 死前闪回→重生到关键节点→第一个不同选择", "直接重生: 睁眼回到XX年前→立刻改变第一个命运转折点"],
    common_mistakes=["复仇太顺利失去张力", "前世记忆倾倒过多", "反派智商过低"],
))

_register(GenreKnowledge(
    name="霸总甜宠",
    aliases=["霸总", "甜宠", "总裁文", "romance"],
    core_appeal="霸道总裁专一宠溺+身份差距的戏剧张力+高甜密度带来的沉浸感",
    target_reader="18-35岁女性，追求被珍视的浪漫幻想",
    word_count_range="50万-150万字",
    structure_nodes=[
        {"position": "1.特殊相遇", "ratio": "15%", "content": "男女主意外相遇，男主被女主某特质吸引", "emotion": "新鲜/好奇"},
        {"position": "2.强势追求", "ratio": "25%", "content": "男主用身份/财富为女主解决困境，制造便利", "emotion": "甜/爽"},
        {"position": "3.感情确认", "ratio": "15%", "content": "女主心动两人走到一起", "emotion": "满足"},
        {"position": "4.外力阻挠", "ratio": "25%", "content": "家族反对/前女友破坏/商业对手陷害", "emotion": "紧张"},
        {"position": "5.共同化解", "ratio": "20%", "content": "一起克服困难，感情升华，幸福结局", "emotion": "爽/治愈"},
    ],
    protagonist_template="女主不能花瓶，要有让男主'非她不可'的独特性——能力/性格/身份上的戏剧反差",
    golden_finger_patterns=["男主的权力/财富=最大金手指", "女主隐藏身份(真实身份是XX)", "契约婚姻→真感情"],
    pleasure_point_types=["宠溺场面(闺蜜/众人震惊)", "身份反转打脸", "英雄救美", "吃醋修罗场", "公开告白"],
    hook_templates=["女主身份即将暴露", "前女友制造误会", "商业危机威胁男主", "家族逼婚倒计时"],
    opening_templates=["契约开局: 被迫签下婚约→相处中产生真感情", "意外开局: 一夜宿醉/车祸→男主负责→感情滋生"],
    common_mistakes=["虐太多变成虐文跑偏", "女主花瓶化无闪光点", "阻力太弱没张力或太强偏离甜宠定位"],
))

_register(GenreKnowledge(
    name="脑洞文",
    aliases=["脑洞", "创意文", "设定流"],
    core_appeal="独特金手指/创意设定为核心卖点，卖点=这个点子本身而非题材",
    target_reader="18-30岁，喜欢新奇设定和反套路",
    word_count_range="50万-200万字",
    structure_nodes=[
        {"position": "1.点子展示", "ratio": "10%", "content": "用开篇事件展示核心创意的独特性和想象空间", "emotion": "新奇"},
        {"position": "2.规则建立", "ratio": "15%", "content": "金手指/设定的规则体系建立，读者理解玩法", "emotion": "理解+期待"},
        {"position": "3.第一次应用", "ratio": "15%", "content": "用金手指解决第一个问题，展示威力和趣味", "emotion": "爽/有趣"},
        {"position": "4.循环升级", "ratio": "25%", "content": "核心梗循环+场景/对象/规模逐步升级", "emotion": "持续新鲜"},
        {"position": "5.规则突破", "ratio": "15%", "content": "发现金手指的隐藏用法/更强模式", "emotion": "惊喜"},
        {"position": "6.终极应用", "ratio": "20%", "content": "用创意解决最大冲突，展示完整形态", "emotion": "满足"},
    ],
    protagonist_template="根据脑洞类型不同而变化，但必须有一项特质与金手指形成化学反应",
    golden_finger_patterns=["条件触发型(满足X→获得Y)", "多条件阶段型(多条件→阶段升级)", "逆向型(失去X→获得更强Y)"],
    pleasure_point_types=["创意本身的惊艳感", "金手指的巧妙应用", "反套路反转", "读者的'还能这样'感"],
    hook_templates=["金手指新功能解锁", "隐藏规则被发现", "创意应用在更宏大场景"],
    opening_templates=["点子先行: 开篇500字内展示核心创意的魅力", "反差开局: 平凡处境→创意加持→第一个惊奇"],
    common_mistakes=["全盘照抄已有作品", "创意新鲜感消退后无内容支撑", "规则体系不自洽"],
))

_register(GenreKnowledge(
    name="凡人流",
    aliases=["凡人", "苟道流"],
    core_appeal="无天赋主角靠谨慎算计在残酷世界生存→智慧碾压的独特爽感",
    target_reader="18-35岁男性，喜欢策略博弈和现实感",
    word_count_range="200万-500万字",
    structure_nodes=[
        {"position": "1.处境展示", "ratio": "10%", "content": "展示主角底层/无天赋处境+世界残酷规则", "emotion": "压抑"},
        {"position": "2.谨慎生存", "ratio": "20%", "content": "用谨慎和智谋度过早期危机，建立基本盘", "emotion": "紧张+智谋爽"},
        {"position": "3.资源积累", "ratio": "20%", "content": "算计每一次资源获取，小而稳的成长", "emotion": "慢热爽"},
        {"position": "4.势力建立", "ratio": "15%", "content": "建立自己的小势力/洞府/信息网", "emotion": "成长"},
        {"position": "5.暴露危机", "ratio": "15%", "content": "底牌被迫暴露，面对远强于自己的敌人", "emotion": "极度紧张"},
        {"position": "6.智取强敌", "ratio": "20%", "content": "以弱胜强靠的是谋划布局而非蛮力", "emotion": "智谋爽(高潮)"},
    ],
    protagonist_template="无特殊天赋/背景→靠谨慎、机智、利弊权衡生存；嘴上说谨慎行为也必须谨慎",
    golden_finger_patterns=["微弱金手指(辅助型)", "纯粹靠智谋(无金手指)", "信息优势(重生/预知但不全知)"],
    pleasure_point_types=["智谋碾压", "以弱胜强", "精准算计的满足感", "底牌揭示", "反派低估主角后遭反噬"],
    hook_templates=["更强敌人注意到主角", "底牌被迫暴露", "算计出现意外变数", "更大危机降临"],
    opening_templates=["底层开局: 展示世界残酷+主角弱小+第一个谨慎选择", "副本引入: 配角→副本信息→主角权衡后进入"],
    common_mistakes=["主角嘴上谨慎行为疯狂(言行不一)", "爽点太慢流失读者", "后期变成传统升级流偏离定位"],
))

_register(GenreKnowledge(
    name="历史架空",
    aliases=["历史", "架空历史", "科举", "种田", "historical"],
    core_appeal="穿越到历史节点→用现代知识/信息差改变命运→改写历史的掌控感",
    target_reader="18-40岁男女，对历史有兴趣但非考据派",
    word_count_range="100万-300万字",
    structure_nodes=[
        {"position": "1.穿越定位", "ratio": "10%", "content": "穿越到关键历史时刻→面临生存危机→明确目标", "emotion": "紧张+好奇"},
        {"position": "2.立足发展", "ratio": "20%", "content": "用现代知识建立初步优势(科举/技术/商业)", "emotion": "成长爽"},
        {"position": "3.势力扩张", "ratio": "25%", "content": "结交权贵/建立势力/经济积累", "emotion": "爽→压力交替"},
        {"position": "4.朝堂博弈", "ratio": "20%", "content": "卷入高层政治斗争，改革与保守碰撞", "emotion": "紧张"},
        {"position": "5.历史转折", "ratio": "15%", "content": "在重大历史事件中发挥作用，改变走向", "emotion": "史诗/满足"},
        {"position": "6.功成身退", "ratio": "10%", "content": "功成名就后选择归隐/继续改革/开创新时代", "emotion": "满足"},
    ],
    protagonist_template="穿越者带着现代知识体系；性格务实不空谈；在理想与现实之间权衡",
    golden_finger_patterns=["现代知识体系(最大金手指)", "历史走向预知(信息差)", "穿越自带系统/空间(选配)"],
    pleasure_point_types=["技术碾压古人", "诗词/科举装逼", "打脸质疑者", "改写历史遗憾", "民族自豪感"],
    hook_templates=["历史走向因主角改变出现偏差", "更高层权贵关注到主角", "改革触犯既得利益集团"],
    opening_templates=["危机开局: 穿越到被抄家/流放/战败的关键节点→用知识自救", "科举开局: 穿越成穷秀才→用现代知识考取功名"],
    common_mistakes=["过度考据影响可读性", "现代技术实现太容易不真实", "主角光环太强历史人物智商欠费"],
))

_register(GenreKnowledge(
    name="规则怪谈",
    aliases=["怪谈", "规则", "副本流"],
    core_appeal="玩家被抽入规则副本→在诡异规则下求生→找出生路的紧张刺激",
    target_reader="18-30岁，喜欢悬疑推理和生存游戏",
    word_count_range="50万-150万字",
    structure_nodes=[
        {"position": "1.副本进入", "ratio": "10%", "content": "展示副本规则和诡异氛围，主角入场", "emotion": "紧张/悬疑"},
        {"position": "2.规则探索", "ratio": "20%", "content": "主角试探规则边界，分析生路和死路", "emotion": "紧张+智谋"},
        {"position": "3.首次危机", "ratio": "15%", "content": "规则触发→有人死亡→主角找到初步规律", "emotion": "惊悚"},
        {"position": "4.深度解析", "ratio": "25%", "content": "揭开副本背景故事→解读隐藏规则→找到通关路径", "emotion": "智谋爽"},
        {"position": "5.通关/升华", "ratio": "20%", "content": "破解核心诡计→成功通关→获得奖励→揭示更大世界观", "emotion": "爽+震撼"},
        {"position": "6.现实主线", "ratio": "10%", "content": "副本间现实世界的主线推进，串联多个副本", "emotion": "串联"},
    ],
    protagonist_template="逻辑强/观察力敏锐；可能带系统/特殊能力但需要有代价；不一定是武力型",
    golden_finger_patterns=["规则洞察(快速分析规则漏洞)", "系统辅助(但系统本身也是谜团)", "前世经验(已经历过类似副本)"],
    pleasure_point_types=["主角比其他人先发现规则", "利用规则反杀/装逼", "副本背景故事的震撼揭示", "通关奖励的惊喜"],
    hook_templates=["隐藏规则被触发", "副本难度突然升级", "现实世界也出现怪谈规则", "系统/能力的来源被揭示"],
    opening_templates=["强制进入: 普通日常→突然被拉入副本→第一条规则出现", "老手归来: 已通关多个副本的主角进入新副本→展示经验优势"],
    common_mistakes=["规则设计太简单没挑战性", "主角光环太强失去紧张感", "副本之间无关联碎片化"],
))

_register(GenreKnowledge(
    name="无限流",
    aliases=["无限", "轮回", "unlimited"],
    core_appeal="在不同世界观副本间跳跃→每次面临新挑战和新能力→持续进化的快感",
    target_reader="18-30岁，喜欢游戏化结构和能力收集",
    word_count_range="100万-300万字",
    structure_nodes=[
        {"position": "1.新手副本", "ratio": "8%", "content": "进入第一个副本→学习基本规则→获得初始能力", "emotion": "紧张+新奇"},
        {"position": "2-6.副本循环", "ratio": "60%", "content": "20-30章一个副本，每个副本独立故事+能力获取，主线串联", "emotion": "循环爽"},
        {"position": "7.现实危机", "ratio": "15%", "content": "副本世界规则侵蚀现实→主角和团队核心危机", "emotion": "紧张+史诗"},
        {"position": "8.终极副本", "ratio": "17%", "content": "最高难度副本→揭示整个系统的真相→终极选择", "emotion": "震撼+满足"},
    ],
    protagonist_template="初始普通人→通过副本积累能力和经验→逐渐成长为团队核心；性格冷静善于分析副本规律",
    golden_finger_patterns=["隐藏职业/血统(副本中获得)", "智力优势(比别人更快分析副本)", "队友/团队(不同能力互补)"],
    pleasure_point_types=["新副本的世界观震撼", "获得稀有道具/能力", "队友配合的战术爽", "揭露系统背后的宏大真相"],
    hook_templates=["副本难度远超预期", "队友在副本中遭遇背叛", "系统出现异常/规则变更", "现实世界也被拉入副本化"],
    opening_templates=["死亡开局: 主角在现实中死亡→进入轮回空间→新手副本", "突然降临: 全人类突然收到轮回邀请→第一批副本开启"],
    common_mistakes=["副本类型重复(总打同一个模式)", "能力体系膨胀失控", "现实主线太弱只靠副本支撑"],
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
