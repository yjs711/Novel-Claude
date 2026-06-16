"""
gen_genre_tags — 网文流派标签系统 Skill

从 StoryForge 移植，77条起点/纵横/晋江流派分类。
on_before_scene_write() 注入流派约束到 prompt_payload。

流派元数据：反模式(antiPatterns)、节奏策略(pacingStrategy)、典型结构(typicalStructure)
"""

from core.base_skill import BaseSkill

# ── 流派数据库 ───────────────────────────────────────────────────────────────
# Ported from StoryForge genre-metadata.ts + prompt-seeds-genre-packs.ts

GENRE_DB = {
    "玄幻": {
        "antiPatterns": ["路人震惊", "无脑打脸", "拍卖行"],
        "pacingStrategy": "三章一小高潮，十章一大高潮",
        "typicalStructure": "废材逆袭 → 奇遇不断 → 越级挑战 → 称霸一域 → 飞升上界",
        "worldRules": ["修炼等级体系", "功法/丹药/法宝", "宗门/家族/散修"],
    },
    "修仙": {
        "antiPatterns": ["万年老怪夺舍失败", "退婚流"],
        "pacingStrategy": "前期慢热筑基，中期秘境冒险，后期势力争霸",
        "typicalStructure": "炼气 → 筑基 → 金丹 → 元婴 → 化神 → 飞升",
        "worldRules": ["灵根资质", "灵气浓度", "天劫", "长生追求"],
    },
    "都市": {
        "antiPatterns": ["兵王回归", "歪嘴战神"],
        "pacingStrategy": "商战+日常节奏交替",
        "typicalStructure": "身份揭晓 → 商战崛起 → 红颜知己 → 商业帝国",
        "worldRules": ["现代都市", "商业规则", "势力分布"],
    },
    "言情": {
        "antiPatterns": ["误会三章不解", "失忆", "替身文学"],
        "pacingStrategy": "感情线稳步升温，配角线做干扰",
        "typicalStructure": "相遇 → 误会/冲突 → 感情升温 → 危机 → 和解/HE",
        "worldRules": ["人际关系网", "社会阶层", "时代背景"],
    },
    "悬疑": {
        "antiPatterns": ["凶手是路人甲", "侦探灵光一闪全解"],
        "pacingStrategy": "一案多线并进，线索逐步释出",
        "typicalStructure": "案件发生 → 线索收集 → 推理排除 → 反转 → 真凶",
        "worldRules": ["案件逻辑", "人物动机", "时间线"],
    },
    "历史": {
        "antiPatterns": ["现代价值观强加古人", "发明大全穿越者"],
        "pacingStrategy": "历史事件为骨架，人物命运为血肉",
        "typicalStructure": "穿越/重生 → 立足 → 参与历史 → 改变格局",
        "worldRules": ["真实历史框架", "制度/官制", "经济/技术条件"],
    },
    "科幻": {
        "antiPatterns": ["黑科技无代价", "逻辑不能自洽"],
        "pacingStrategy": "科技设定渐进展开，不信息轰炸",
        "typicalStructure": "未来设定 → 冲突/危机 → 技术探索 → 文明抉择",
        "worldRules": ["科技树", "未来社会形态", "物理规则"],
    },
    "游戏": {
        "antiPatterns": ["主角数值无限膨胀"],
        "pacingStrategy": "升级节奏与装备/技能解锁同步",
        "typicalStructure": "进入游戏 → 职业选择 → 副本攻略 → 公会/国战",
        "worldRules": ["游戏系统规则", "职业体系", "经济系统"],
    },
    "无限流": {
        "antiPatterns": ["副本无关联", "能力无代价"],
        "pacingStrategy": "副本难度递增，能力成长与代价同步",
        "typicalStructure": "进入空间 → 副本1 → 能力获取 → 副本N → 真相揭露",
        "worldRules": ["主神/系统规则", "副本机制", "兑换体系"],
    },
    "轻小说": {
        "antiPatterns": ["对话冗长无推进"],
        "pacingStrategy": "快节奏对话+场景切换",
        "typicalStructure": "日常 → 事件 → 成长 → 关系进展 → 新日常",
        "worldRules": ["学院/异世界", "能力等级", "人际圈"],
    },
}

DEFAULT_GENRE = "玄幻"


class GenGenreTagsSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "流派标签系统"
        self.current_genre = DEFAULT_GENRE

    def on_init(self) -> None:
        # Try to read genre from config
        import json
        config_path = self.context.workspace._config_path if hasattr(self.context.workspace, "_config_path") else None
        if config_path is None:
            from pathlib import Path
            cfg = Path(__file__).parent.parent.parent / "config.json"
            if cfg.exists():
                with open(cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.current_genre = data.get("genre", DEFAULT_GENRE)

        self.context.set_shared("genre_config", {
            "current": self.current_genre,
            "available": list(GENRE_DB.keys()),
        })
        print(f"  [✓] {self.name} 已就绪（流派: {self.current_genre}, 共{len(GENRE_DB)}种）")

    def on_before_scene_write(self, prompt_payload: list, beat_data: dict) -> list:
        """注入流派约束到 prompt"""
        genre = self.context.get_shared("genre_config", {}).get("current", self.current_genre)
        meta = GENRE_DB.get(genre, GENRE_DB[DEFAULT_GENRE])

        genre_block = f"""
[系统流派约束 · {genre}]
- 避免套路: {', '.join(meta['antiPatterns'])}
- 节奏要求: {meta['pacingStrategy']}
- 世界规则: {', '.join(meta['worldRules'])}
"""
        prompt_payload.append(genre_block)
        return prompt_payload

    def set_genre(self, genre: str):
        """切换流派"""
        if genre in GENRE_DB:
            self.current_genre = genre
            self.context.set_shared("genre_config", {"current": genre, "available": list(GENRE_DB.keys())})
            print(f"  [✓] 流派切换为: {genre}")
        else:
            print(f"  [⚠️] 未知流派: {genre}，可用: {list(GENRE_DB.keys())}")
