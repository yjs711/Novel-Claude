"""
Novel-Claude Fusion — 灵感工坊

基于2025-2026年网文行业验证的开篇公式和脑洞生成方法。
来源: 万订作者经验(白蘸糖/白特慢)、起点编辑公开言论、
  社区共识(什么值得买/知乎/CSDN)、DeepSeek提示词模板体系。

功能: 生成创意起点——黄金开篇、脑洞组合、人设+金手指配对。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import random


@dataclass
class PremiseIdea:
    """一个完整的开篇创意"""
    title_hook: str          # 一句话噱头
    conflict: str            # 核心冲突
    protagonist: str         # 主角设定
    golden_finger: str       # 金手指
    opening_scene: str       # 开篇场景
    dialogue_hook: str       # 必须包含的对话场景


# ── 四大钩子公式 ──────────────────────────────────────────────────────────

HOOK_FORMULAS = [
    {
        "name": "信息反差钩子",
        "formula": "反常状态 + 常规悖论 + 短促定格",
        "template": "主角处于{状态}，但{悖论}。{定格场景}。",
        "example": "我死了整整三年，没有腐烂，没有归土。他们为我打造了一口寸金鎏棺，锁在深山密室，却不许我入土为安。",
    },
    {
        "name": "极端状态钩子",
        "formula": "极致绝境 + 生死/尊严危机 + 无力可控 + 唯一期待",
        "template": "{绝境}。{危机}。{无力感}。但{期待}。",
        "example": "刀锋冰凉，死死贴在我的颈动脉上。漫天风雪，四下无人，我站在生死边缘，等一场根本不存在的奇迹。",
    },
    {
        "name": "高压回忆钩子",
        "formula": "当下轻场景 + 过往高压事件回溯 + 因果绑定 + 遗憾留白",
        "template": "{温馨当下}。但{回忆中的高压事件}。{因果}。",
        "example": "烛光温柔，蛋糕香甜，是我们的五周年纪念日。我轻轻将一式离婚协议推到他面前。",
    },
    {
        "name": "核心驱动力钩子",
        "formula": "绝境处境 + 唯一执念 + 不可失败的代价 + 终身宿命感",
        "template": "{绝境}。唯一执念:{执念}。代价:{代价}。输不起。",
        "example": "母亲躺在ICU，医药费日日累加。我此生别无他求，唯一的执念，就是拼尽所有，留住她的性命。输不起，也不能输。",
    },
]


# ── 章节单元公式 ──────────────────────────────────────────────────────────

CHAPTER_CYCLE = {
    "name": "五步两段法",
    "steps": [
        {"name": "抛矛盾", "length": "前300字", "content": "直接进入冲突，不写风景/设定/内心戏"},
        {"name": "拉仇恨", "length": "约800字", "content": "让矛盾升级，反派加压，读者血压上升"},
        {"name": "主角出手", "length": "约800字", "content": "主角用金手指/能力反击，对话展示成长"},
        {"name": "全场震惊", "length": "约300字", "content": "配角反应、围观群众震惊，必须有至少1句对话(如: '这怎么可能——')"},
        {"name": "留钩子", "length": "约100字", "content": "新危机预告，让读者必须点下一章"},
    ],
    "dialogue_requirement": "小对峙每3-5章一次,重要对峙每10-15章一次。第3步和第4步建议有对话。",
}


# ── 题材+身份+金手指 组合表 ──────────────────────────────────────────────

GENRE_COMBOS = {
    "修仙": {
        "identities": ["外门杂役", "被退婚的废柴", "采矿囚徒", "落第书生", "将死的老乞丐", "被灭门的遗孤"],
        "golden_fingers": ["面板外挂(肝技能必成)", "重生记忆(知道未来机缘)", "逆天功法(残缺实为神级)", "古老灵魂(戒指里的老爷爷)", "混沌珠/小世界(随身空间)", "词条错位(魔道圣子获得'侠肝义胆')"],
        "conflicts": ["宗门大比", "秘境夺宝", "退婚羞辱", "家族覆灭", "被逐出师门"],
    },
    "都市": {
        "identities": ["外卖员", "失业程序员", "退役兵王", "实习医生", "被开除的销售", "破产富二代"],
        "golden_fingers": ["百倍暴击系统", "神豪抽奖", "重生记忆(股市/比特币)", "神医传承(透视眼)", "读心术(听到商业机密)"],
        "conflicts": ["前女友嫁入豪门", "被公司裁员", "家人重病缺钱", "房子被强拆", "被富二代羞辱"],
    },
    "玄幻": {
        "identities": ["农奴之子", "铁匠学徒", "被献祭的祭品", "奴隶角斗士", "流放的叛徒之子"],
        "golden_fingers": ["血脉觉醒(神兽/古神)", "多系魔法亲和", "远古传承/神格碎片", "契约神兽(龙/凤凰)", "位面交易系统"],
        "conflicts": ["学院测试零天赋", "被家族驱逐", "兽潮入侵", "教廷追杀", "异族宣战"],
    },
    "重生": {
        "identities": ["被背叛致死的CEO", "含冤而死的妃子", "末日最后幸存者", "被骗光家产的富商"],
        "golden_fingers": ["完整前世记忆", "先知先觉(股市/灾难/机缘)", "后悔药系统(每个遗憾可重来一次)"],
        "conflicts": ["前世仇人正在崛起", "蝴蝶效应改变关键事件", "被前世的盟友当成威胁"],
    },
    "悬疑": {
        "identities": ["警局实习生", "法医", "私家侦探", "记者", "连环案唯一幸存者"],
        "golden_fingers": ["规则洞察(快速分析规则漏洞)", "系统辅助(系统本身也是谜团)", "前世经验(经历过类似副本)"],
        "conflicts": ["发现上司是凶手", "每件证据都指向自己", "失踪七天的自己出现在监控里"],
    },
}


def generate_opening_hook(genre: str = None, hook_type: int = None) -> dict:
    """生成一个黄金开篇钩子。
    hook_type: 0=信息反差, 1=极端状态, 2=高压回忆, 3=核心驱动力。None=随机。
    """
    if hook_type is None:
        hook_type = random.randint(0, 3)
    hook = HOOK_FORMULAS[hook_type]

    # 获取体裁组合
    combo = GENRE_COMBOS.get(genre) if genre else random.choice(list(GENRE_COMBOS.values()))
    identity = random.choice(combo["identities"])
    gf = random.choice(combo["golden_fingers"])
    conflict = random.choice(combo["conflicts"])

    return {
        "hook_name": hook["name"],
        "formula": hook["formula"],
        "example": hook["example"],
        "genre": genre or "随机",
        "identity": identity,
        "golden_finger": gf,
        "conflict": conflict,
    }


def generate_premise(genre: str) -> PremiseIdea:
    """为指定体裁生成一个完整开篇创意"""
    combo = GENRE_COMBOS.get(genre)
    if not combo:
        combo = random.choice(list(GENRE_COMBOS.values()))

    identity = random.choice(combo["identities"])
    gf = random.choice(combo["golden_fingers"])
    conflict = random.choice(combo["conflicts"])

    # 生成对话场景
    dialogue_scenes = {
        "修仙": f"宗门执事冷着脸宣布: '{identity}，最后一次测试不合格，明日下山。'主角站在人群最后，捏紧了袖中的{gf[:6]}。",
        "都市": f"CEO把辞退信推到桌上: '公司不需要你了。'{identity}接过信封，看到了信纸背面隐藏的{conflict}线索。",
        "玄幻": f"教廷裁判官举起法杖: '测试结果——零天赋。'全场哄笑。{identity}感觉到体内的{gf[:6]}微微发热。",
        "重生": f"'签字吧，离婚。'{identity}看着前世背叛自己的妻子，嘴角微微上扬。这一次，他已经提前买下了整栋楼。",
        "悬疑": f"法医摘下口罩: '死亡时间，七天前。'但监控显示，死者昨天还在便利店买了包烟。{identity}的后背一阵发凉。",
    }

    return PremiseIdea(
        title_hook=f"{identity}获得{gf}，{conflict}",
        conflict=conflict,
        protagonist=f"{identity}，{gf}持有者",
        golden_finger=gf,
        opening_scene=f"前300字: {conflict}发生。{identity}被迫应对。",
        dialogue_hook=dialogue_scenes.get(genre, dialogue_scenes["玄幻"]),
    )


def generate_outline_chapter(genre: str, chapter_num: int, prev_chapter_summary: str = "") -> dict:
    """按五步两段法生成一章大纲，包含对话场景要求"""
    combo = GENRE_COMBOS.get(genre, GENRE_COMBOS["修仙"])

    steps = CHAPTER_CYCLE["steps"]
    outline = {
        "chapter_num": chapter_num,
        "genre": genre,
        "structure": [],
        "dialogue_required": "第3步和第4步必须有对话。第4步至少1句围观者反应对话。",
    }

    for step in steps:
        outline["structure"].append({
            "name": step["name"],
            "length": step["length"],
            "content_hint": step["content"],
        })

    return outline


def list_genres() -> List[str]:
    """列出灵感工坊支持的所有体裁"""
    return list(GENRE_COMBOS.keys())


def list_hook_types() -> List[dict]:
    """列出四大钩子类型"""
    return [{"name": h["name"], "formula": h["formula"]} for h in HOOK_FORMULAS]
