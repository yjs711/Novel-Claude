"""
det_story_state_crud — StoryState 持久化管理 Skill

负责加载、保存、更新 StoryState JSON 文件。
自动与 Novel-Claude 现有 settings/ 目录（core_blueprint.json等）同步。

on_init: 从 .novel_{name}/story_state.json 加载（不存在则创建）
on_after_scene_write: 更新章节状态并保存
"""

import json
from pathlib import Path
from datetime import datetime

from core.base_skill import BaseSkill
from core.story_state import (
    StoryState, ChapterState, Character,
    save_story_state, load_story_state,
    save_story_state_sharded, load_story_state_sharded
)
import json


class DetStoryStateCrudSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "StoryState 持久化管理"
        self._state: StoryState = None
        self._state_path: Path = None

    def on_init(self) -> None:
        novel_dir = Path(self.context.workspace.NOVEL_DIR) if hasattr(self.context.workspace, "NOVEL_DIR") else Path(".novel")
        self._state_path = novel_dir / "story_state.json"

        # Check for sharded mode in config
        self._use_sharded = False
        cfg_path = Path(__file__).parent.parent.parent / "config.json"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self._use_sharded = cfg.get("performance", {}).get("story_state_shard_by_volume", False)

        # Load (sharded or monolithic)
        if self._use_sharded:
            self._state = load_story_state_sharded(self._state_path)
        else:
            self._state = load_story_state(self._state_path)

        if not self._state.title:
            self._sync_from_settings()
        self._state.log_action("session_start")

        self.context.set_shared("story_state", self._state)
        mode = "分片" if self._use_sharded else "整体"
        print(f"  [✓] {self.name} 已就绪（{mode}存储, {len(self._state.characters)}角色, {len(self._state.plot_threads)}线, {len(self._state.chapters)}章）")

    def _sync_from_settings(self):
        """从 Novel-Claude settings/ 同步角色到 StoryState"""
        settings = Path(self.context.workspace.SETTINGS_DIR) if hasattr(self.context.workspace, "SETTINGS_DIR") else Path(".novel/settings")
        blueprint_path = settings / "core_blueprint.json"
        if not blueprint_path.exists():
            return

        with open(blueprint_path, "r", encoding="utf-8") as f:
            blueprint = json.load(f)

        # Extract characters from blueprint
        char_entries = blueprint.get("characters", [])
        for entry in char_entries:
            char_id = entry.get("name", f"char_{len(self._state.characters)}")
            # normalize id
            char_key = char_id.strip().lower().replace(" ", "_")
            if char_key not in self._state.characters:
                self._state.characters[char_key] = Character(
                    id=char_key,
                    full_name=char_id.strip(),
                    role=entry.get("type", "supporting"),
                    physical_description=entry.get("description", ""),
                    notes=json.dumps(entry, ensure_ascii=False) if isinstance(entry, dict) else "",
                )

        self._state.log_action("synced_from_settings", {"entries": len(char_entries)})

    def on_after_scene_write(self, beat_data: dict, raw_text: str) -> None:
        """每章生成后更新章节状态"""
        chapter_id = beat_data.get("chapter_id") or self.context.current_chapter_id
        if chapter_id not in self._state.chapters:
            self._state.chapters[chapter_id] = ChapterState(
                number=chapter_id,
                status="drafted",
                word_count=len(raw_text),
                last_modified=datetime.now().isoformat(),
            )
        else:
            ch = self._state.chapters[chapter_id]
            ch.status = "drafted"
            ch.word_count = len(raw_text)
            ch.last_modified = datetime.now().isoformat()

        self._state.log_action("chapter_drafted", {"chapter": chapter_id, "word_count": len(raw_text)})
        self._save()

    def _save(self):
        if self._state_path:
            if self._use_sharded:
                save_story_state_sharded(self._state, self._state_path)
            else:
                save_story_state(self._state, self._state_path)

    def get_state(self) -> StoryState:
        return self._state

    def add_character(self, char: Character):
        self._state.characters[char.id] = char
        self._state.log_action("character_added", {"id": char.id, "name": char.full_name})
        self._save()

    def add_plot_thread(self, thread: "PlotThread"):
        from core.story_state import PlotThread
        self._state.plot_threads[thread.id] = thread
        self._state.log_action("plot_thread_added", {"id": thread.id, "name": thread.name})
        self._save()

    def update_chapter_status(self, chapter_id: int, status: str):
        if chapter_id in self._state.chapters:
            self._state.chapters[chapter_id].status = status
        else:
            self._state.chapters[chapter_id] = ChapterState(number=chapter_id, status=status)
        self._state.log_action("chapter_status_update", {"chapter": chapter_id, "status": status})
        self._save()
