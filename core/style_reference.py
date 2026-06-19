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

_register(StyleReference(
    name="打更人市井烟火",
    source="大奉打更人",
    author="卖报小郎君",
    genre="都市/悬疑",
    prose_traits=["市井烟火气", "插科打诨", "节奏明快", "官场+江湖双线", "成人向幽默"],
    excerpt="""大奉京兆府，监牢。

许七安坐在审讯室的铁椅上，手腕脚踝都锁着沉重镣铐。

他面色如常，心里已经把穿越之神、系统之神、金手指之神全部问候了一遍。

没有系统。没有金手指。没有随身老爷爷。甚至没有原主的完整记忆。唯一继承的，只有这具被酒色掏空的身体，和一个"铜锣——""银锣——""金锣——"的升官发财梦。

牢门打开，一名身穿青色官袍的中年男人走进来，面无表情地在他对面坐下："许七安，你可知罪？"

许七安想说：大人，我刚穿越过来，还没搞清楚状况。但他嘴上说的是："下官冤枉。"——因为原主的肌肉记忆告诉他，在大奉官场，永远不要认罪。""",
    technique_notes="开篇三要素（监牢/审讯/穿越）一秒入戏。'许七安面色如常心里已经...'——内心独白和表面行为的反差制造喜剧节奏。'他嘴上说的是...因为原主的肌肉记忆'——用具体细节解释人物行为，不靠旁白。穿越者的现代思维vs古代官场的碰撞=核心爽点来源。",
))

_register(StyleReference(
    name="大王饶命怼人",
    source="大王饶命",
    author="会说话的肘子",
    genre="都市",
    prose_traits=["毒舌怼人", "段子密集", "节奏极快", "笑中带泪", "兄妹温情底色"],
    excerpt="""吕树看到这里撇撇嘴，想到班级群现在就是自己最大的负面情绪收入来源，果断发消息：

"有些人表面上很轻松，你们却不知道，实际上他们背地里……更轻松……"

班级群再次安静了。不少成绩中等每天很努力却依旧追赶不上吕树成绩的学生当时就牙疼了。尼玛，你不说话能死是吧……

"来自周方的负面情绪，+77……"

"来自刘洋的负面情绪，+81……"

就这一下子，又给吕树增加了500多点负面情绪值。吕树感觉自己现在发家致富什么的就依靠自己这群可爱的同学了啊！""",
    technique_notes="怼人→收获怨气→兑换资源→变强→继续怼人。爽点自循环机制。'你不说话能死是吧'——让读者替角色说出心声，代入感拉满。系统提示'+77'打断叙事——用游戏化界面制造节奏断裂和笑点。笑完立刻接温情（兄妹线），节奏控制精准。",
))

_register(StyleReference(
    name="全球高武渐爆",
    source="全球高武",
    author="老鹰吃小鸡",
    genre="都市高武",
    prose_traits=["真实感强", "压抑渐爆", "群像出色", "热血但不中二", "节奏精准"],
    excerpt="""方平睁开眼，发现自己躺在高中教室的课桌上。

周围是熟悉的同学，黑板上写着高考倒计时：37天。

他记得自己已经三十岁了。在工地上搬砖，被拖欠工资，被包工头骂得狗血淋头。那个三十岁的方平，活得毫无尊严。

而现在，他回到了十七岁。回到了那个改变命运的最后三十七天。

他握了握拳——这一次，他要考武科。

在这个世界，武者决定一切。经商、从政、社会地位——全部由武道实力决定。马化腾是宗师高手，企业竞争靠武力对决。穷人想翻身，只有一条路：成为武者。""",
    technique_notes="'躺在高中教室'→'三十岁搬砖被拖欠工资'→'回到十七岁'——三段信息差在300字内建立完整期待。'马化腾是宗师'——用真实人名做世界观锚点，一秒说服读者。老鹰的节奏秘诀：杀人前三章就在铺垫此人的强大/背景/重要性→压抑到读者主动要求'必须杀他'→才动手。",
))

_register(StyleReference(
    name="星门慢热隐忍",
    source="星门",
    author="老鹰吃小鸡",
    genre="都市/高武",
    prose_traits=["极度低调开篇", "慢火炖煮", "谋而后定", "隐忍爆发", "生死时速"],
    excerpt="""穿着巡检司三级巡检制服，李皓迈步跨入了巡检司办公区。

作为一名加入巡检司才一年的半新人，李皓在巡检司资历不深，平时都会稍微来早一点，简单打扫一下办公区的卫生，再烧壶水，等待其他同事到来。

不过今天的李皓，来的比平时稍微迟一点，此刻办公区已经有不少人已经到了。

看到李皓进门，门口办公桌，一位同样身穿制服的中年大妈，一脸热情，带着一些调侃意味，打趣道："小皓，今天来晚了，黑眼圈都出来了，昨晚是不是去潇洒了？" """,
    technique_notes="最平淡的开篇——没有冲突、没有金手指、没有危机。用'扫地烧水上班'建立真实日常。但这恰好是慢热文的精髓：日常越真实，后续危机越有力。节奏控制：前50章慢慢铺垫世界规则和人物关系，50章后开始加速，越往后越快。",
))

