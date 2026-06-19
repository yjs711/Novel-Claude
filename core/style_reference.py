"""
Novel-Claude Fusion — Style Reference Engine (文风参照)

Injects real prose excerpts from high-subscription web novels as style anchors.
Research (POLARIS 2026): Human-Reference Anchoring = most effective technique
for improving AI fiction quality. 9B model matches 27B in blind tests.

All excerpts from novels with 30,000+ average subscriptions (均订三万+).
Used as style targets, NEVER copied verbatim in output.

Sources: 凡人修仙传, 诡秘之主, 雪中悍刀行, 无限恐怖, 仙逆
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class StyleReference:
    """A prose style reference from a high-subscription web novel."""
    name: str               # style name
    source: str             # source novel
    author: str             # author
    genre: str              # primary genre
    prose_traits: List[str] # key style characteristics
    excerpt: str            # the actual prose excerpt (200-500 chars)
    technique_notes: str    # what to learn from this style


# ── Style database ───────────────────────────────────────────────────────────

STYLE_DB: Dict[str, StyleReference] = {}


def _register(s: StyleReference) -> StyleReference:
    STYLE_DB[s.name] = s
    return s


# ── Core style references ────────────────────────────────────────────────────

_register(StyleReference(
    name="凡人质朴白描",
    source="凡人修仙传",
    author="忘语",
    genre="修仙",
    prose_traits=["质朴白描", "细节堆叠真实感", "慢节奏呼吸", "底层视角", "去戏剧化叙述"],
    excerpt="""二愣子睁大着双眼，直直望着茅草和烂泥糊成的黑屋顶，身上盖着的旧棉被，已呈深黄色，看不出原来的本来面目，还若有若无的散发着淡淡的霉味。

在他身边紧挨着的另一人，是二哥韩铸，酣睡的十分香甜，从他身上不时传来轻重不一的阵阵打呼声。

离床大约半丈远的地方，是一堵黄泥糊成的土墙，因为时间过久，墙壁上裂开了几丝不起眼的细长口子，从这些裂纹中，隐隐约约的传来韩母唠唠叨叨的埋怨声，偶尔还掺杂着韩父，抽旱烟杆的"啪嗒""啪嗒"吸吮声。""",
    technique_notes="不抒情不评价，用物件细节(霉味棉被/裂纹土墙/烟杆啪嗒)让读者自己感受到贫穷。节奏极慢但每一句都在建立真实感。动词少形容词更少。",
))

_register(StyleReference(
    name="诡秘克制描写",
    source="诡秘之主",
    author="爱潜水的乌贼",
    genre="悬疑/克苏鲁",
    prose_traits=["克制冷峻", "氛围先行", "翻译腔适度", "细节暗示恐惧", "理性叙述者"],
    excerpt="""邓恩转头望了眼马车外面，路灯的昏黄交织成了文明的光辉。

这里没有高窗，幽深的黑暗成为了主角，但在拱形圣台后面，大门正对而入的墙壁之上，十几二十个拳头大小的圆孔贯通往外，让灿烂的、纯粹的太阳辉芒照入进来，凝缩而光明。这就像黑夜里的行人，陡然抬头，看见了星空，看见了一枚枚璀璨，那是如此的崇高，如此的纯净，如此的神圣。""",
    technique_notes="用光暗对比建立氛围。'幽深的黑暗成为了主角'——不说恐怖但比说恐怖更恐怖。'路灯的昏黄交织成了文明的光辉'——一个意象胜过千言万语。结尾排比递进释放情绪但不煽情。",
))

_register(StyleReference(
    name="雪中豪放飘逸",
    source="雪中悍刀行",
    author="烽火戏诸侯",
    genre="武侠",
    prose_traits=["文白掺杂", "豪放飘逸", "意象密集", "节奏顿挫", "人物语言个性鲜明"],
    excerpt="""她被一剑洞穿心胸时，曾惨白笑言："天不生你李淳罡，很无趣呢。"

李淳罡大声道："剑来！"

徽山所有剑士的数百佩剑一齐出鞘，向大雪坪飞来。龙虎山道士各式千柄桃木剑一概出鞘，浩浩荡荡飞向牯牛大岗。两拨飞剑。遮天蔽日。

这一日，剑神李淳罡再入陆地剑仙境界。""",
    technique_notes="'剑来'二字封神——极简命令句的爆发力。短句+意象轰炸+节奏加速。'两拨飞剑。遮天蔽日。'——句号断开制造画面定格。情绪由惨白→悲壮→爆发→升华，四步情绪弧。",
))

_register(StyleReference(
    name="无限写实独白",
    source="无限恐怖",
    author="zhttty",
    genre="都市/无限流",
    prose_traits=["现代写实", "内心独白", "存在主义底色", "长句蓄力", "节奏由慢到快的加速感"],
    excerpt="""郑吒一直觉得自己死在现实中，上班下班，吃饭排泄，睡觉醒来，他不知道自己的意义何在，绝不会在于主任那张肥油直冒的笑脸里，绝对不会在于酒吧结识的所谓白领女子体内，也绝对不会在于这个一望无边的钢铁丛林——现代化都市中。

