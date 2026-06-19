"""
gen_writing_style — 写作风格系统 Skill

从 StoryForge writing-styles.ts 移植，11种写作风格。
on_before_scene_write() 注入风格指令到 prompt_payload。
"""

from core.base_skill import BaseSkill

# ── 风格数据库 ───────────────────────────────────────────────────────────────
# Ported from StoryForge writing-styles.ts

STYLE_DB = {
  "金庸武侠": {
    "promptInjection": "金庸风格。长句铺陈，白描淡写，人物对话文白相间。武功描写虚实结合，重意境不重力道。章回体叙事。",
    "vocabulary": [
      "内力",
      "轻功",
      "剑法",
      "门派",
      "江湖",
      "侠义",
      "恩怨",
      "天下"
    ],
    "avoidPatterns": [
      "数值化战力",
      "游戏化升级",
      "现代口语"
    ],
    "dialogueStyle": "文白相间，半文半白，长者言简后生急切",
    "narrativeDistance": "中远距离，说书人口吻，偶尔上帝视角点评"
  },
  "古龙风格": {
    "promptInjection": "古龙风格。短句断行，一句一段。留白暗示，对话机锋暗藏。环境氛围大于动作描写。寂寞美学贯穿始终。",
    "vocabulary": [
      "寂寞",
      "天涯",
      "刀",
      "酒",
      "夜色",
      "杀手",
      "风",
      "笑"
    ],
    "avoidPatterns": [
      "长篇打斗描写",
      "过度解释动机",
      "连续长句"
    ],
    "dialogueStyle": "短促机锋，四字为限，一问一答间刀光剑影",
    "narrativeDistance": "近距离跟随主角感官，大量环境氛围渲染"
  },
  "网文爽文": {
    "promptInjection": "快节奏爽文。主角每次出手都让读者解气。重在爽和燃，打脸要响，突破要震撼。",
    "vocabulary": [
      "碾压",
      "打脸",
      "震撼",
      "突破",
      "逆袭",
      "全场哗然"
    ],
    "avoidPatterns": [
      "主角长期压抑",
      "实力增长不明显",
      "反派说教"
    ],
    "dialogueStyle": "直接爽快，不拖泥带水，打脸台词要狠",
    "narrativeDistance": "紧跟主角，代入感强，读者视角=主角视角"
  },
  "热血燃向": {
    "promptInjection": "热血少年漫式。友情/努力/胜利。绝境中不放弃，每一次突破都燃到让人起鸡皮疙瘩。",
    "vocabulary": [
      "燃烧",
      "咆哮",
      "决不",
      "拼尽",
      "信念",
      "伙伴"
    ],
    "avoidPatterns": [
      "消极退让",
      "理性分析过多"
    ],
    "dialogueStyle": "吼出来的信念，简短有力的宣言",
    "narrativeDistance": "近景特写，强调动作和表情的冲击力"
  },
  "暗黑压抑": {
    "promptInjection": "暗黑风格。世界是残酷的，善意常常带来灾难。主角在黑暗中挣扎求存，道德灰色地带。",
    "vocabulary": [
      "腐烂",
      "阴影",
      "绝望",
      "背叛",
      "挣扎",
      "血迹"
    ],
    "avoidPatterns": [
      "阳光结局",
      "单纯的善恶对立",
      "奇迹逆转"
    ],
    "dialogueStyle": "冷静克制，偶有崩溃爆发",
    "narrativeDistance": "沉溺式，强调环境的压迫感和内心的寒冷"
  },
  "幽默吐槽": {
    "promptInjection": "轻松幽默吐槽风。主角自带吐槽体质，内心OS比对话多。用笑点包装严肃剧情。",
    "vocabulary": [
      "卧槽",
      "离谱",
      "什么鬼",
      "救命",
      "无语"
    ],
    "avoidPatterns": [
      "过于正经的叙述",
      "长篇大道理"
    ],
    "dialogueStyle": "吐槽+内心弹幕，对话轻松日常感强",
    "narrativeDistance": "第一人称或紧贴第一人称，内心OS丰富"
  },
  "纯文学": {
    "promptInjection": "纯文学质感。注重语言质地和人性深度。场景为心理服务，留白多于填充。",
    "vocabulary": [],
    "avoidPatterns": [
      "套路化情节",
      "脸谱化角色",
      "过度戏剧化",
      "网文爽感"
    ],
    "dialogueStyle": "暗示多于明说，潜台词丰富",
    "narrativeDistance": "意识流，内心世界为主"
  },
  "文艺唯美": {
    "promptInjection": "唯美文艺风。画面感优先，用诗化的比喻描绘世界。每段都像一幅插画。",
    "vocabulary": [
      "光影",
      "琉璃",
      "微风",
      "繁花",
      "星光",
      "涟漪"
    ],
    "avoidPatterns": [
      "粗俗用语",
      "快节奏"
    ],
    "dialogueStyle": "温柔含蓄，留有余味",
    "narrativeDistance": "中远距离，镜头感强"
  },
  "白描纪实": {
    "promptInjection": "冷峻白描。不加修饰地呈现事实和动作。只用动词和名词，零心理描写。读者自己判断。",
    "vocabulary": [],
    "avoidPatterns": [
      "形容词",
      "副词",
      "心理独白",
      "作者评价"
    ],
    "dialogueStyle": "纯对话，不带任何修饰词",
    "narrativeDistance": "摄像头式，只记录不解释"
  },
  "硬汉冷峻": {
    "promptInjection": "硬汉派。硬朗简洁，不动声色。像雷蒙德·钱德勒式：冷峻的外壳下藏着对人性的洞察。",
    "vocabulary": [
      "枪",
      "街",
      "暗",
      "冷",
      "夜",
      "酒精"
    ],
    "avoidPatterns": [
      "煽情",
      "长篇内心独白"
    ],
    "dialogueStyle": "简洁有力，每句话都带刺",
    "narrativeDistance": "第一人称硬汉视角，看透一切但不说透"
  },
  "第一人称口语化": {
    "promptInjection": "口语化第一人称。主角用自己的口吻讲自己的故事，像朋友跟你聊天一样自然。带方言/口头禅。",
    "vocabulary": [],
    "avoidPatterns": [
      "书面化长句",
      "第三人称客观描述"
    ],
    "dialogueStyle": "我就是我，说话就是这个调调",
    "narrativeDistance": "完全第一人称，口语节奏，可以跑题可以纠正自己"
  },
  "多视角切换": {
    "promptInjection": "多视角叙事。不同角色章节轮流担任POV，每个视角有独特的语言风格和信息盲区。",
    "vocabulary": [],
    "avoidPatterns": [
      "全知视角",
      "单一视角"
    ],
    "dialogueStyle": "随视角角色性格变化",
    "narrativeDistance": "每章固定一个视角，章末自然切换到下一视角"
  },
  "说书风": {
    "promptInjection": "传统说书人风格。且听下回分解。和读者直接互动，评点人物命运。像单田芳/郭德纲说书。",
    "vocabulary": [
      "话说",
      "列位",
      "且说",
      "按下不表",
      "花开两朵各表一枝"
    ],
    "avoidPatterns": [
      "西方小说式内心独白",
      "模板化表达"
    ],
    "dialogueStyle": "说书人腔调，人物对话夹在叙述中",
    "narrativeDistance": "说书人站在故事之外，随时可以点评和预告"
  },
  "剧本风": {
    "promptInjection": "剧本/视觉化写作。每个段落都是可直接拍摄的分镜。场景/动作/对白清晰分离。",
    "vocabulary": [],
    "avoidPatterns": [
      "内心独白",
      "叙述者评价"
    ],
    "dialogueStyle": "纯对白推进，动作描写精简到分镜级别",
    "narrativeDistance": "摄像机视角，只记录可见可听的内容"
  },
  "意识流": {
    "promptInjection": "意识流风格。思绪自由流动，时间跳跃，感官碎片拼贴。适合描写角色的内心风暴。",
    "vocabulary": [],
    "avoidPatterns": [
      "线性叙事",
      "因果关系明确的连接词"
    ],
    "dialogueStyle": "打断、跳跃、不完整",
    "narrativeDistance": "完全沉浸在第一人称的思维碎片中"
  },
  "轻小说": {
    "promptInjection": "日式轻小说风格。轻松明快，对话为主，描写简洁。角色互动萌点突出。",
    "vocabulary": [],
    "avoidPatterns": [
      "沉重哲学思辨",
      "过度严肃",
      "长篇景物描写"
    ],
    "dialogueStyle": "活泼自然，个性鲜明，吐槽和卖萌并重",
    "narrativeDistance": "第一人称近距离，日常感强"
  },
  "硬核科幻": {
    "promptInjection": "硬核科幻风格。科学逻辑自洽，技术设定有真实物理/生物/CS依据。用科学思维推演剧情。",
    "vocabulary": [
      "熵",
      "奇点",
      "量子",
      "维度",
      "光年",
      "文明"
    ],
    "avoidPatterns": [
      "科学原理凭空捏造",
      "技术万能论",
      "无视物理规律"
    ],
    "dialogueStyle": "准确清晰，可含术语但不卖弄",
    "narrativeDistance": "第三人称有限视角，保持理性"
  },
  "黑色幽默": {
    "promptInjection": "黑色幽默。用荒诞和讽刺包裹严肃主题。笑着笑着就笑不出来了才是好的黑色幽默。",
    "vocabulary": [],
    "avoidPatterns": [
      "煽情",
      "说教",
      "感伤"
    ],
    "dialogueStyle": "反讽、双关、装傻、一本正经说胡话",
    "narrativeDistance": "冷眼旁观的讲述者，含而不露的讽刺"
  },
  "暗黑哥特": {
    "promptInjection": "暗黑哥特式。阴冷氛围，颓废美，人性阴暗面的诗化表达。死亡与美共存。",
    "vocabulary": [
      "腐朽",
      "阴影",
      "诅咒",
      "鲜血",
      "月光",
      "墓碑"
    ],
    "avoidPatterns": [
      "阳光结局",
      "道德说教",
      "轻松日常"
    ],
    "dialogueStyle": "咏叹调式，带诗性，沉重",
    "narrativeDistance": "沉溺式感官描写，压抑氛围铺满"
  },
  "现代极简": {
    "promptInjection": "海明威式极简。少即是多。用最短的句子表达最丰富的意思。冰山原则。",
    "vocabulary": [],
    "avoidPatterns": [
      "形容词堆砌",
      "冗余比喻",
      "修饰从句"
    ],
    "dialogueStyle": "省略引述动词，纯对白，留白巨大",
    "narrativeDistance": "冰山原则——省略的比呈现的多"
  }
}

