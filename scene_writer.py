"""
Scene Writer - Chapter content generation with @DSL context injection

Following NovelForge's approach:
1. Generate chapter content from chapter_outline (not beats directly)
2. Use @DSL to inject: world_setting, organization cards, scene cards,
   character cards, previous chapter content, writing guide
3. Add continuation support with word count control
4. Progressive saving and state machine management
"""

import os
import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from utils.config import SETTINGS_DIR, VOLUMES_DIR, MANUSCRIPTS_DIR
from utils.config_loader import get_config
from utils.llm_client import ProgressiveWriter, generate_stream
from core.context_assembler import assemble_context, get_assembler
from core.event_bus import event_bus
from utils.logger import get_logger, log_step
from world_builder import load_setting_chunk

logger = get_logger(__name__)
from utils.chapter_state import get_state_manager, STATE_PENDING, STATE_GENERATING, STATE_COMPLETED, STATE_FAILED


# ============================================================================
# Core Functions
# ============================================================================

def load_chapter_outline(volume_id: int, chapter_id: int) -> Optional[dict]:
    """Load chapter outline from vol_NN_chapters/ch_XXX_outline.json"""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_chapters" / f"ch_{chapter_id:03d}_outline.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_volume_outline(volume_id: int) -> Optional[dict]:
    """Load volume outline from volumes/vol_XX_outline.json"""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_outline.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_previous_chapter(volume_id: int, chapter_id: int) -> Optional[str]:
    """Load previous chapter content for context. 256K: load more."""
    if chapter_id <= 1:
        return None
    prev_chars = get_config("writing.previous_chapter_chars", 4000)
    path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id-1:03d}_final.md"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            return content[-prev_chars:]
    return None


def load_history_chapters(volume_id: int, chapter_id: int, count: int = None) -> str:
    """Load multiple previous chapters for deeper context. 256K: default 15 chapters."""
    if count is None:
        count = get_config("writing.history_chapters_count", 15)

    if chapter_id <= count:
        count = chapter_id - 1
    if count <= 0:
        return ""

    history = []
    for i in range(1, count + 1):
        prev_id = chapter_id - i
        if prev_id < 1:
            break
        path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{prev_id:03d}_final.md"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                # Get key plot points from each chapter (first 200 and last 500 chars)
                content = f.read()
                first_part = content[:200] if len(content) > 200 else content
                last_part = content[-500:] if len(content) > 500 else content
                history.append(f"=== 第{prev_id}章梗概 ===\n{first_part}\n...（中间内容）...\n{last_part}")

    return "\n\n".join(history)


def load_next_chapter_outline(volume_id: int, chapter_id: int) -> Optional[dict]:
    """Load next chapter outline for continuity check."""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_chapters" / f"ch_{chapter_id+1:03d}_outline.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_entity_cards(entity_names: List[str]) -> Dict[str, List[dict]]:
    """Load entity cards (character, scene, organization) matching the given names."""
    result = {
        "characters": [],
        "scenes": [],
        "organizations": []
    }

    blueprint_path = Path(SETTINGS_DIR) / "core_blueprint.json"
    if not blueprint_path.exists():
        return result

    with open(blueprint_path, 'r', encoding='utf-8') as f:
        blueprint = json.load(f)

    content = blueprint.get("content", blueprint)
    entity_name_set = set(entity_names)

    # Filter characters
    for char in content.get("character_cards", []):
        if char.get("name") in entity_name_set:
            result["characters"].append(char)

    # Filter scenes
    for scene in content.get("scene_cards", []):
        if scene.get("name") in entity_name_set:
            result["scenes"].append(scene)

    # Filter organizations
    for org in content.get("organization_cards", []):
        if org.get("name") in entity_name_set:
            result["organizations"].append(org)

    return result


# ══════════════════════════════════════════════════════════════════════
# 后处理模式检测器 — 基于 Antislop 2025 论文
# 否定指令无法阻止 LLM 生成禁用模式（Semantic Gravity Wells 2025），
# 因此需要在生成后进行正则扫描+标记，供用户手动修复或触发去AI味改写。
# ══════════════════════════════════════════════════════════════════════

# 禁用模式定义 — 每个模式带严重级别和正向改写建议
BANNED_PATTERNS = [
    # L1: AI解释性句式 (高优先级 — 直接暴露AI味)
    ("AI解释", r"不是.{0,40}而是", "每句只陈述一个事实，不建立对比。改为两个独立的短句。"),
    ("AI解释", r"不仅.{0,40}更是", "同上，改为两个独立短句。"),
    ("AI解释", r"这(意味着|说明|表明|代表着|标志着)", "删掉'这X着'，让读者自己得出结论。"),
    ("AI解释", r"(换句话说|也就是说|换言之|简而言之)", "删掉，前面已经说清楚了。"),
    ("AI解释", r"似乎.{0,20}(了一般|似的|在诉说|在告诉)", "改为具体的感官描写。"),
    ("AI解释", r"(仿佛|如同|宛如).{0,30}(在诉说|在告诉|在表达|在揭示)", "改为具体的声音/动作描写。"),
    # L2: AI模板比喻
    ("模板比喻", r"像.{0,20}(石子|涟漪|浆糊|流星|利剑|松树|火苗|扁舟|针扎|电流|耳光|婴儿|心跳|蜗牛|蝼蚁)", "用具体的物理感受替代比喻。"),
    ("模板比喻", r"(如同|犹如|仿佛|宛如).{0,20}(石子|涟漪|浆糊|流星|利剑|松树|火苗|扁舟|针扎|电流|耳光|婴儿|心跳|蜗牛|蝼蚁)", "同上。"),
    ("模板比喻", r"(空气|时间|世界|空间)(仿佛|似乎|好像).{0,20}(凝固|静止|停止|冻结)", "用具体的声音/动作描写替代。"),
    # L3: AI高频词汇
    ("AI高频词", r"(不禁|顿时|忽然|陡然)", "删掉副词，直接写动作。"),
    ("AI高频词", r"一股.{0,20}(力量|气流|暖流|寒意|杀意|威压|波动)", "一股→具体的感官来源（如'丹田涌上的热流'→'丹田发热，像吞了块烧红的铁'）。"),
    ("AI高频词", r"前所未有", "删掉，用具体对比替代。"),
    ("AI高频词", r"不可名状", "用具体感官描写替代（视觉/触觉/声音）。"),
    # L4: AI动作模板
    ("AI动作", r"指节发白|攥紧衣角|咬紧下唇|眼眶泛红|心脏漏拍|脊背发凉|镀上金边", "用独特的个人习惯动作替代通用模板。"),
    ("AI动作", r"命运的齿轮|这一切(刚刚开始|才刚开始|还远未结束)", "删掉，用具体情节推进替代口号。"),
]


