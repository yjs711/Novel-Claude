"""
wf_mo_shen_workflow — 三档工作流切换 Skill

从 Mo-Shen graph/setup.py 移植。
quick:  Planner → Outline Agent → Chapter Writer (3Agent)
standard: + Worldbuilder + Character Designer (5Agent)
deep: + Continuity Reviewer 重写循环 (7Agent)

在 on_init() 读取 config.json workflow_mode，影响 scene_writer 行为。
"""

import json
from pathlib import Path
from core.base_skill import BaseSkill

WORKFLOW_MODES = {
    "quick": {
        "agents": ["Planner", "OutlineAgent", "ChapterWriter"],
        "description": "快速模式 — 3 Agent，适合试写验证",
        "max_revision_rounds": 0,
    },
    "standard": {
        "agents": ["Planner", "Worldbuilder", "CharacterDesigner", "OutlineAgent", "ChapterWriter"],
        "description": "标准模式 — 5 Agent，包含世界构建和角色设计",
        "max_revision_rounds": 1,
    },
    "deep": {
        "agents": ["Planner", "Worldbuilder", "CharacterDesigner", "OutlineAgent", "ChapterWriter", "ContinuityReviewer"],
        "description": "深度模式 — 6 Agent + 重写循环，质量最高",
        "max_revision_rounds": 3,
    },
}

DEFAULT_MODE = "quick"


class WfMoShenWorkflowSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "三档工作流"
        self.current_mode = DEFAULT_MODE

    def on_init(self) -> None:
        # 从 config.json 读取
        cfg = Path(__file__).parent.parent.parent / "config.json"
        if cfg.exists():
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.current_mode = data.get("workflow", {}).get("mode", DEFAULT_MODE)

        mode_info = WORKFLOW_MODES.get(self.current_mode, WORKFLOW_MODES[DEFAULT_MODE])
        self.context.set_shared("workflow_mode", self.current_mode)
        self.context.set_shared("workflow_config", mode_info)
        print(f"  [✓] {self.name} 已就绪（模式: {self.current_mode} — {mode_info['description']}）")

    def on_volume_planning(self, outline_draft: dict) -> dict:
        """根据工作流模式调整大纲规划"""
        mode = self.context.get_shared("workflow_mode", DEFAULT_MODE)
        if mode == "quick":
            outline_draft["_skip_worldbuilding"] = True
            outline_draft["_skip_character_design"] = True
        elif mode == "standard":
            outline_draft["_skip_worldbuilding"] = False
            outline_draft["_skip_character_design"] = False
        elif mode == "deep":
            outline_draft["_skip_worldbuilding"] = False
            outline_draft["_skip_character_design"] = False
            outline_draft["_enable_revision_loop"] = True
            outline_draft["_max_revision_rounds"] = 3
        return outline_draft

    def set_mode(self, mode: str):
        if mode in WORKFLOW_MODES:
            self.current_mode = mode
            self.context.set_shared("workflow_mode", mode)
            self.context.set_shared("workflow_config", WORKFLOW_MODES[mode])
            print(f"  [✓] 工作流切换为: {mode}")
        else:
            print(f"  [⚠️] 未知模式: {mode}，可用: {list(WORKFLOW_MODES.keys())}")