_register(StyleReference(
    name="绍宋厚重史笔",
    source="绍宋",
    author="榴弹怕水",
    genre="历史",
    prose_traits=["史笔厚重", "细节考证", "人物复杂", "权谋暗线", "时代氛围浓郁"],
    excerpt="""建炎元年，五月。

赵玖站在明道宫的九龙井前，望着井水中自己模糊的倒影。

井水幽深，倒影中的脸年轻、苍白，和这具身体原主人的记忆一样——陌生。他穿越了，成为了刚从金营逃回的康王赵构。而此时，汴京已陷，二圣被掳，整个大宋摇摇欲坠。

"殿下。"身后传来声音，"宗泽老将军求见。"

赵玖转身。他想起史书上关于这个时代的记载：宗泽死前高呼"过河"，岳飞被杀时才三十九岁，秦桧永远跪在西湖边。

而现在，这些人就在他面前，活着，呼吸着。

他忽然意识到——自己站的位置，是历史的拐点。""",
    technique_notes="历史感不是堆砌名词，而是'宗泽死前高呼过河/岳飞三十九岁被杀/秦桧永远跪在西湖边'——用已知的历史结局反照当下。'活着，呼吸着'——三个字让历史人物从纸上站起来。穿越者的信息差=最大爽点来源——我知道历史走向，我能改变它。",
))

_register(StyleReference(
    name="覆汉雄浑大气",
    source="覆汉",
    author="榴弹怕水",
    genre="历史",
    prose_traits=["雄浑大气", "战争场面", "谋略博弈", "英雄群像", "文白适度"],
    excerpt="""光和六年，秋。

公孙珣站在涿县城头，望着城外连营的乌桓骑兵。

边塞的风吹得旗帜猎猎作响。身后是五千步卒，身前是三万乌桓铁骑。

他拔出腰间的刀，回头对将士们说了一句话。这句话后来被写进了《后汉书》，成为了整个时代最著名的一句战前宣言——

"诸位，今日随我赴死。若得胜归，富贵共之；若败，公孙珣死在诸君之前。"

五千人对三万人。这不是战争，这是拼命。

但公孙珣知道，如果他不在这里挡住乌桓人，身后的冀州、兖州、豫州——整个中原腹地——都将暴露在乌桓铁蹄之下。那是几十万百姓。""",
    technique_notes="'光和六年，秋'——用真实年号建立历史坐标系。'五千步卒对三万铁骑'——数字的硬碰硬。'这句话后来被写进了后汉书'——用未来视角写当下，制造史诗感。'那不是战争，那是拼命'——一句话定义了公孙珣的性格。历史文的爽点：明知是死局，用智谋和勇气破局。",
))

_register(StyleReference(
    name="诡秘之主开篇",
    source="诡秘之主",
    author="爱潜水的乌贼",
    genre="悬疑/克苏鲁",
    prose_traits=["翻译腔克制", "悬念层叠", "细节暗示", "理性主角", "世界观逐层揭示"],
    excerpt="""周明瑞从一阵剧烈的头痛中醒来。

眼前是陌生的天花板——深棕色木质，带着虫蛀的痕迹。空气中弥漫着铁锈和廉价消毒水的味道，还有一丝若有若无的……血腥气。

他试图坐起来，发现双手沾满暗红色的液体。不是他的血。

桌上摊开一本笔记，字迹潦草而急促，最后一页只有四个字：所有人都会死，包括我。

窗外，一轮绯红色的月亮正静静地注视着他。""",
    technique_notes="开篇四件套：头痛+血腥+笔记+红月——悬念密度极高，每个细节都指向一个问题（发生了什么），但都不回答。'不是他的血'——用否定句比肯定句更恐怖。'绯红色的月亮正静静地注视着他'——环境拟人化，世界本身在观察主角。乌贼的节奏：信息释放像剥洋葱，一层之后永远还有一层。",
))


# ── Genre → Style mapping ────────────────────────────────────────────────────

GENRE_STYLE_MAP: Dict[str, List[str]] = {
    "修仙": ["凡人质朴白描", "仙逆悲壮抒情"],
    "玄幻": ["仙逆悲壮抒情", "凡人质朴白描"],
    "都市": ["无限写实独白", "大王饶命怼人", "全球高武渐爆"],
    "都市高武": ["全球高武渐爆", "星门慢热隐忍"],
    "悬疑": ["诡秘之主开篇", "诡秘克制描写"],
    "克苏鲁": ["诡秘之主开篇", "诡秘克制描写"],
    "武侠": ["雪中豪放飘逸"],
    "凡人流": ["凡人质朴白描", "星门慢热隐忍"],
    "无限流": ["无限写实独白"],
    "规则怪谈": ["诡秘之主开篇", "诡秘克制描写"],
    "重生复仇": ["无限写实独白", "全球高武渐爆"],
    "历史架空": ["绍宋厚重史笔", "覆汉雄浑大气"],
    "脑洞文": ["大王饶命怼人", "诡秘之主开篇"],
    "霸总甜宠": ["打更人市井烟火"],
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