DEFAULT_STYLE = "网文爽文"


class GenWritingStyleSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "写作风格系统"
        self.current_style = DEFAULT_STYLE

    def on_init(self) -> None:
        self.context.set_shared("style_config", {
            "current": self.current_style,
            "available": list(STYLE_DB.keys()),
        })
        print(f"  [✓] {self.name} 已就绪（风格: {self.current_style}, 共{len(STYLE_DB)}种）")

    def on_before_scene_write(self, prompt_payload: list, beat_data: dict) -> list:
        """注入风格指令到 system prompt 位置。如果 style_reference 已注入，跳过。"""
        if self.context.get_shared("unified_style_injected"):
            return prompt_payload  # style_reference.py already handles this
        style_name = self.context.get_shared("style_config", {}).get("current", self.current_style)
        style = STYLE_DB.get(style_name, STYLE_DB[DEFAULT_STYLE])

        style_block = style["promptInjection"]

        if style.get("vocabulary"):
            style_block += f"\n首选词汇: {', '.join(style['vocabulary'])}"
        if style.get("avoidPatterns"):
            style_block += f"\n避免: {', '.join(style['avoidPatterns'])}"
        if style.get("dialogueStyle"):
            style_block += f"\n对话风格: {style['dialogueStyle']}"

        # 注入到最前面（作为 system prompt 的角色设定部分）
        prompt_payload.insert(0, f"[写作风格: {style_name}]\n{style_block}\n")
        return prompt_payload

    def set_style(self, style_name: str):
        """切换写作风格"""
        if style_name in STYLE_DB:
            self.current_style = style_name
            self.context.set_shared("style_config", {"current": style_name, "available": list(STYLE_DB.keys())})
            print(f"  [✓] 写作风格切换为: {style_name}")
        else:
            print(f"  [⚠️] 未知风格: {style_name}，可用: {list(STYLE_DB.keys())}")