def _extract_protagonist_names(outline: dict = None, entity_list: list = None) -> list[str]:
    """从大纲和实体列表中提取主角名字，用于POV检测排除误报。"""
    names = []
    # 从 entity_list 中找 role_type=protagonist 的角色
    if entity_list:
        entities = load_entity_cards(entity_list)
        for char in entities.get("characters", []):
            if char.get("role_type") == "protagonist" and char.get("name"):
                names.append(char["name"])
    # 回退：从 outline 的 entity_list 推断（第一个角色通常是主角）
    if not names and outline:
        el = outline.get("entity_list", [])
        if el:
            # entity_list 的元素可能是字符串或字典
            first = el[0]
            if isinstance(first, str):
                names.append(first)
            elif isinstance(first, dict) and first.get("name"):
                names.append(first["name"])
    # 最终回退：从核心蓝图中提取
    if not names:
        blueprint = load_setting_chunk("core_blueprint")
        if blueprint:
            content = blueprint.get("content", blueprint)
            for char in content.get("character_cards", []):
                if char.get("role_type") == "protagonist" and char.get("name"):
                    names.append(char["name"])
                    break
    return names


def scan_banned_patterns(text: str, protagonist_names: list[str] = None) -> list[dict]:
    """扫描文本中的禁用模式，返回标记列表。
    protagonist_names: 主角名字列表，用于排除POV检测的误报（主角的「他知道」不应标记）
    每个标记包含: {pattern_type, severity(L1/L2/L3/L4/L5), matched_text, position, suggestion}
    """
    import re
    findings = []
    seen_spans = set()

    # ── 构建动态POV模式（排除主角）──
    pov_patterns = _build_pov_patterns(protagonist_names or [])

    # 合并静态和动态模式
    all_patterns = list(BANNED_PATTERNS) + pov_patterns

    for idx, (ptype, regex, suggestion) in enumerate(all_patterns):
        # severity: 前4个L1, 5-8 L2, 9-12 L3, 13-16 L4, 17+ L5
        group = idx // 4
        severity = f"L{min(group + 1, 5)}"
        try:
            for m in re.finditer(regex, text):
                start, end = m.start(), m.end()
                if any(start <= s_end and end >= s_start for s_start, s_end in seen_spans):
                    continue
                seen_spans.add((start, end))
                findings.append({
                    "type": ptype,
                    "severity": severity,
                    "matched": m.group()[:80],
                    "position": start,
                    "line": text[:start].count('\n') + 1,
                    "suggestion": suggestion,
                })
        except re.error:
            continue  # 跳过无效正则（如主角名为空导致的正则错误）

    findings.sort(key=lambda f: f["position"])
    return findings


def _build_pov_patterns(protagonist_names: list[str]) -> list[tuple]:
    """根据主角名构建POV/旁白检测模式。主角的「他知道/他感到」不标记（排除误报）。"""
    import re

    # 非主角角色名模式 — 从文本中检测到的中文人名
    # 如果知道主角名，构建排除主角的模式
    pov_mental_verbs = r"(心中|心想|暗自|心道|默念|思忖|暗想)"

    patterns = []

    if protagonist_names:
        # 有主角名：构建排除主角的正则
        protag_pattern = "|".join(re.escape(n) for n in protagonist_names)
        # 心理动词 + 非主角角色（检测到的人名而非主角名）
        # 思路：匹配「心想/感到+非主角名」，而非简单「知道+他」
        patterns.append((
            "POV泄露",
            r"(心想|心道|暗自|思忖|默念|心中暗).{0,30}(?!" + protag_pattern + r")[A-Z一-鿿]{2,3}",
            "POV违规: 跳入了非主角角色内心。改为外部表现。"
        ))
        # 「X感到/X觉得」where X is a named character that's not the protagonist
        patterns.append((
            "POV泄露",
            r"(?!" + protag_pattern + r")[A-Z一-鿿]{2,3}.{0,10}(感到|觉得|意识到|发现)",
            "POV违规: 非主角角色的内部感知。改为外部表现。"
        ))
    else:
        # 无主角名：用保守模式（接受部分误报）
        patterns.append((
            "POV泄露",
            r"([A-Z一-鿿]{2,3})(心想|心道|暗自|思忖).{0,30}",
            "POV警告: 可能跳入配角内心。检查该角色是否为视角角色。"
        ))

    # 旁白解说（不需要主角名）
    patterns.extend([
        ("旁白解说", r"原来.{0,30}(是|就是|不是|只是|因为|为了)", "旁白解释。改为角色通过感官发现。"),
        ("旁白解说", r"(其实|事实上|说白了|简单来说|归根结底)", "旁白评论。删掉，让情节说话。"),
        ("旁白评价", r"这是.{0,30}(道理|真理|规则|法则|命运|宿命|结局|归宿|必然|注定|代价|惩罚)", "上帝视角评价。删掉。"),
        ("信息泄露", r"(他不知道|他没注意|他没发现|他还没意识到|他不知道的是|殊不知)", "视角角色未知信息。改为后续发现线索。"),
        ("作者评价", r"(笨嘴笨舌|伶牙俐齿|聪明绝顶|愚不可及|天生.{0,10}(的|就))", "作者评价形容词。改为具体行为描写。"),
    ])

    return patterns


