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
        "promptInjection": "你是金庸风格的武侠作家。长句铺陈，白描淡写，人物对话文白相间。武功描写虚实结合，重意境不重力道。",
        "vocabulary": ["内力", "轻功", "剑法", "门派", "江湖", "侠义", "恩怨"],
        "avoidPatterns": ["数值化战力", "游戏化升级"],
        "dialogueStyle": "文白相间，半文半白",
        "narrativeDistance": "中远距离，说书人口吻",
    },
    "古龙风格": {
        "promptInjection": "你是古龙风格的悬疑武侠作家。短句断行，留白暗示，对话机锋暗藏。环境氛围大于动作描写。",
        "vocabulary": ["寂寞", "天涯", "刀", "酒", "夜色", "杀手"],
        "avoidPatterns": ["长篇打斗描写", "过度解释动机"],
        "dialogueStyle": "短促机锋，四字为限",
        "narrativeDistance": "近距离跟随主角感官",
    },
    "网文爽文": {
        "promptInjection": "你是网文爽文风格的作家。快节奏，强爽感，主角每次出手都让读者解气。重在'爽'和'燃'。",
        "vocabulary": ["碾压", "打脸", "震撼", "突破", "逆袭"],
        "avoidPatterns": ["主角长期压抑", "实力增长不明显"],
        "dialogueStyle": "直接爽快，不拖泥带水",
        "narrativeDistance": "紧跟主角，代入感强",
    },
    "纯文学": {
        "promptInjection": "你是纯文学风格的作家。注重语言质地和人性深度。场景描写为心理服务。",
        "vocabulary": [],
        "avoidPatterns": ["套路化情节", "脸谱化角色", "过度戏剧化"],
        "dialogueStyle": "暗示多于明说",
        "narrativeDistance": "意识流，内心世界为主",
    },
    "轻小说": {
        "promptInjection": "你是轻小说风格的作家。轻松明快，人物对话为主，插画感场景描写。",
        "vocabulary": [],
        "avoidPatterns": ["沉重哲学思辨", "过度严肃"],
        "dialogueStyle": "活泼自然，个性鲜明",
        "narrativeDistance": "近距离第一人称",
    },
    "硬核科幻": {
        "promptInjection": "你是硬核科幻风格的作家。科学逻辑自洽，技术设定有真实物理/生物/计算机科学依据。",
        "vocabulary": ["熵", "奇点", "量子", "维度"],
        "avoidPatterns": ["科学原理凭空捏造", "技术万能论"],
        "dialogueStyle": "准确清晰，可含术语",
        "narrativeDistance": "第三人称有限视角",
    },
    "黑色幽默": {
        "promptInjection": "你是黑色幽默风格的作家。用荒诞和讽刺包裹严肃主题。",
        "vocabulary": [],
        "avoidPatterns": ["煽情", "说教"],
        "dialogueStyle": "反讽、双关、装傻",
        "narrativeDistance": "冷眼旁观的讲述者",
    },
    "暗黑哥特": {
        "promptInjection": "你是暗黑哥特风格的作家。阴冷氛围，颓废美，人性阴暗面的诗化表达。",
        "vocabulary": ["腐朽", "阴影", "诅咒", "鲜血", "月光"],
        "avoidPatterns": ["阳光结局", "道德说教"],
        "dialogueStyle": "咏叹调式，带诗性",
        "narrativeDistance": "沉溺式感官描写",
    },
    "现代极简": {
        "promptInjection": "你是极简主义风格的作家。少即是多——用最短的句子表达最丰富的意思。海明威式。",
        "vocabulary": [],
        "avoidPatterns": ["形容词堆砌", "冗余比喻"],
        "dialogueStyle": "省略引述动词，纯对白",
        "narrativeDistance": "冰山原则，省略大于呈现",
    },
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
        """注入风格指令到 system prompt 位置"""
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