郑吒觉得自己快腐烂了，从二十四岁一直腐烂到老，然后化为泥土变成一个名字，不，连一个名字都不会存在，因为没有人会记得你。

他想改变些什么，他想有自己的意义……

"想明白生命的意义吗？想真正的……活着吗？" """,
    technique_notes="第一段长句像被困住——句式模拟了主角的生存状态。重复'绝对不会在于'建立压抑节奏。'腐烂'一词贯穿——生理性词汇比'空虚''迷茫'有力100倍。最后两行突然变短——节奏释放。",
))

_register(StyleReference(
    name="仙逆悲壮抒情",
    source="仙逆",
    author="耳根",
    genre="修仙",
    prose_traits=["悲壮抒情", "排比递进", "生死哲思", "极端情绪渲染", "短句收束"],
    excerpt="""这雨，出生于天，死于大地，中间的过程，便是人生。我之所以看这雨水，不看天，不看地，看的也不是雨……而是这雨的一生——这便是生与死！

我颠覆了整个天地，只为了摆正你的倒影。我逆转了整个苍穹，只为了那天，遮不住你要睁开的双眼。我轰开了无穷虚无，只为了打开一条路……让你找到回家的方向。""",
    technique_notes="意象延伸——从'看雨'推演到'生死'再推演到'道'。排比递进——'颠覆天地→逆转苍穹→轰开虚无'逐级加码。每段结尾用句号或破折号收束——力量集中到最后一个词。",
))

# ── Genre → Style mapping ────────────────────────────────────────────────────

GENRE_STYLE_MAP: Dict[str, List[str]] = {
    "修仙": ["凡人质朴白描", "仙逆悲壮抒情"],
    "玄幻": ["仙逆悲壮抒情", "雪中豪放飘逸"],
    "都市": ["无限写实独白"],
    "悬疑": ["诡秘克制描写"],
    "武侠": ["雪中豪放飘逸"],
    "凡人流": ["凡人质朴白描"],
    "无限流": ["无限写实独白"],
    "规则怪谈": ["诡秘克制描写"],
    "重生复仇": ["无限写实独白"],
    "历史架空": ["凡人质朴白描"],
    "霸总甜宠": ["无限写实独白"],
    "脑洞文": ["诡秘克制描写"],
}


# ── API ──────────────────────────────────────────────────────────────────────

def get_style_reference(style_name: str) -> Optional[StyleReference]:
    """Get a style reference by name."""
    return STYLE_DB.get(style_name)


def get_styles_for_genre(genre: str) -> List[StyleReference]:
    """Get recommended style references for a genre."""
    style_names = GENRE_STYLE_MAP.get(genre, [])
    if not style_names:
        # Fuzzy match
        for g, names in GENRE_STYLE_MAP.items():
            if g in genre or genre in g:
                style_names = names
                break
    return [STYLE_DB[n] for n in style_names if n in STYLE_DB]


def list_styles() -> List[str]:
    """List all available style names."""
    return list(STYLE_DB.keys())


def build_style_prompt(genre: str, max_styles: int = 1) -> str:
    """
    Build a style reference injection for the chapter prompt.
    Injects REAL prose excerpts as style targets.

    Uses Human-Reference Anchoring (POLARIS 2026): the model sees
    high-quality human prose as a target to match, not just rules to follow.
    """
    styles = get_styles_for_genre(genre)
    if not styles:
        return ""

    # Use the first matching style (most relevant to genre)
    style = styles[0]
    parts = [
        "\n[Style Reference — Write like this. Not rules. Feeling.]",
        f"Source: {style.source} by {style.author} (30,000+ avg subscriptions)",
        f"Style: {', '.join(style.prose_traits[:3])}",
        "",
        style.excerpt,
        "",
        f"[Technique: {style.technique_notes[:300]}]",
        "",
    ]
    return "\n".join(parts)


def build_style_prompt_multi(genre: str, max_styles: int = 2) -> str:
    """Build a multi-style reference prompt for voice discovery."""
    styles = get_styles_for_genre(genre)[:max_styles]
    if not styles:
        return ""

    parts = ["\n[Style References — Voice Discovery]", ""]
    for i, s in enumerate(styles, 1):
        parts.append(f"--- Style {i}: {s.name} ({s.source}, {s.author}) ---")
        parts.append(f"Traits: {', '.join(s.prose_traits[:3])}")
        parts.append(s.excerpt)
        parts.append("")

    parts.append("Choose the style that best fits this chapter. Adapt, don't copy.")
    return "\n".join(parts)
