"""
gen_deai_engine — 去AI味引擎 Skill

从 StoryForge anti-ai-adapter.ts 移植。
on_chapter_render() 执行去AI味检测：高频词统计 + 五维评分。
"""

import re
from collections import Counter
from core.base_skill import BaseSkill

# ── 高频AI词汇（80+ 个，按类别组织） ───────────────────────────────────────────
# Ported from StoryForge anti-ai-adapter.ts extractHighFreqWords()

AI_FATIGUE_WORDS = [
    # 连接词类（29个）
    "不禁", "不由得", "忍不住", "顿时", "忽然", "猛然", "骤然", "倏然", "陡然", "蓦然",
    "猛地", "一下子", "刹那", "顷刻", "转瞬", "瞬间", "霎时", "眨眼间", "旋即", "当即",
    "立刻", "马上", "赶紧", "急忙", "连忙", "赶忙", "匆匆", "猛然间", "蓦然间",

    # 形容词/副词类（25个）
    "缓缓", "微微", "淡淡", "幽幽", "静静", "轻轻", "悄悄", "默默", "暗暗", "隐隐",
    "狠狠", "死死", "牢牢", "渐渐", "慢慢", "款款", "徐徐", "盈盈", "凛然", "漠然",
    "木然", "释然", "欣然", "哑然", "恍然",

    # 动作描写类（21个）
    "嘴角上扬", "身躯一震", "瞳孔放大", "倒吸一口凉气", "深吸一口气",
    "喃喃自语", "目光深邃", "神色复杂", "眼神闪烁", "眉头紧锁", "拳头紧握",
    "嘴唇颤抖", "脸色苍白", "冷汗直流", "身体僵硬", "身形一晃",
    "脚步踉跄", "眼前一黑", "心头一震", "浑身一颤", "面不改色",

    # 心理描写类（15个）
    "心中一沉", "心头一暖", "百感交集", "五味杂陈", "思绪万千",
    "心乱如麻", "难以置信", "哭笑不得", "无言以对", "不知所措",
    "忐忑不安", "心神不宁", "如释重负", "暗自庆幸", "心生警惕",

    # 其他高频AI词（16个）
    "仿佛", "似乎", "好像", "犹如", "宛若", "如同",
    "某种", "某种程度", "某种意义", "某种方式",
    "充斥着", "弥漫着", "笼罩着", "回荡着", "泛起", "涌动",
]

# ── 模板模式（25+ 条） ──────────────────────────────────────────────────────────

