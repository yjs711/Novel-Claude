"""
wf_auto_director — AI 自动导演 Skill

从 AI-Novel-Writing-Assistant 移植。
从一句灵感 → 世界观 → 角色 → 卷纲 → 拆章 → 写作 全链路。

on_init() 注册导演工具，on_volume_planning() 注入导演决策。
"""

import json
from pathlib import Path
from typing import List, Optional
from core.base_skill import BaseSkill


class WfAutoDirectorSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "AI自动导演"
        self.pipeline_stages = [
            "灵感捕获",
            "一句话梗概",
            "世界观构建",
            "角色设计",
            "分卷规划",
            "拆章到场景",
            "逐章写作",
        ]
        self.current_stage = 0

    def on_init(self) -> None:
        self.context.set_shared("director_pipeline", {
            "stages": self.pipeline_stages,
            "current": self.current_stage,
            "completed": [],
        })
        print(f"  [✓] {self.name} 已就绪（{len(self.pipeline_stages)}段全链路）")

    def on_volume_planning(self, outline_draft: dict) -> dict:
        """导演介入卷纲规划"""
        # 自动评估是否需要调整
        notes = self._director_notes(outline_draft)
        if notes:
            if "_director_notes" not in outline_draft:
                outline_draft["_director_notes"] = []
            outline_draft["_director_notes"].extend(notes)

        self.current_stage = 4  # 分卷规划阶段
        self._update_progress()
        return outline_draft

    def on_before_scene_write(self, prompt_payload: list, beat_data: dict) -> list:
        """导演在每章写作前注入指导"""
        # 注入当前进度
        progress = self._progress_summary()
        prompt_payload.append(f"\n[导演 · 创作进度]\n{progress}\n")

        # 注入节奏检查
        pacing_note = self._pacing_reminder(beat_data)
        if pacing_note:
            prompt_payload.append(pacing_note)

        return prompt_payload

    def _director_notes(self, outline: dict) -> list:
        """根据大纲给出导演建议"""
        notes = []
        vols = outline.get("volumes", {})
        total_chapters = sum(len(v.get("chapters", [])) for v in vols.values())

        if total_chapters < 30:
            notes.append("⚠️ 总章节数偏少（<30章），建议扩展中间卷的章节数")
        if total_chapters > 200:
            notes.append("⚠️ 总章节数偏多（>200章），建议合并部分支线章节")

        # 检查节奏分布
        chapter_counts = [len(v.get("chapters", [])) for v in vols.values()]
        if chapter_counts:
            avg = sum(chapter_counts) / len(chapter_counts)
            for i, count in enumerate(chapter_counts, 1):
                if count > avg * 2:
                    notes.append(f"📊 第{i}卷章节数({count})远超平均({avg:.0f})，考虑拆分")

        return notes

    def _pacing_reminder(self, beat_data: dict) -> str:
        """根据节拍数据给节奏提醒"""
        ch_id = beat_data.get("chapter_id", 0)
        vol_id = beat_data.get("volume_id", 1)

        # 每卷开头3章：建立阶段
        # 每卷最后3章：高潮阶段
        total_in_vol = beat_data.get("total_in_volume", 10)
        pos_in_vol = beat_data.get("position_in_volume", 1)

        if pos_in_vol <= 2:
            return "[导演] 📖 卷首建立阶段：铺垫世界观和角色动机，节奏可稍缓"
        elif pos_in_vol >= total_in_vol - 2:
            return "[导演] 🔥 卷末高潮阶段：冲突集中爆发，节奏加快，每章至少一个爽点"
        elif total_in_vol // 2 - 1 <= pos_in_vol <= total_in_vol // 2 + 1:
            return "[导演] 🎯 卷中转折阶段：引入新变数或信息，打破现有平衡"
        return ""

    def _progress_summary(self) -> str:
        pipeline = self.context.get_shared("director_pipeline", {})
        stages = pipeline.get("stages", self.pipeline_stages)
        current = pipeline.get("current", self.current_stage)
        completed = pipeline.get("completed", [])

        lines = []
        for i, stage in enumerate(stages):
            if i < current:
                lines.append(f"  ✅ {stage}")
            elif i == current:
                lines.append(f"  🔄 {stage} ← 当前")
            else:
                lines.append(f"  ⬜ {stage}")
        return "\n".join(lines)

    def _update_progress(self):
        pipeline = self.context.get_shared("director_pipeline", {})
        pipeline["current"] = self.current_stage
        self.context.set_shared("director_pipeline", pipeline)

    def advance_stage(self):
        """推进到下一阶段"""
        if self.current_stage < len(self.pipeline_stages) - 1:
            self.current_stage += 1
            self._update_progress()
            print(f"  [导演] 进入阶段: {self.pipeline_stages[self.current_stage]}")

    def get_llm_tools(self) -> list:
        """注册导演工具"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "director_assess",
                    "description": "导演评估当前故事状态并给出调整建议",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "assessment": {"type": "string", "description": "当前故事状态评估"},
                            "issues": {"type": "array", "items": {"type": "string"}, "description": "发现的问题"},
                            "suggestions": {"type": "array", "items": {"type": "string"}, "description": "调整建议"},
                        },
                        "required": ["assessment"],
                    },
                },
            }
        ]

    def execute_tool(self, tool_name: str, kwargs: dict) -> str:
        if tool_name == "director_assess":
            assessment = kwargs.get("assessment", "")
            issues = kwargs.get("issues", [])
            suggestions = kwargs.get("suggestions", [])
            result = f"[导演评估] {assessment}"
            if issues:
                result += f"\n问题: {', '.join(issues)}"
            if suggestions:
                result += f"\n建议: {', '.join(suggestions)}"
            return result
        return "未知工具"
