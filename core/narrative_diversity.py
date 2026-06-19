"""
Novel-Claude Fusion — 叙事多样性引擎

基于 StoryScope 2026 (Russell et al., 61,608篇小说, 304特征) 的已验证结构标记。
仅做结构同质化检测+多样性评分，不注入未验证的原型提示。

来源: StoryScope (arXiv 2604.03136) — 仅叙事结构特征即可93.2%识别AI写作。
30个特征即可达到84.8%识别率。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import re


@dataclass
class ChapterFingerprint:
    """章节结构指纹 — 基于StoryScope 2026已验证的7个结构标记"""
    chapter_id: int
    protagonist_resolves: bool       # 章末以主角行动解决问题
    explicit_theme: bool             # 叙述者/角色直接陈述主题
    philosophical_dialogue: bool     # 对话含抽象/哲学讨论
    single_pov: bool                 # 全章仅一个视角
    linear_time: bool                # 无闪回、无时间操作
    tidy_ending: bool                # 章末收束干净
    subplot_advance: bool            # 至少推进一条支线


def fingerprint_chapter(text: str, chapter_id: int) -> ChapterFingerprint:
    """快速结构指纹提取（零token，纯正则）"""
    last_500 = text[-500:] if len(text) > 500 else text
    last_200 = text[-200:] if len(text) > 200 else text

    protagonist_resolves = bool(re.search(
        r'(他|她|林\w|萧\w|叶\w|楚\w|苏\w|秦\w)'
        r'(终于|最终|成功|完成|解决|打败|突破|达到|踏入)',
        last_500,
    ))
    explicit_theme = bool(re.search(
        r'(让|令|使).{2,8}(明白|意识到|懂得|领悟).{0,20}(道理|真意|含义|真谛)',
        text,
    ))
    philosophical_dialogue = bool(re.search(
        r'[""「].{20,}(人生|命运|世间|这世上|力量|权利|正义|真理|自由|爱).{20,}[""」]',
        text,
    ))
    pov_markers = len(re.findall(r'(视角切换|另一边|与此同时.{0,5}在|场景转换)', text))
    single_pov = pov_markers <= 1
    flashback_markers = len(re.findall(
        r'(回想|回忆|当年|曾经|那是.{2,5}年前|那时候|从前)', text,
    ))
    linear_time = flashback_markers <= 1
    tidy_ending = bool(re.search(
        r'(就这样|至此|从此|于是).{0,20}(。|！|？|\n)', last_200,
    ))
    subplot_advance = len(re.findall(
        r'(与此同时|另一边|与此同|镜头转|场景切换)', text,
    )) >= 1

    return ChapterFingerprint(
        chapter_id=chapter_id,
        protagonist_resolves=protagonist_resolves,
        explicit_theme=explicit_theme,
        philosophical_dialogue=philosophical_dialogue,
        single_pov=single_pov,
        linear_time=linear_time,
        tidy_ending=tidy_ending,
        subplot_advance=subplot_advance,
    )


def diversity_score(fingerprints: List[ChapterFingerprint]) -> Tuple[int, List[str]]:
    """
    叙事多样性评分 (0-100)。高分=多样，低分=同质化(AI典型模式)。
    数据来源: StoryScope 2026 (Russell et al., 61,608篇)。
    扣分权重: 按AI-vs-人类差距大小比例分配。
    """
    if len(fingerprints) < 2:
        return 100, ["需要更多章节才能评估多样性"]

    issues = []
    score = 100

    # StoryScope: 69% AI vs 46% 人类 — 差距23百分点 → 权重-20
    if all(f.protagonist_resolves for f in fingerprints):
        score -= 20
        issues.append("全部章节均为'主角驱动解决'模式 (StoryScope: 69% AI vs 46% 人类)")

    # StoryScope: 77% AI vs 52% 人类 — 差距25百分点 → 权重-15
    if sum(1 for f in fingerprints if f.explicit_theme) > len(fingerprints) * 0.5:
        score -= 15
        issues.append("多数章节出现'主题直接陈述' (StoryScope: 77% AI vs 52% 人类)")

    # StoryScope: 59% AI vs 34% 人类 — 差距25百分点 → 权重-10 (发生频率较低)
    if all(f.philosophical_dialogue for f in fingerprints):
        score -= 10
        issues.append("全部章节含哲学讨论对话 (StoryScope: 59% AI vs 34% 人类)")

    # StoryScope: AI压倒性使用单一视角、线性时间、整洁收束
    if all(f.single_pov for f in fingerprints):
        score -= 10
        issues.append("全部单一视角，缺乏多视角切换")

    if all(f.linear_time for f in fingerprints):
        score -= 10
        issues.append("全部线性时间线，缺乏闪回/时间操作 (StoryScope: AI压倒性线性)")

    if all(f.tidy_ending for f in fingerprints):
        score -= 10
        issues.append("全部章末整洁收束 (StoryScope: AI默认整洁收束)")

    # StoryScope: 79% AI故事缺乏支线
    if not any(f.subplot_advance for f in fingerprints):
        score -= 15
        issues.append("无支线推进 (StoryScope: 79% AI故事缺乏支线)")

    return max(score, 10), issues
