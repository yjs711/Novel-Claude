"""
情感自动分析器 — 根据场景/大纲文本自动判断情感基调
基于 Aether Weaver (2025) + Cowen-Keltner 情感理论

用法:
    analyzer = EmotionAnalyzer()
    emotion = analyzer.detect(outline_text)
    # 返回: 'sorrow' | 'anger' | 'fear' | 'joy' | ...
"""
from __future__ import annotations
import re
from typing import Optional

class EmotionAnalyzer:
    """关键词+规则 情感分类器，用于运行时自动判断。P2可接LLM做精确分类。"""

    EMOTIONS = {
        "sorrow": {
            "keywords": ["死","离别","失去","孤独","寂寞","悲伤","哭泣","眼泪","怀念","遗憾","告别","永远","走了","不再","最后","坟","埋","殇","苦","悲","泪"],
            "patterns": ["永远的","再也","最后一次","回不来","阴阳两隔"],
            "weight": 1.0,
        },
        "anger": {
            "keywords": ["杀","灭","毁","怒","恨","仇","报复","血","屠","诛","碎","杀意","狞","嘶吼","咆哮","砍","斩","烧"],
            "patterns": ["不得好死","血债血偿","不共戴天","恨之入骨"],
            "weight": 1.0,
        },
        "fear": {
            "keywords": ["恐怖","诡异","阴森","黑暗","毛骨悚然","颤抖","冷汗","恐惧","害怕","躲","藏","逃","鬼","尸","血淋淋","尖叫","惊叫"],
            "patterns": ["不敢回头","脊背发凉","不寒而栗"],
            "weight": 1.0,
        },
        "joy": {
            "keywords": ["笑","喜","欢呼","庆祝","胜利","成功","突破","升","晋级","突破","喜悦","欢","畅快","兴高采烈"],
            "patterns": ["不负所望","大获全胜","终于成功"],
            "weight": 1.0,
        },
        "love": {
            "keywords": ["爱","情","思念","温柔","拥抱","吻","心动","暖","依偎","牵手","心动","表白","相拥","深情","眷恋"],
            "patterns": ["默默守护","不离不弃","相视一笑","牵肠挂肚"],
            "weight": 1.0,
        },
        "loneliness": {
            "keywords": ["独","一人","空","寂静","冷清","迷惘","彷徨","徘徊","孑然","形单影只","独自","孤","寂寥"],
            "patterns": ["一个人走","无人知晓","独自面对","茫茫人海"],
            "weight": 1.0,
        },
        "warmth": {
            "keywords": ["温暖","治愈","阳光","春风","花开","鸟鸣","美好","幸福","安逸","平静","安稳","平淡","馨","暖"],
            "patterns": ["岁月静好","向阳而生","春暖花开"],
            "weight": 1.0,
        },
        "humor": {
            "keywords": ["搞笑","吐槽","滑稽","荒诞","搞笑","幽默","调侃","逗","耍","整蛊","绝了","好家伙"],
            "patterns": ["哭笑不得","一脸懵逼","社死现场"],
            "weight": 1.0,
        },
        "awe": {
            "keywords": ["磅礴","浩荡","无边","宇宙","星辰","天","浩瀚","恢弘","震撼","雄伟","壮观","滔天","遮天","灭世","神","圣","古","洪荒","太古"],
            "patterns": ["天地为之变色","日月无光","洪荒之力"],
            "weight": 1.0,
        },
        "despair": {
            "keywords": ["绝望","崩溃","万念俱灰","心死","断念","颓丧","放弃","认命","碎","灭","尽","绝","无一幸免","黑"],
            "patterns": ["一切结束","再也没有希望","心如死灰"],
            "weight": 1.0,
        },
        "tension": {
            "keywords": ["紧迫","逼近","倒数","最后一刻","千钧一发","命悬一线","危急","火急","箭在弦上","逼近","逼","追","赶","抢","冲"],
            "patterns": ["争分夺秒","迫在眉睫","起死回生"],
            "weight": 1.0,
        },
    }

    @classmethod
    def detect(cls, text: str, chapter_num: int = 1) -> Optional[str]:
        """
        关键词+规则 快速分类。
        返回: emotion key 或 None (无法判断时返回None，后端使用默认)
        """
        if not text or len(text) < 5:
            return None

        scores = {}
        text_lower = text

        for emo_key, config in cls.EMOTIONS.items():
            score = 0.0
            # 关键词匹配
            for kw in config["keywords"]:
                count = text_lower.count(kw)
                if count > 0:
                    score += count * config["weight"]
            # 模式匹配（加权更高）
            for pat in config["patterns"]:
                if pat in text_lower:
                    score += 3.0
            scores[emo_key] = score

        # 返回最高分情感
        max_score = max(scores.values()) if scores else 0
        if max_score < 2:
            # 分数太低，无法判断
            return None

        # 如果多个情感得分接近，返回第一个高分
        best = max(scores, key=scores.get)
        return best

    @classmethod
    def detect_from_outline(cls, outline_text: str, chapter_num: int = 1) -> Optional[str]:
        """从大纲/细纲文本中检测情感基调"""
        return cls.detect(outline_text, chapter_num)

    @classmethod
    def format_emotion_hint(cls, emotion: str) -> str:
        """生成情感提示文本（注入 prompt 前使用）"""
        labels = {
            "sorrow": "悲伤/离别",
            "anger": "愤怒/复仇",
            "fear": "恐惧/紧张",
            "joy": "喜悦/胜利",
            "love": "爱/心动",
            "loneliness": "孤独/迷茫",
            "warmth": "温暖/治愈",
            "humor": "幽默/反讽",
            "awe": "震撼/敬畏",
            "despair": "绝望/崩溃",
            "tension": "紧张/焦虑",
        }
        label = labels.get(emotion, emotion)
        return f"\n\n**本章情感基调（由大纲自动检测）：{label}**\n请在写作中把握此情感基调，但不要直接写出情感标签词。"