AI_OVERUSED_PATTERNS = [
    # 原有 10 条
    (r"他(不禁|不由得|忍不住)", "意志力表达过频"),
    (r"(缓缓|慢慢|渐渐)地", "过程描写过频"),
    (r"嘴角.*上扬", "微表情模板化"),
    (r"心中.*震", "内心反应模板化"),
    (r"仿佛.*一般", "比喻句式过频"),
    (r"似乎[^，]{0,10}", "模糊表达过频"),
    (r"(突然|忽然|一瞬间)", "突发转折过频"),
    (r"眼神.*闪过一丝", "眼神描写模板化"),
    (r"深吸一口气", "准备动作模板化"),
    (r"喃喃自语[^。]", "自言自语过频"),

    # 新增 15 条
    (r"(仿佛|犹如|宛若).{2,8}(一般|般|似的)", "比喻泛滥"),
    (r".{2,6}的感觉", "X的感觉句式"),
    (r".{1,4}了起来", "X了起来句式"),
    (r"(微微|淡淡|缓缓|轻轻)(地)?(一)?(笑|叹|摇|点|抬)", "X的X重复"),
    (r"心中(一凛|苦笑|暗骂|叹息|感动)", "心理描写模板"),
    (r"空气(仿佛|似乎)", "环境描写模板"),
    (r"周围(一片|陷入)", "环境描写模板"),
    (r"就在这时", "过渡模板"),
    (r"正在此时", "过渡模板"),
    (r"(露|流|闪)出.*(笑容|表情|神光)", "X出Y泛滥"),
    (r"的.{1,4}，.{1,8}的", "修辞堆叠"),
    (r"(响|泛|涌|升|浮)起", "X起句式"),
    (r"在.*(的)?(目光|注视|视线|眼神)中", "X在Y中"),
    (r"(过了)?(良久|许久|片刻|少顷)", "时间状语模板"),
    (r"(结果|最终|终究|终究是)", "结果句式"),
    (r"倒抽一口冷气", "倒吸凉气变体"),
    # 对仗解释句式（AI最高频指纹）
    (r"不是.{2,15}而是", "不是A而是B句式"),
    (r"不是.{2,10}是(?!的)", "不是A是B句式"),
    (r"不仅.{2,15}更是", "不仅A更是B句式"),
    (r"与其说.{2,15}不如说", "与其说A不如说B句式"),
    (r"不像.{2,10}倒像", "不像A倒像B句式"),

    # ── 过度解释/主题总结（StoryScope 2026: 77% AI vs 52% human）──
    (r"(让|令|使).{2,8}(终于|终于|彻底|真正|完全)(明白|意识到|懂得|领悟|理解|知道|认清)", "角色顿悟模板"),
    (r"这.{2,10}(告诉|启示|让.{2,5}明白|让.{2,5}懂得)", "主题总结句式"),
    (r"(原来|其实).{2,10}(才是|并不|从未|本就)", "真相揭示模板"),
    (r"人生.{2,15}(道理|哲理|真谛|就是这样|本就)", "人生哲理陈述"),
    (r"(命运|世间|这世上|这世界|老天).{2,10}(总是|从来|不会|从不)", "命运感慨模板"),
    (r"他(终于|终于|彻底|真正)明白.{0,20}(道理|真意|含义|深意|意义)", "角色领悟总结"),
    (r"这一.{2,6}(让|令|使).{2,12}(意识到|认识到|体会到|感受到)", "事件触发领悟"),
    (r"(原来|其实|说到底).{2,20}(道理是|真相是|本质是|关键是)", "本质解释句式"),
    (r"这也.{2,15}(教训|启示|警醒|提醒)", "教训总结句式"),
    (r"从此以后.{0,20}(他|她|他们)", "从此以后总结"),
    (r"终究.{2,10}(敌不过|逃不过|抵不过|躲不过)", "命运感概"),
    (r"(这世间|天地间|世间).{2,15}(法则|规矩|道理|秩序)", "世界观解释"),
    (r"(说到底|归根结底|总而言之|综上).{0,20}(就是|还是|才是)", "总结性陈述"),
]


# ── 常见AI词替换建议 ───────────────────────────────────────────────────────────