def format_pattern_report(findings: list[dict]) -> str:
    """格式化模式检测报告。"""
    if not findings:
        return ""

    l1 = [f for f in findings if f["severity"] == "L1"]
    l2 = [f for f in findings if f["severity"] == "L2"]
    l3 = [f for f in findings if f["severity"] == "L3"]
    l4 = [f for f in findings if f["severity"] == "L4"]

    lines = ["\n\n---\n## 🤖 AI模式检测报告\n"]
    lines.append(f"共发现 {len(findings)} 处AI写作模式 (L1解释: {len(l1)}, L2比喻: {len(l2)}, L3高频词: {len(l3)}, L4动作: {len(l4)})\n")

    for f in findings[:20]:  # 最多显示20条
        lines.append(f"- [{f['severity']}][{f['type']}] 第{f['line']}行: 「{f['matched']}」 → {f['suggestion']}")

    if len(findings) > 20:
        lines.append(f"\n... 还有 {len(findings) - 20} 处未列出")

    return "\n".join(lines)


def load_world_setting() -> dict:
    """Load world setting for context."""
    path = Path(SETTINGS_DIR) / "world_setting.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _build_fallback_overview(volume_id: int, chapter_id: int) -> str:
    """当章节细纲缺失时，从世界观文件提取结构化要点（而非叙事段落）。
    基于 NovelForge 2025 设计原则: 结构化数据→正文，叙事文本会通过 in-context learning 污染风格。"""
    parts = ["【本章大纲】"]

    # 1. 主角 + 当前状态（1行）
    blueprint = load_setting_chunk("core_blueprint")
    if blueprint:
        content = blueprint.get("content", blueprint)
        chars = content.get("character_cards", [])
        if chars:
            mc = chars[0]
            role = mc.get("role_type", "")
            desc = mc.get("description", "")[:60]
            parts.append(f"主角: {mc.get('name','?')} ({role}) — {desc}")

    # 2. 世界规则（1行关键规则）
    world_setting = load_setting_chunk("world_setting")
    if world_setting:
        content = world_setting.get("content", world_setting)
        world_view = content.get("world_view", "")[:120]
        if world_view:
            parts.append(f"世界: {world_view}")

    # 3. 当前势力（1行）
    if world_setting:
        factions = content.get("major_power_camps", [])
        if factions:
            names = [f.get("name","") for f in factions[:3]]
            parts.append(f"势力: {', '.join(names)}")

    # 4. 故事核心（1行）
    one_sentence = load_setting_chunk("one_sentence")
    if one_sentence:
        content = one_sentence.get("content", one_sentence)
        sentence = content.get("one_sentence", "")
        if sentence:
            parts.append(f"核心: {sentence}")

    # 5. 故事背景（压缩到100字以内，只取开头）
    story_outline = load_setting_chunk("story_outline")
    if story_outline:
        content = story_outline.get("content", story_outline)
        overview = content.get("overview", "")[:80]
        if overview:
            parts.append(f"背景: {overview}")

    if len(parts) == 1:
        return f"【本章大纲】\n第{chapter_id}章，请根据小说类型和风格自然展开。"
    return "\n".join(parts)


def _build_style_anchor(genre: str = "", style: str = "") -> str:
    """Few-shot 风格锚定 — 按题材注入2-3条真人原文示例。
    基于 IEEE 2025: few-shot比零样本高23.5倍 + 5C框架: 示例放user msg + redundancy原则。
    来源: DSPy训练集6条 + style_reference.py内置 + 联网验证题材匹配。
    """
    # ── 题材 → [3条示例] 映射 ──
    # 每条格式: (标签, 原文摘录, 技法提示)
    GENRE_ANCHORS: dict[str, list] = {
        "修仙": [
            ("忘语《凡人修仙传》白描",
             "二愣子睁大着双眼，直直望着茅草和烂泥糊成的黑屋顶，身上盖着的旧棉被已呈深黄色。离床半丈远是一堵黄泥糊成的土墙，墙壁上裂开了几丝不起眼的细长口子，从裂纹中隐隐约约传来韩母唠唠叨叨的埋怨声，偶尔还掺杂着韩父抽旱烟杆的啪嗒啪嗒吸吮声。",
             "白描: 视觉→听觉，零比喻，一层信息一句。"),
            ("天蚕土豆《斗破苍穹》开篇",
             "「斗之力，三段！」望着测验魔石碑上面闪亮得甚至有些刺眼的五个大字，少年面无表情，唇角有着一抹自嘲。周围传来的不屑嘲笑以及惋惜轻叹，让得少年呼吸微微急促。少年缓缓抬起头来，露出一张有些清秀的稚嫩脸庞，漆黑的眸子木然的在周围那些嘲讽的同龄人身上扫过。",
             "冲突: 用围观者反应制造羞辱感，而非内心独白。"),
        ],
        "玄幻": "修仙",
        "洪荒": "修仙",
        "家族修仙": "修仙",
        "都市": [
            ("余华《活着》白描",
             "它趴在地上，歪着脑袋吧哒吧哒掉眼泪，旁边一个赤膊男人蹲在地上霍霍地磨着牛刀。我不忍心看它被宰掉。走着走着心里总放不下这头牛。我赶紧往回走，蹲下把牛脚上的绳子解了，站起来后拍拍牛的脑袋。这牛还真聪明，知道自己不死了，一下子站起来，也不掉眼泪了。",
             "连续动作推进，零比喻。"),
        ],
        "重生": "都市",
        "总裁": "都市",
        "种田": "都市",
        "科幻": [
            ("刘慈欣《三体》",
             "在中国，任何超脱飞扬的思想都会砰然坠地的，现实的引力太沉重了。疯狂如同无形的洪水，将城市淹没其中，并渗透到每一个细微的角落和缝隙。",
             "物理概念做喻体=解释性比喻(不删)，区别于装饰性比喻。"),
        ],
        "悬疑": [
            ("乌贼《诡秘之主》",
             "黑色的夜幕上，一轮赤红色的满月高高悬挂，撒下绯红色的流纱，寂静得恍若凝固。廷根市码头区，一个脸色苍白的年轻人从睡梦中惊醒。他的脸蓦地狰狞起来又蓦地平静下来，缓缓睁开半眯的充满血丝的双眼。",
             "特定感官建立氛围(绯红满月/寂静)，动作推进而非心理描写。"),
        ],
        "克苏鲁": "悬疑",
        "灵异": "悬疑",
        "盗墓": "悬疑",
        "武侠": [
            ("古龙",
             "冷风如刀，以大地为砧板，视众生为鱼肉。万里飞雪，将穹苍作烘炉，熔万物为白银。一个人，一口箱子。一个沉默平凡的人，提着一口陈旧平凡的箱子，在满天夕阳下，默然地走入了长安古城。",
             "诗化短句，一段一句。学留白和节奏。"),
        ],
        "轻小说": [
            ("张小花《史上第一混乱》",
             "我真倒霉，真的。人家穿越称雄称王，我却只能被反穿越。昨天刘老六领回来一个高壮的、穿得跟个土鳖似的人，介绍说这是荆轲。第二个客户是个胖子，他叫秦始皇——我从来没想过秦始皇是一个胖子。",
             "口语节奏+吐槽推进。"),
        ],
        "发疯文": "轻小说",
    }

    examples = GENRE_ANCHORS.get(genre)
    if isinstance(examples, str):
        examples = GENRE_ANCHORS.get(examples)
    if not examples:
        examples = GENRE_ANCHORS.get("修仙", [])

    if not examples:
        return ""

    lines = ["\n【同题材真人原文 — 学习叙事方法，不抄袭句子】"]
    for title, text, technique in examples:
        lines.append(f"\n{title}:\n「{text}」\n→{technique}")
    lines.append("\n用以上叙事手法续写：")
    return "\n".join(lines)


