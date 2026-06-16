"""
det_continuity_engine — 确定性连续性检查 Skill

零 token 成本。每章生成后自动运行9项检查，结果写入 shared_state。
CLI 命令: python cli.py continuity [--chapter N]

Ported from: Novel-OS core/continuity_engine.py
"""

import os
from pathlib import Path
from typing import List, Optional

from core.base_skill import BaseSkill
from core.continuity_engine import (
    run_all, summarize, to_context_block, Finding
)
from core.story_state import StoryState


class DetContinuityEngineSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "确定性连续性引擎"

    def on_init(self) -> None:
        print(f"  [✓] {self.name} 已就绪（9项零token检查）")

    def on_post_chapter_continuity(self, chapter_id: int) -> None:
        """每章生成后运行所有检查，结果写入 shared_state"""
        story_state: Optional[StoryState] = self.context.get_shared("story_state")
        if story_state is None:
            print(f"  [⚠️] {self.name}: 未找到 story_state，跳过检查")
            return

        # Get project path from workspace
        project_path = Path(self.context.workspace.workspace_root) if hasattr(self.context.workspace, "workspace_root") else Path.cwd()

        findings = run_all(story_state, project_path, as_of_chapter=chapter_id)

        # Store results for other skills / CLI to read
        self.context.set_shared("continuity_findings", findings)
        self.context.set_shared("continuity_summary", summarize(findings))
        self.context.set_shared("continuity_context_block", to_context_block(findings))

        # Print summary
        print()
        print(summarize(findings))
        print()

    def run_check(self, story_state: StoryState, chapter_id: int = None, project_path: Path = None) -> List[Finding]:
        """Public API — run checks manually (called from CLI)."""
        pp = project_path or Path(self.context.workspace.workspace_root) if hasattr(self.context.workspace, "workspace_root") else Path.cwd()
        return run_all(story_state, pp, as_of_chapter=chapter_id)