REPLACEMENT_MAP = {
    "缓缓": "慢慢/一点一点/不动声色地",
    "微微": "略略/轻轻/稍稍",
    "淡淡": "平静/冷淡/随意",
    "幽幽": "低低/无声地/悄然",
    "静静": "安静地/默不作声地/不动",
    "轻轻": "略略/小心地/不着痕迹地",
    "悄悄": "暗自/不动声色地/不露声色",
    "默默": "无言地/沉默地/不发一言",
    "暗暗": "暗自/悄悄/不动声色",
    "隐隐": "隐约/微微/若有若无",
    "狠狠": "用力/狠劲/重重",
    "死死": "紧紧/牢牢/拼命",
    "牢牢": "紧紧/稳固地/牢牢地",
    "渐渐": "逐渐/慢慢地/一点一点",
    "慢慢": "逐渐/一点一点/不慌不忙",
    "款款": "缓缓/从容地/不疾不徐",
    "徐徐": "缓缓/慢慢地/不紧不慢",
    "盈盈": "满溢/荡漾/波光粼粼",
    "凛然": "威严地/正气凛然/不怒自威",
    "漠然": "冷淡地/无动于衷/毫不在意",
    "木然": "呆滞地/毫无表情/面无表情",
    "释然": "放下/坦然/如释重负",
    "欣然": "高兴地/欣然/痛快",
    "哑然": "沉默/无言/愣住",
    "恍然": "猛然/突然/一下子",
    "不禁": "不由/下意识/忍不住",
    "不由得": "忍不住/下意识/不由自主",
    "忍不住": "不由自主/一下子/没忍住",
    "顿时": "立刻/当即/马上",
    "忽然": "突然/猛地/冷不丁",
    "猛然": "猛地/骤然/猝然",
    "骤然": "突然/一下子/猛然",
    "倏然": "忽然/一下子/转瞬",
    "陡然": "突然/猛地/一下子",
    "蓦然": "忽然/猛然/一下子",
    "猛地": "突然/一下子/猝然",
    "一下子": "突然/猛然/瞬间",
    "刹那": "瞬间/片刻/一眨眼",
    "顷刻": "立刻/马上/瞬间",
    "转瞬": "转眼/瞬间/一眨眼",
    "瞬间": "一眨眼/刹那/片刻",
    "霎时": "突然/一下子/顷刻",
    "眨眼间": "转眼/一眨眼/瞬间",
    "旋即": "立刻/当即/马上",
    "当即": "立刻/马上/当场",
    "立刻": "马上/当即/立刻",
    "马上": "立刻/当即/马上",
    "赶紧": "急忙/连忙/赶快",
    "急忙": "匆忙/赶紧/连忙",
    "连忙": "赶紧/急忙/赶忙",
    "赶忙": "赶紧/急忙/连忙",
    "匆匆": "匆忙/急匆匆/急急忙忙",
    "仿佛": "好像/似乎/像是",
    "似乎": "好像/仿佛/似乎",
    "好像": "仿佛/似乎/如同",
    "犹如": "如同/好像/宛如",
    "宛若": "宛如/好似/如同",
    "如同": "好像/犹如/宛如",
    "某种": "一种/某种程度/某种方式",
    "充斥着": "满是/充满/到处是",
    "弥漫着": "笼罩/充满/四处都是",
    "笼罩着": "覆盖/包围/笼罩",
    "回荡着": "回响/回荡/余音",
    "泛起": "涌起/泛起/冒出",
    "涌动": "翻涌/涌动/涌动",
    "掠过": "闪过/掠过/扫过",
    "闪过": "掠过/一闪/掠过",
    "浮现": "显现/浮现/冒出",
    "迸发": "爆发/迸发/涌出",
    "绽放": "盛开/绽放/展开",
    "身躯一震": "身体一颤/猛地一怔/身形一顿",
    "瞳孔放大": "瞳孔收缩/眼睛睁大/瞳孔骤缩",
    "倒吸一口凉气": "倒抽冷气/倒吸一口凉气/倒抽一口冷气",
    "深吸一口气": "长吸一口气/吸了口气/深吸",
    "目光深邃": "目光幽深/眼神深邃/目光深沉",
    "神色复杂": "神情复杂/神色难辨/神色微妙",
    "眼神闪烁": "眼神游移/目光闪烁/眼神飘忽",
    "眉头紧锁": "紧皱眉头/眉头紧皱/眉心紧蹙",
    "拳头紧握": "攥紧拳头/双拳紧握/紧握双拳",
    "嘴唇颤抖": "嘴唇微颤/唇瓣颤抖/嘴唇发抖",
    "脸色苍白": "面色惨白/脸色煞白/面色发白",
    "冷汗直流": "冷汗涔涔/冷汗直冒/冷汗直流",
    "身体僵硬": "浑身僵硬/身体一僵/身子发僵",
    "身形一晃": "身形一颤/身子一晃/身形微晃",
    "脚步踉跄": "脚步虚浮/踉跄后退/脚步不稳",
    "眼前一黑": "眼前发黑/视线一暗/眼前一暗",
    "心头一震": "心中一颤/心头一凛/心中一震",
    "浑身一颤": "身子一颤/浑身一震/身体微颤",
    "面不改色": "神色不变/面不改色/不动声色",
    "心中一沉": "心头一沉/心中一凛/心中暗沉",
    "心头一暖": "心中一暖/心头一热/心中微暖",
    "百感交集": "感慨万千/百感交集/思绪翻涌",
    "五味杂陈": "百感交集/感慨万千/心中复杂",
    "思绪万千": "思绪翻涌/百感交集/心绪万千",
    "心乱如麻": "心烦意乱/心绪纷乱/心乱如麻",
    "难以置信": "不可思议/无法相信/出乎意料",
    "哭笑不得": "啼笑皆非/哭笑不得/无奈",
    "无言以对": "哑口无言/无话可说/一时语塞",
    "不知所措": "慌了神/手足无措/一时愣住",
    "忐忑不安": "心神不宁/七上八下/心里忐忑",
    "心神不宁": "心神不定/心绪不宁/心神恍惚",
    "如释重负": "松了口气/长舒一口气/放下重担",
    "暗自庆幸": "暗自高兴/暗自窃喜/暗自庆幸",
    "心生警惕": "心生戒备/警觉/心生防备",
    "嘴角上扬": "嘴角微翘/唇角微扬/嘴角勾起",
    "面不改色": "神色不变/不动声色/面不改色",
}


class GenDeaiEngineSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "去AI味引擎"
        self.threshold = 5  # 同一词出现超过此次数才报警

    def on_init(self) -> None:
        try:
            print(f"  [OK] {self.name} ready: {len(AI_FATIGUE_WORDS)} words, {len(AI_OVERUSED_PATTERNS)} patterns, L1-L6 layers active")
        except UnicodeEncodeError:
            print(f"  [OK] {self.name} ready: {len(AI_FATIGUE_WORDS)} words, {len(AI_OVERUSED_PATTERNS)} patterns")

    def on_chapter_render(self, full_text: str, chapter_id: int) -> str:
        """渲染前去AI味检测，结果写入 shared_state"""
        report = self.analyze(full_text)
        self.context.set_shared("deai_report", report)
        self.context.set_shared("deai_banned_words", list(report.get("flagged_words", {}).keys()))
        self.context.set_shared("deai_templates", list(report.get("flagged_patterns", {}).keys()))
        self._print_report(report, chapter_id)
        return full_text

    def analyze(self, text: str) -> dict:
        """分析文本，返回六维评分（L1-L6 去AI味层次）。"""
        # L1: 高频词检测
        word_counts = {}
        for word in AI_FATIGUE_WORDS:
            count = text.count(word)
            if count > 0:
                word_counts[word] = count
        flagged_words = {w: c for w, c in word_counts.items() if c >= self.threshold}

        # L2: 模板模式检测
        pattern_counts = {}
        for pattern, label in AI_OVERUSED_PATTERNS:
            matches = len(re.findall(pattern, text))
            if matches > 0:
                pattern_counts[label] = matches
        flagged_patterns = {p: c for p, c in pattern_counts.items() if c >= self.threshold}

        # L3: 形容词/副词密度（每300字≥7个 → 标记）
        adj_density = self._check_adj_adv_density(text, window=300, threshold=7)
        # L4: 四字成语密度（每500字≥4个连续或同段≥3个 → 标记）
        idiom_density = self._check_idiom_density(text, window=500, threshold=4)
        # L5: 段落变异度（段长方差过小 → AI均匀感）
        para_variation = self._check_paragraph_variation(text)
        # L6: 标点节奏（省略号/感叹号密度）
        punct_rhythm = self._check_punctuation_rhythm(text)

        # L7: 2-gram 重复检测
        ngram_flagged = self._detect_bigram_repetition(text, window_chars=500, max_count=8)

        # L8: 过度解释/主题总结 (StoryScope 2026 — 77% AI vs 52% human)
        over_explain = self._check_over_explanation(text)

        # 句式多样性
        sentences = re.split(r'[。！？\n]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
        if len(sentences) >= 3:
            lengths = [len(s) for s in sentences]
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            syntax_score = min(100, max(10, 100 - variance * 0.5))
        else:
            syntax_score = 50

        # 对话标签多样性
        dialogue_tags = re.findall(r'(说道|答道|问道|叫道|喊道|说道|笑着说|冷声道|低声道|淡淡道|沉声道|开口)', text)
        unique_tags = len(set(dialogue_tags)) if dialogue_tags else 1
        dialogue_score = min(100, unique_tags * 12)

        # 综合打分（六层权重）
        vocab_score = max(10, 100 - len(flagged_words) * 4)
        pattern_score = max(10, 100 - len(flagged_patterns) * 6)
        ngram_penalty = len(ngram_flagged) * 3
        ngram_score = max(10, 100 - ngram_penalty)

        dimensions = [
            {"name": "词汇多样性(L1)", "score": max(10, vocab_score), "markers": list(flagged_words.keys())},
            {"name": "模板化程度(L2)", "score": max(10, pattern_score), "markers": list(flagged_patterns.keys())},
            {"name": "修饰密度(L3)", "score": adj_density["score"], "markers": adj_density.get("samples", [])},
            {"name": "成语密度(L4)", "score": idiom_density["score"], "markers": idiom_density.get("samples", [])},
            {"name": "段落变异(L5)", "score": para_variation["score"], "markers": para_variation.get("issues", [])},
            {"name": "标点节奏(L6)", "score": punct_rhythm["score"], "markers": punct_rhythm.get("issues", [])},
            {"name": "句式变化(L7)", "score": max(10, int(syntax_score)), "markers": []},
            {"name": "对话自然度(L8)", "score": max(10, dialogue_score), "markers": []},
            {"name": "过度解释(L9)", "score": over_explain["score"], "markers": over_explain.get("samples", [])},
        ]

        overall = int(sum(d["score"] for d in dimensions) / len(dimensions))

        return {
            "overall_score": overall,
            "dimensions": dimensions,
            "flagged_words": flagged_words,
            "flagged_patterns": flagged_patterns,
            "ngram_flagged": ngram_flagged,
            "adj_density": adj_density,
            "idiom_density": idiom_density,
            "para_variation": para_variation,
            "punct_rhythm": punct_rhythm,
            "suggestions": self._generate_suggestions(flagged_words, flagged_patterns, ngram_flagged),
        }

    def _check_adj_adv_density(self, text: str, window: int = 300, threshold: int = 7) -> dict:
        """
        L3: 形容词/副词密度检测
        AI 倾向于过度修饰。检测"的""地"结构前的修饰词密度。
        每 window 字内形容词/副词超过 threshold → 标记。
        """
        # 提取"的""地"结尾的修饰结构
        adj_pattern = re.findall(r'[一-鿿]{2,4}的', text)
        adv_pattern = re.findall(r'[一-鿿]{2,4}地', text)
        total_modifiers = len(adj_pattern) + len(adv_pattern)
        # 按每300字归一化
        chars = len(re.findall(r'[一-鿿]', text))
        if chars == 0:
            return {"score": 100, "density": 0}
        density = total_modifiers / (chars / window)
        score = max(10, 100 - int(density * 10))
        return {
            "score": min(100, score),
            "density": round(density, 1),
            "modifier_count": total_modifiers,
            "samples": adj_pattern[:5] + adv_pattern[:3] if density > threshold else [],
        }

    def _check_idiom_density(self, text: str, window: int = 500, threshold: int = 4) -> dict:
        """
        L4: 四字成语密度 + 对话意图检测
        AI 过度使用四字成语 + 对话缺乏意图标签（试探/回避/施压/诱导/挑衅/敷衍）。
        """
        # 四字成语检测
        four_char = re.findall(r'[一-鿿]{4}', text)
        chars = len(re.findall(r'[一-鿿]', text))
        if chars == 0:
            return {"score": 100, "density": 0}
        density = len(four_char) / (chars / window)
        consecutive = 0
        max_consecutive = 0
        for match in re.finditer(r'(?:[一-鿿]{4}[，、,\s]?){2,}', text):
            count = len(re.findall(r'[一-鿿]{4}', match.group()))
            max_consecutive = max(max_consecutive, count)

        # 对话意图标签检测（AI经典问题：对话无意图推进）
        intent_patterns = {
            "试探": r'试探|试试|测试|看看',
            "回避": r'避开|转移|绕开|不说|没回答',
            "施压": r'逼|催|威胁|警告|最后',
            "诱导": r'引导|暗示|透露|泄露',
            "挑衅": r'冷笑|嘲讽|不屑|挑衅',
            "敷衍": r'随便|再说|以后|改天|应付',
        }
        dialog_lines = re.findall(r'[「「""].*?[」」""]', text)
        intent_hits = 0
        for line in dialog_lines:
            for intent, pat in intent_patterns.items():
                if re.search(pat, line):
                    intent_hits += 1
                    break
        intent_ratio = intent_hits / max(len(dialog_lines), 1)
        intent_penalty = max(0, (0.5 - intent_ratio) * 40)  # 少于50%对话有意图则扣分

        score = max(10, 100 - int(density * 12) - max_consecutive * 3 - int(intent_penalty))
        return {
            "score": min(100, score),
            "density": round(density, 1),
            "four_char_count": len(four_char),
            "max_consecutive": max_consecutive,
            "dialogue_intent_ratio": round(intent_ratio, 2),
            "samples": four_char[:8] if density > threshold or max_consecutive >= 2 else [],
        }

    def _check_paragraph_variation(self, text: str) -> dict:
        """
        L5: 段落变异度检测
        AI 段落长度过于均匀。单句段25-45%、段长20-100字为健康范围。
        全部段落长度方差过小 → AI 均匀感。
        """
        paragraphs = re.split(r'\n+', text)
        paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 10]
        if len(paragraphs) < 3:
            return {"score": 100, "variance": 0, "single_ratio": 0, "issues": []}

        para_lens = [len(p) for p in paragraphs]
        avg = sum(para_lens) / len(para_lens)
        variance = sum((l - avg) ** 2 for l in para_lens) / len(para_lens)
        # 单句段比例
        single_sentence = sum(1 for p in paragraphs if p.count('。') <= 1)
        single_ratio = single_sentence / len(paragraphs)

        issues = []
        if variance < 200:
            issues.append(f"段长方差过小({variance:.0f})，疑似AI均匀感")
        if single_ratio < 0.15:
            issues.append(f"单句段过少({single_ratio:.0%})，需要打破节奏")
        if single_ratio > 0.6:
            issues.append(f"单句段过多({single_ratio:.0%})，可能过于碎片化")

        score = max(10, 100 - len(issues) * 15 - max(0, (200 - variance) / 20))
        return {"score": min(100, int(score)), "variance": int(variance), "single_ratio": round(single_ratio, 2), "issues": issues}

    def _check_punctuation_rhythm(self, text: str) -> dict:
        """
        L6: 标点节奏检测
        AI 过度使用省略号/感叹号/破折号制造情绪。
        省略号≤5/千字、感叹号≤8/千字、破折号≤5/千字。
        """
        chars_count = len(re.findall(r'[一-鿿]', text))
        if chars_count == 0:
            return {"score": 100, "ellipsis": 0, "exclamation": 0, "dash": 0}
        chars_per_k = chars_count / 1000

        ellipsis = len(re.findall(r'…{1,}|\.{3,}', text)) / chars_per_k
        exclamation = len(re.findall(r'！+', text)) / chars_per_k
        dash = len(re.findall(r'——|—', text)) / chars_per_k

        issues = []
        if ellipsis > 5:
            issues.append(f"省略号过多({ellipsis:.1f}/千字)")
        if exclamation > 8:
            issues.append(f"感叹号过多({exclamation:.1f}/千字)")
        if dash > 5:
            issues.append(f"破折号过多({dash:.1f}/千字)")

        score = max(10, 100 - len(issues) * 12 - int(max(0, ellipsis - 5) * 3 + max(0, exclamation - 8) * 2 + max(0, dash - 5) * 3))
        return {
            "score": min(100, int(score)),
            "ellipsis_per_k": round(ellipsis, 1),
            "exclamation_per_k": round(exclamation, 1),
            "dash_per_k": round(dash, 1),
            "issues": issues,
        }

    def _check_over_explanation(self, text: str) -> dict:
        """
        L9: 过度解释/主题总结检测
        StoryScope 2026: 77% AI stories have narrator explain theme vs 52% human.
        Detects: explicit moral lessons, philosophical monologues, tidy chapter-end summaries.

        Returns {score, matches, samples, density}
        """
        OVER_EXPLAIN_PATTERNS = [
            (r"(让|令|使).{2,8}(终于|彻底|真正|完全)(明白|意识到|懂得|领悟|理解|知道|认清)", "角色顿悟"),
            (r"这.{2,10}(告诉|启示|让.{2,5}明白)", "主题总结"),
            (r"(原来|其实).{2,10}(才是|并不|从未|本就)", "真相揭示"),
            (r"人生.{2,15}(道理|哲理|真谛|就是这样|本就)", "人生哲理"),
            (r"(命运|世间|这世上|这世界|老天).{2,10}(总是|从来|不会|从不)", "命运感慨"),
            (r"他(终于|彻底|真正)明白.{0,20}(道理|真意|含义|深意|意义)", "角色领悟总结"),
            (r"这一.{2,6}(让|令|使).{2,12}(意识到|认识到|体会到)", "事件触发领悟"),
            (r"(原来|其实|说到底).{2,20}(道理是|真相是|本质是|关键是)", "本质解释"),
            (r"这也.{2,15}(教训|启示|警醒|提醒)", "教训总结"),
            (r"从此以后.{0,20}(他|她|他们)", "从此以后总结"),
            (r"终究.{2,10}(敌不过|逃不过|抵不过|躲不过)", "命运感概"),
            (r"(这世间|天地间|世间).{2,15}(法则|规矩|道理|秩序)", "世界观解释"),
            (r"(说到底|归根结底|总而言之|综上).{0,20}(就是|还是|才是)", "总结陈述"),
        ]

        matches = []
        for pattern, label in OVER_EXPLAIN_PATTERNS:
            found = re.findall(pattern, text)
            if found:
                for m in found:
                    snippet = m if isinstance(m, str) else ''.join(m)
                    matches.append({"label": label, "snippet": snippet[:30]})

        chars = len(re.findall(r'[一-鿿]', text))
        if chars == 0:
            return {"score": 100, "matches": 0, "samples": [], "density": 0.0}

        density = len(matches) / (chars / 1000)  # per 1000 chars
        # Score: each match costs 5 points, density > 2 costs extra
        penalty = len(matches) * 5 + max(0, (density - 2.0) * 10)
        score = max(10, 100 - int(penalty))

        samples = [f"{m['label']}: {m['snippet']}" for m in matches[:5]]

        return {
            "score": min(100, score),
            "matches": len(matches),
            "samples": samples,
            "density": round(density, 1),
        }

    def _detect_bigram_repetition(self, text: str, window_chars: int = 500, max_count: int = 8) -> list:
        """
        检测二字词在滑动窗口内的重复频率。
        如果某二字词在任意 window_chars 字窗口内出现 >= max_count 次，标记为高频重复。
        """
        # 提取所有中文字符二字词
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        if len(chinese_chars) < window_chars:
            return []

        # 提取所有二字词
        bigrams = [chinese_chars[i] + chinese_chars[i + 1] for i in range(len(chinese_chars) - 1)]
        if not bigrams:
            return []

        # 用滑动窗口检查每个词在任意窗口内的频率
        flagged = []
        window_start = 0
        window_counter = Counter()

        for window_end in range(len(bigrams)):
            # 扩展窗口直到达到字符数限制
            while window_start < window_end:
                # 计算当前窗口内的字符数（近似）
                window_start_chars = sum(len(b) for b in bigrams[window_start:window_end])
                if window_start_chars > window_chars:
                    window_counter[bigrams[window_start]] -= 1
                    if window_counter[bigrams[window_start]] <= 0:
                        del window_counter[bigrams[window_start]]
                    window_start += 1

            window_counter[bigrams[window_end]] += 1

            # 检查是否有词超过阈值
            for word, count in window_counter.items():
                if count >= max_count and word not in flagged:
                    flagged.append(word)

        return flagged

    def _generate_suggestions(self, flagged_words: dict, flagged_patterns: dict, ngram_flagged: list = None) -> list:
        suggestions = []
        if flagged_words:
            top_words = sorted(flagged_words.items(), key=lambda x: -x[1])[:3]
            suggestions.append(f"减少使用: {', '.join(w for w, _ in top_words)}（各出现{sum(c for _, c in top_words)}次）")

            # 输出具体替换建议
            for word, count in top_words:
                if word in REPLACEMENT_MAP:
                    suggestions.append(f"  → {word} → {REPLACEMENT_MAP[word]}（出现{count}次）")

        if flagged_patterns:
            suggestions.append(f"增加句式多样性，避免模板化表达: {', '.join(list(flagged_patterns.keys())[:3])}")

        if ngram_flagged:
            suggestions.append(f"高频重复二字词: {', '.join(ngram_flagged[:5])}（在500字窗口内出现≥8次）")

        if not suggestions:
            suggestions.append("本章去AI味表现良好")
        return suggestions

    def _print_report(self, report: dict, chapter_id: int):
        overall = report["overall_score"]
        emoji = "🟢" if overall >= 80 else "🟡" if overall >= 60 else "🔴"
        print(f"\n{emoji} 去AI味检测 第{chapter_id}章: {overall}/100")
        for dim in report["dimensions"]:
            bar = "█" * (dim["score"] // 10) + "░" * (10 - dim["score"] // 10)
            print(f"  {dim['name']:8s} {bar} {dim['score']}")
        if report["suggestions"]:
            for s in report["suggestions"]:
                print(f"  → {s}")

    def on_before_scene_write(self, prompt_payload: list, beat_data: dict) -> list:
        """
        在场景写作前注入去AI味硬约束。
        从 shared_state 读取 deai_banned_words，构造 prompt 约束注入到 prompt_payload。
        """
        banned = self.context.get_shared("deai_banned_words", [])
        if banned:
            constraint = f"\n[去AI味约束] 禁止使用以下词汇：{'、'.join(banned[:15])}\n"
            prompt_payload.append(constraint)
        return prompt_payload