def load_writing_guide(volume_id: int) -> Optional[str]:
    """Load writing guide for the volume if exists."""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_writing_guide.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("content", {}).get("content", "")
    return None


def _load_structured_outline_chapter(chapter_id: int) -> dict:
    """Load per-chapter structured outline detail (scenes, beats, hooks) from 大纲.json."""
    try:
        config = _load_config()
        novel_name = config.get("workspace", {}).get("novel_name", "")
        from pathlib import Path
        outline_path = Path(f".novel_{novel_name}" if novel_name else ".novel") / "大纲.json"
        if not outline_path.exists():
            return {}
        with open(outline_path, 'r', encoding='utf-8') as f:
            outline = json.load(f)
        for vol in outline.get("volumes", []):
            for ch in vol.get("chapters_list", []):
                if ch.get("number") == chapter_id:
                    return ch
    except Exception:
        pass
    return {}


def _load_foreshadowing_context(chapter_id: int) -> str:
    """Load foreshadowing data relevant to this chapter."""
    try:
        config = _load_config()
        novel_name = config.get("workspace", {}).get("novel_name", "")
        from pathlib import Path
        fs_path = Path(f".novel_{novel_name}" if novel_name else ".novel") / "伏笔.json"
        if not fs_path.exists():
            return ""
        with open(fs_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        items = data.get("items", [])
        parts = []
        planted_here = [i for i in items if i.get("planted_in") == chapter_id and i.get("status") != "resolved"]
        needs_resolve = [i for i in items if i.get("status") == "planted" and i.get("target_resolve", 9999) <= chapter_id]
        if planted_here:
            parts.append("本章需埋入的伏笔: " + ", ".join(i["description"] for i in planted_here))
        if needs_resolve:
            parts.append("⚠️ 本章必须回收的伏笔: " + ", ".join(f"{i['description']}(第{i['planted_in']}章埋入)" for i in needs_resolve))
        return "\n".join(parts) if parts else ""
    except Exception:
        return ""


def build_chapter_prompt(volume_id: int, chapter_id: int, chapter_title: str = None,
                         overview: str = None, entities: dict = None) -> str:
    """Build the full writing prompt for a chapter. Shared between CLI and WebUI.
    All parameters are optional — if not provided, they are loaded from disk.
    Returns a prompt string; NEVER returns None (falls back to minimal prompt)."""
    # Load from disk if not provided
    entity_list = []
    if chapter_title is None or overview is None:
        outline = load_chapter_outline(volume_id, chapter_id)
        if outline:
            chapter_title = chapter_title or outline.get("title", f"第{chapter_id}章")
            overview = overview or outline.get("overview", "")
            entity_list = outline.get("entity_list", [])
        else:
            chapter_title = chapter_title or f"第{chapter_id}章"
            # 回退：从世界观文件构建基本概览（无细纲时自动生成基础提示）
            overview = overview or _build_fallback_overview(volume_id, chapter_id)
            logger.info("No chapter outline for vol%d ch%d, using fallback overview", volume_id, chapter_id)

    if entities is None:
        entities = load_entity_cards(entity_list)

    prev_chapter = load_previous_chapter(volume_id, chapter_id)
    history_chapters = load_history_chapters(volume_id, chapter_id, count=3)
    next_outline = load_next_chapter_outline(volume_id, chapter_id)

    # ── Build prompt: one chapter = one clear goal ──
    # Principle: emotional goal > plot outline > constraints
    # Information budget: minimal. Skill injections handle the rest via hooks.
    prompt_parts = []

    # 1. Entity context (lightweight — who is in this scene)
    prompt_parts.append(f"【本章大纲】\n{overview}\n")
    if entities:
        chars = entities.get('characters', [])
        if chars:
            prompt_parts.append(f"【出场角色】{', '.join(c.get('name','?') for c in chars[:5])}\n")

    if prev_chapter:
        prompt_parts.append(f"【前章结尾（接续点）】\n{prev_chapter}\n")

    if history_chapters:
        prompt_parts.append(f"【近期剧情回顾】\n{history_chapters}\n")

    if next_outline:
        next_title = next_outline.get("title", "")
        next_overview = next_outline.get("overview", "")
        prompt_parts.append(f"【下一章预告】:\n{next_title}：{next_overview}\n")

    # Structured outline (scene-level beats — AI: detail in = detail out)
    # Unlike human authors (who may lose inspiration from over-planning),
    # AI models produce BETTER output with MORE detailed outlines.
    structured_outline = _load_structured_outline_chapter(chapter_id)
    if structured_outline:
        detail_parts = []
        if structured_outline.get("summary"):
            detail_parts.append(f"概要: {structured_outline['summary']}")
        if structured_outline.get("emotional_beat"):
            detail_parts.append(f"本章情绪目标: {structured_outline['emotional_beat']}")
        if structured_outline.get("satisfaction_beat"):
            detail_parts.append(f"本章爽点(必须写到): {structured_outline['satisfaction_beat']}")
        if structured_outline.get("ending_hook"):
            detail_parts.append(f"章末钩子: {structured_outline['ending_hook']}")
        if structured_outline.get("scenes_text") or structured_outline.get("scenes"):
            scenes = structured_outline.get("scenes_text") or "\n".join(
                f"- {s.get('name','')}: POV={s.get('pov','主角')} | 目标={s.get('goal','')} | 冲突={s.get('conflict','')} | 字数≈{s.get('word_target','?')}字"
                for s in (structured_outline.get("scenes", []) if isinstance(structured_outline.get("scenes"), list) else [])
            )
            detail_parts.append(f"场景分解 (POV锁死，禁止透视配角内心):\n{scenes}")
        if detail_parts:
            prompt_parts.append("【细纲 — 本章执行指南（AI模型：越详细输出越精准）】\n" + "\n".join(detail_parts) + "\n")
    else:
        # No structured outline — inject minimal goal from overview
        logger.info("No structured_outline for chapter %d, using overview as fallback", chapter_id)

    fs_ctx = _load_foreshadowing_context(chapter_id)
    if fs_ctx:
        prompt_parts.append(f"【伏笔提醒】{fs_ctx}\n")

    # 核心约束 — 27B实测: 详细正向规则比极简规则有效(5C框架不适用小模型)
    prompt_parts.append(
        "【写作要求】\n"
        "1. 本章聚焦一个核心事件，围绕它写2-3个场景。不要跨越多个独立事件。\n"
        "2. 每个场景用1个具体感官（气味/温度/声音/触觉）建立氛围。全文仅2-3个比喻用于超自然现象。\n"
        "3. 情绪用外部动作呈现。写「他把镐柄攥得嘎吱响」不写「他感到很愤怒」。对话中穿插角色的小动作（搓手指/敲桌面/别过脸）。\n"
        "4. 偶尔插入与主线无关的闲笔：一段环境描写、一个路人细节、一句角色闲聊。不做每段都在推进情节的高效机器。\n"
        "5. 背景信息通过角色当前感官或对话自然透露，每次1句话。一段内不倾倒超过2条背景信息。句长交替：长句铺陈后跟短句收力。短句可短到1-5字。\n"
        "6. 章末用动作/画面/对话收尾，不总结。禁止「他知道/他意识到/他明白/充满希望/即将展开」类升华句。约3000字。直接输出正文。\n"
    )

    prompt = "\n".join(prompt_parts)

    # 风格锚定注入 — 按题材选择对应真人示例，不混用
    # 基于 Bohr 2025 (Show+Tell) + Gao 2024 (正面示例) + Tang 2025 (EMNLP)
    try:
        _genre = get_config("genre", default="")
        _style = get_config("style", default="")
        prompt += _build_style_anchor(_genre, _style)
    except Exception:
        prompt += _build_style_anchor()  # 回退默认

    # Inject story engine constraints (题材×风格 — 27B可执行的实战约束)
    try:
        from core.story_engine import build_writing_context
        from utils.config_loader import get_config
        genre = get_config("genre", default="")
        style = get_config("style", default="")
        if genre or style:
            engine_ctx = build_writing_context(genre, style)
            if engine_ctx:
                prompt += engine_ctx
    except Exception:
        pass  # 引擎注入失败不影响生成

    return prompt


def generate_chapter_content(volume_id: int, chapter_id: int, state_manager=None,
                              rewrite_guidance: str = None) -> str:
    """
    Generate chapter content from chapter outline using @DSL context injection.
    Supports progressive saving via state_manager.
    If rewrite_guidance is provided, injects it as quality gate feedback.
    """
    if rewrite_guidance:
        print(f"\n[REWRITE] 第 {volume_id} 卷第 {chapter_id} 章 — 质量门控重写 (guidance: {rewrite_guidance[:80]}...)")
    else:
        print(f"\n[INFO] 正在生成第 {volume_id} 卷第 {chapter_id} 章...")

    # Load chapter outline
    outline = load_chapter_outline(volume_id, chapter_id)
    if not outline:
        print(f"[ERROR] 找不到章节大纲: vol_{volume_id:02d} ch_{chapter_id:03d}")
        return ""

    chapter_title = outline.get("title", f"第{chapter_id}章")
    overview = outline.get("overview", "")
    entity_list = outline.get("entity_list", [])

    print(f"  章节: {chapter_title}")
    print(f"  概述: {overview[:50]}...")
    print(f"  参与者: {', '.join(entity_list)}")

    # Load entities for display
    entities = load_entity_cards(entity_list)

    # Build prompt using shared function
    prompt = build_chapter_prompt(volume_id, chapter_id, chapter_title, overview, entities)

    # ── Style Reference Injection (Human-Reference Anchoring, POLARIS 2026) ──
    # Must be at TOP of prompt — style target must be seen before instructions
    try:
        from core.style_reference import build_style_prompt
        from utils.config_loader import get_config
        genre_name = get_config("genre", default="")
        if not genre_name:
            from core.genre_knowledge import match_genre
            genre_name = "修仙"
        style_prompt = build_style_prompt(genre_name)
        if style_prompt:
            prompt = style_prompt + "\n" + prompt
    except Exception as e:
        logger.debug("Style reference injection skipped: %s", e)

    # Inject rewrite guidance if provided
    if rewrite_guidance:
        prompt += f"\n\n[Quality Gate Rewrite — Previous attempt issues to fix]\n{rewrite_guidance}\n"

    # Narrative diversity injection DISABLED — archetypes are unverified working hypotheses.
    # Will re-enable after web-verifying archetype definitions against published taxonomy.
    # See: core/narrative_diversity.py [待验证] markers.

    # Inject story engine constraints (题材×风格 — 27B可执行的实战约束)
    try:
        from core.story_engine import build_writing_context
        from utils.config_loader import get_config
        genre = get_config("genre", default="")
        style = get_config("style", default="")
        if genre or style:
            engine_ctx = build_writing_context(genre, style)
            if engine_ctx:
                prompt += engine_ctx
                logger.debug("Story engine injected: %s x %s", genre, style)
    except Exception as e:
        logger.debug("Story engine injection skipped: %s", e)

    # Inject legacy storyform constraints (fallback — 手动选择的 Dramatica 模板)
    try:
        from core.storyform import Storyform
        from utils.config_loader import get_config
        novel_name = get_config("workspace.novel_name", default="")
        sf_path = Path(".novel") / f"{novel_name}" / "storyform.json" if novel_name else None
        if not sf_path or not sf_path.exists():
            sf_path = Path(".novel") / "storyform.json"
        if sf_path.exists():
            import json
            sf_data = json.loads(sf_path.read_text(encoding="utf-8"))
            sf = Storyform.from_dict(sf_data)
            sf_context = sf.to_writing_context()
            if sf_context:
                prompt += "\n" + sf_context
    except Exception as e:
        logger.debug("Storyform injection skipped: %s", e)

    # Inject genre knowledge — slim: only this chapter's relevant hooks + mistakes
    try:
        from core.genre_knowledge import get_genre_knowledge
        from utils.config_loader import get_config
        genre_name = get_config("genre", default="")
        if genre_name:
            gk = get_genre_knowledge(genre_name)
            if gk:
                hook_str = " | ".join(gk.hook_templates[:3]) if gk.hook_templates else ""
                avoid_str = " | ".join(gk.common_mistakes[:3]) if gk.common_mistakes else ""
                slim = f"\n[{gk.name}] 可用钩子: {hook_str}. 避免: {avoid_str}.\n"
                prompt += slim
    except Exception as e:
        logger.debug("Genre knowledge skipped: %s", e)

    # Mark unified injections so duplicate skills skip themselves
    # (context is shared across all skills via event_bus subscribers)
    for skill in event_bus.subscribers:
        try:
            skill.context.set_shared("unified_style_injected", True)
            skill.context.set_shared("unified_genre_injected", True)
        except Exception:
            pass

    # Emit hook for skill injection (memories, constraints, state)
    beat_data = {"chapter_id": chapter_id, "title": chapter_title, "overview": overview}
    prompt_parts = [prompt]
    prompt_parts = event_bus.emit_pipeline("on_before_scene_write", prompt_parts, beat_data)
    prompt = "\n".join(prompt_parts)

    # Progressive saving callback
    def on_progress(ch_id, accumulated, char_count):
        if state_manager and ch_id:
            state_manager.update_progress(ch_id, char_count)
            # Save to temp file
            temp_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{ch_id:03d}_temp.md"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(accumulated)

    # Generate content with progressive saving
    writer = ProgressiveWriter(on_progress=on_progress, chunk_size=get_config("writing.progress_chunk_size", 1000), task="writing")
    content = writer.write(prompt, chapter_id=chapter_id)

    return content


def review_chapter_content(volume_id: int, chapter_id: int, content: str, outline: dict) -> str:
    """
    Review chapter content for:
    1. Missing title - add from outline
    2. Word count check (using config.json settings)
    3. Content too short - flag for rewrite

    Returns tuple: (reviewed_content, needs_rewrite, issues)
    """
    issues = []

    # Get config values
    target_word_count = get_config("writing.target_word_count", 6000)
    min_word_count = get_config("writing.min_word_count", 4000)
    max_word_count = get_config("writing.max_word_count", 9000)
    auto_fix_title = get_config("review.auto_fix_title", True)
    word_count_check = get_config("review.word_count_check", True)

    # Check if title exists (first line should be # 第X章 xxx)
    title_pattern = r'^#\s*第\d+章\s+.+'
    if not re.match(title_pattern, content.strip()):
        if auto_fix_title:
            chapter_title = outline.get("title", f"第{chapter_id}章") if outline else f"第{chapter_id}章"
            content = f"# 第{chapter_id}章 {chapter_title}\n\n{content}"
            issues.append(f"[审阅] 缺少章节标题，已自动添加：第{chapter_id}章 {chapter_title}")
        else:
            issues.append(f"[审阅] 缺少章节标题")

    # Check word count (code-based)
    if word_count_check:
        word_count = count_chinese_words(content)
        if word_count < min_word_count:
            issues.append(f"[审阅] 字数不足（{word_count}字），低于{min_word_count}字下限")
            return content, True, issues
        elif word_count > max_word_count:
            issues.append(f"[审阅] 字数过多（{word_count}字），超过{max_word_count}字上限")
            return content, True, issues
        elif word_count < target_word_count * 0.9:
            issues.append(f"[审阅] 字数偏少（{word_count}字），目标{target_word_count}字")
        else:
            issues.append(f"[审阅] 字数检查通过（{word_count}字）")

    # Check for obvious logical issues
    first_lines = content.strip().split('\n')[:5]
    if len(first_lines) < 3:
        issues.append("[审阅] 正文开头内容过少")
        return content, True, issues

    return content, False, issues


def count_chinese_words(text: str) -> int:
    """
    Count words in mixed Chinese/English text.
    - Chinese characters: each character counts as one word
    - English words: split by whitespace, each word counts as one
    - Punctuation is ignored
    """
    import re

    # Remove markdown title if present
    text = re.sub(r'^#\s*第\d+章\s+.+\n?', '', text)

    # Count Chinese characters (each Chinese char is a word)
    chinese_chars = len(re.findall(r'[一-鿿　-〿＀-￯]', text))

    # Count English words (sequences of letters/digits)
    english_words = len(re.findall(r'[a-zA-Z0-9]+', text))

    # Total word count
    return chinese_chars + english_words


def deep_review_chapter(content: str, outline: dict, entity_list: List[str]) -> dict:
    """
    Deep review of chapter content vs outline.
    Returns: {needs_rewrite: bool, guidance: str, issues: List[str]}
    """
    # Check if deep review is enabled
    if not get_config("review.deep_review_enabled", True):
        return {"needs_rewrite": False, "issues": [], "guidance": "", "missing_events": [], "wrong_events": []}

    from utils.llm_client import generate_json
    from pydantic import BaseModel
    from typing import List

    class ReviewResult(BaseModel):
        needs_rewrite: bool
        issues: List[str]
        guidance: str
        missing_events: List[str]
        wrong_events: List[str]

    prompt = f"""你是网络小说编辑。请审阅以下章节内容，与大纲进行对比。

【章节大纲】：
标题：{outline.get('title', '')}
概述：{outline.get('overview', '')}

【章节正文】：
{content[:3000]}...（正文已截断）

【参与者实体】：
{', '.join(entity_list)}

请检查：
1. 大纲中的核心事件是否在正文中出现
2. 正文是否有偏离大纲设定的事件
3. 角色行为是否与设定矛盾
4. 场景描写是否符合要求

输出JSON：
{{"needs_rewrite": true/false, "issues": ["问题1", "问题2"], "guidance": "重新写作的指导建议", "missing_events": ["遗漏事件1"], "wrong_events": ["偏离事件1"]}}
"""

    try:
        result = generate_json(prompt, ReviewResult)
        if hasattr(result, 'model_dump'):
            return result.model_dump()
        return result if isinstance(result, dict) else {"needs_rewrite": False, "issues": [], "guidance": "", "missing_events": [], "wrong_events": []}
    except Exception as e:
        print(f"[WARN] 深度审阅失败: {e}")
        return {"needs_rewrite": False, "issues": [], "guidance": "", "missing_events": [], "wrong_events": []}


def post_process_chapter(volume_id: int, chapter_id: int, content: str,
                         outline: dict = None) -> tuple:
    """
    Shared post-generation pipeline: save -> emit hooks -> quality gate.
    Called by BOTH CLI (run_scene_writer) and WebUI (/api/write-stream).

    Returns: (final_path: str, gate_verdict: str, gate_guidance: str)
      gate_verdict: "PASS" | "REWRITE" | "BLOCK" | None (no gate)
    """
    # Save
    save_result = save_chapter_content(volume_id, chapter_id, content, outline)
    if isinstance(save_result, tuple):
        final_path, needs_rewrite, basic_guidance = save_result
    else:
        final_path = save_result
        needs_rewrite = False
        basic_guidance = ""

    # Emit full hook chain
    beat_data = {
        "chapter_id": chapter_id, "beats": [],
        "needs_rewrite": needs_rewrite, "guidance": basic_guidance,
    }
    event_bus.emit("on_after_scene_write", beat_data, content)
    event_bus.emit("on_post_chapter_continuity", chapter_id)
    event_bus.emit("on_chapter_render", content, chapter_id)
    event_bus.emit("on_after_chapter_complete", chapter_id, content)

    # Check quality gate result
    from core.quality_gate import get_last_result
    gate_result = get_last_result()
    gate_verdict = gate_result.verdict if gate_result else None
    gate_guidance = gate_result.rewrite_guidance if gate_result else ""

    return final_path, gate_verdict, gate_guidance


def save_chapter_content(volume_id: int, chapter_id: int, content: str, outline: dict = None):
    """Save chapter content to file, with review."""
    save_dir = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}"
    save_dir.mkdir(parents=True, exist_ok=True)

    # Load outline if not provided
    if outline is None:
        outline = load_chapter_outline(volume_id, chapter_id)

    entity_list = outline.get("entity_list", []) if outline else []

    # Basic review: check title, content length
    reviewed_content, basic_needs_rewrite, basic_issues = review_chapter_content(volume_id, chapter_id, content, outline)

    # Log basic issues
    for issue in basic_issues:
        print(f"  {issue}")

    # Deep review for content coherence (only if basic check passed)
    deep_review_result = {"needs_rewrite": False, "issues": [], "guidance": ""}
    if not basic_needs_rewrite:
        deep_review_result = deep_review_chapter(reviewed_content, outline, entity_list)
        if deep_review_result.get("needs_rewrite"):
            print(f"  [审阅] 发现严重问题：{', '.join(deep_review_result.get('issues', []))}")
            print(f"  [审阅] 指导意见：{deep_review_result.get('guidance', '')}")

    # Determine if rewrite is needed
    final_needs_rewrite = basic_needs_rewrite or deep_review_result.get("needs_rewrite", False)

    # Save content
    final_path = save_dir / f"ch_{chapter_id:03d}_final.md"

    # ── 后处理模式检测 (Antislop 2025: 否定指令无法阻止, 需生成后扫描) ──
    # 提取主角名以避免POV误报
    protagonist_names = _extract_protagonist_names(outline, entity_list)
    pattern_findings = scan_banned_patterns(reviewed_content, protagonist_names)
    pattern_report = format_pattern_report(pattern_findings)
    save_content = reviewed_content + pattern_report if pattern_report else reviewed_content

    with open(final_path, 'w', encoding='utf-8') as f:
        f.write(save_content)

    if pattern_findings:
        l1_count = len([f for f in pattern_findings if f["severity"] == "L1"])
        l2_count = len([f for f in pattern_findings if f["severity"] == "L2"])
        print(f"  [AI模式检测] 发现 {len(pattern_findings)} 处问题 (解释:{l1_count} 比喻:{l2_count} 其他:{len(pattern_findings)-l1_count-l2_count})")

    if final_needs_rewrite:
        print(f"[⚠] 第 {chapter_id} 章标记为需要检查")
        return str(final_path), True, deep_review_result.get("guidance", "")
    else:
        print(f"[✓] 第 {chapter_id} 章成稿已保存至 {final_path}")
        return str(final_path), False, ""


def run_scene_writer(volume_id: int, start_chapter: int, end_chapter: int):
    """
    Main entry point for scene writing.
    Generates chapters from start_chapter to end_chapter.
    Uses state machine for progress tracking and supports resume from interruption.
    """
    state_manager = get_state_manager(volume_id)
    completed = 0
    failed = 0

    # Register chapters that need to be generated
    for chapter_id in range(start_chapter, end_chapter + 1):
        state = state_manager.get_state(chapter_id)
        if state.state == STATE_COMPLETED:
            # Check if file actually exists
            save_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id:03d}_final.md"
            if save_path.exists() and save_path.stat().st_size > 1000:
                print(f"[Skip] 第 {chapter_id} 章已完成，跳过")
                continue
            else:
                # File doesn't exist, mark as pending
                state.state = STATE_PENDING

    for chapter_id in range(start_chapter, end_chapter + 1):
        state = state_manager.get_state(chapter_id)

        # Skip if already completed
        save_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id:03d}_final.md"
        if save_path.exists() and save_path.stat().st_size > 1000:
            print(f"[Skip] 第 {chapter_id} 章已存在，跳过")
            continue

        # Check for temp file (resume from interruption)
        temp_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id:03d}_temp.md"
        if temp_path.exists():
            print(f"[Resume] 检测到第 {chapter_id} 章的临时文件，将继续生成")
            # Delete temp file to restart fresh
            temp_path.unlink()

        print(f"\n{'='*60}")
        print(f"[INFO] 启动场景子智能体集群，目标：卷 {volume_id} 章 {chapter_id}")
        print(f"{'='*60}")

        # Mark as generating
        state_manager.mark_generating(chapter_id)

        try:
            # ── Quality Gate rewrite loop ──
            gate_round = 0
            max_gate_rounds = 3
            content = ""
            guidance = ""

            while gate_round < max_gate_rounds:
                gate_round += 1

                # Generate chapter content (with progressive saving + guidance injection)
                content = generate_chapter_content(volume_id, chapter_id, state_manager,
                                                   rewrite_guidance=guidance if guidance else None)

                if not content:
                    break

                # Save + emit hooks + run quality gate (shared pipeline)
                log_step("Chapter post-process", chapter_id=chapter_id, volume_id=volume_id,
                         words=len(content), round=gate_round)
                final_path, gate_verdict, gate_guidance = post_process_chapter(
                    volume_id, chapter_id, content)

                if gate_verdict == "PASS" or gate_verdict is None:
                    log_step("Chapter PASS", chapter_id=chapter_id, round=gate_round)
                    if gate_verdict == "PASS":
                        print(f"  [OK] Quality Gate: PASS (round {gate_round})")
                    else:
                        print(f"  [OK] Quality Gate: no gate result (round {gate_round})")
                    break
                elif gate_verdict == "REWRITE" and gate_round < max_gate_rounds:
                    guidance = gate_guidance
                    logger.warning("Quality Gate: REWRITE round %d/%d, chapter %d",
                                   gate_round, max_gate_rounds, chapter_id)
                    log_step("Chapter REWRITE", chapter_id=chapter_id, round=gate_round)
                    for sk in event_bus.subscribers:
                        if hasattr(sk, 'record_rewrite'):
                            sk.record_rewrite(chapter_id)
                            break
                elif gate_verdict == "BLOCK":
                    logger.error("Quality Gate: BLOCKED chapter %d after %d rounds",
                                 chapter_id, gate_round)
                    log_step("Chapter BLOCKED", chapter_id=chapter_id, rounds=gate_round)
                    break
                else:
                    logger.error("Quality Gate: max rounds exceeded, chapter %d", chapter_id)
                    gate_verdict = "BLOCK"
                    break

            if content:
                # Mark as completed (or blocked)
                if gate_verdict == "BLOCK":
                    state_manager.mark_failed(chapter_id, f"Quality Gate BLOCKED after {gate_round} rounds")
                    failed += 1
                else:
                    state_manager.mark_completed(chapter_id)
                    completed += 1

                # Delete temp file if exists
                if temp_path.exists():
                    temp_path.unlink()

                # Track entity states for this chapter
                from core.entity_tracker import track_chapter_entities
                track_chapter_entities(volume_id, chapter_id)
            else:
                state_manager.mark_failed(chapter_id, "content empty")
                failed += 1
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] 第 {chapter_id} 章生成失败: {error_msg}")
            state_manager.mark_failed(chapter_id, error_msg)
            failed += 1

    print(f"\n{'='*60}")
    print(f"[INFO] 本批次生成完成：成功 {completed} 章，失败 {failed} 章")
    print(f"[INFO] 可通过重新运行命令继续生成失败的章节")
    print(f"{'='*60}")


# ============================================================================

# ============================================================================
# Batch Mode (for compatibility)
# ============================================================================

def generate_batch_jsonl(volume_id: int, start_chap: int, end_chap: int, output_jsonl: str):
    """Generate batch JSONL for chapter outlines (not beats)."""
    requests = []

    for chapter_id in range(start_chap, end_chap + 1):
        outline = load_chapter_outline(volume_id, chapter_id)
        if not outline:
            continue

        custom_id = f"v{volume_id:02d}_ch{chapter_id:03d}"

        # Build prompt similar to generate_chapter_content
        prompt_parts = [
            f"【章节大纲】:\n标题：{outline.get('title', '')}\n概述：{outline.get('overview', '')}\n",
        ]

        # Inject entity context
        entity_list = outline.get("entity_list", [])
        entities = load_entity_cards(entity_list)
        if entities["characters"]:
            prompt_parts.append(f"【角色】: {json.dumps(entities['characters'], ensure_ascii=False)}\n")
        if entities["scenes"]:
            prompt_parts.append(f"【场景】: {json.dumps(entities['scenes'], ensure_ascii=False)}\n")

        # Add writing guide
        writing_guide = load_writing_guide(volume_id)
        if writing_guide:
            prompt_parts.append(f"【写作指南】: {writing_guide}\n")

        prompt_parts.append("请根据章节大纲创作正文，约6000字。直接输出正文。")

        request_obj = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v4/chat/completions",
            "body": {
                "model": "glm-4",
                "messages": [{"role": "user", "content": "\n".join(prompt_parts)}],
                "temperature": 0.85
            }
        }
        requests.append(request_obj)

    with open(output_jsonl, 'w', encoding='utf-8') as f:
        for req in requests:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")

    print(f"[✓] 已生成包含 {len(requests)} 个请求的 Batch 文件: {output_jsonl}")


def process_batch_results(result_jsonl: str):
    """Process batch results and save chapters."""
    if not os.path.exists(result_jsonl):
        print(f"[ERROR] 找不到结果文件: {result_jsonl}")
        return

    chapters_map = {}

    with open(result_jsonl, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            custom_id = data["custom_id"]
            try:
                content = data["response"]["body"]["choices"][0]["message"]["content"]
            except (KeyError, TypeError):
                content = "（该段场景生成失败）"

            chapters_map[custom_id] = content

    for custom_id, content in chapters_map.items():
        # Parse custom_id: v01_ch001
        parts = custom_id.split("_")
        vol_id = int(parts[0][1:])
        ch_id = int(parts[1][2:])

        save_chapter_content(vol_id, ch_id, content)


def get_world_context() -> str:
    """Get world context for backward compatibility."""
    from core.context_assembler import assemble_context
    path = Path(SETTINGS_DIR) / "world_setting.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""