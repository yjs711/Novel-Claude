"""
mem_sedimentation — 记忆沉淀 Skill

每章生成后自动提取结构化信息，写回 StoryState，形成记忆闭环。

- 每章：轻量提取（角色状态/认知/伏笔/剧情/新信息）
- 每10章：深度提取（情绪走势/悬念质量/弧光评估/节奏/去AI味）

Design doc: docs/superpowers/specs/2026-06-18-memory-sedimentation-design.md
"""

from pathlib import Path
from typing import Optional, List

from core.base_skill import BaseSkill
from core.story_state import StoryState, save_story_state_sharded
from utils.sedimentation import (
    LightExtract, DeepExtract,
    run_light_extraction, run_deep_extraction,
    _is_duplicate_light,
)
from utils.llm_client import _get_client, resolve_flash_model


class MemSedimentationSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "记忆沉淀系统"

    def on_init(self) -> None:
        print(f"  [[OK]] {self.name} 已就绪（每章轻量提取 + 每10章深度提取）")

    def on_after_chapter_complete(self, chapter_id: int, full_text: str) -> None:
        """章节完成后执行沉淀提取"""
        if not full_text or len(full_text.strip()) < 100:
            print(f"  [[!]] {self.name}: 章节内容过短，跳过提取")
            return

        story_state: Optional[StoryState] = self.context.get_shared("story_state")
        if story_state is None:
            print(f"  [[!]] {self.name}: 未找到 story_state，跳过提取")
            return

        # ── LLM client ──
        try:
            from utils.llm_client import resolve_provider
            client = _get_client()
            flash_model = resolve_flash_model(resolve_provider())
        except Exception as e:
            print(f"  [[!]] {self.name}: LLM 客户端不可用: {e}")
            return

        def llm_call(prompt: str) -> str:
            """Thin wrapper for chat completion."""
            response = client.chat.completions.create(
                model=flash_model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Low temp for extraction accuracy
                max_tokens=2048,
            )
            return response.choices[0].message.content or ""

        # ── 1. Light extraction (every chapter) ──
        try:
            light = run_light_extraction(full_text, llm_call)
            if light is not None:
                self._apply_light(light, story_state, chapter_id)
                print(f"  [[OK]] {self.name}: 第{chapter_id}章轻量提取完成 "
                      f"(状态变更:{len(light.character_state_changes)}角色, "
                      f"认知:{sum(len(v) for v in light.character_knowledge_gained.values())}条, "
                      f"伏笔种:{len(light.foreshadowing_planted)}/收:{len(light.foreshadowing_resolved)}, "
                      f"剧情推进:{len(light.plot_advances)})")
        except Exception as e:
            print(f"  [[!]] {self.name}: 轻量提取异常(ch{chapter_id}): {e}")

        # ── 2. Deep extraction (every 10 chapters) ──
        if chapter_id % 10 == 0:
            try:
                story_context = self._build_story_context(story_state)
                chapter_context = self._build_chapter_context(story_state, chapter_id)
                deep = run_deep_extraction(full_text, story_context, chapter_context, llm_call)
                if deep is not None:
                    self._apply_deep(deep, story_state, chapter_id)
                    print(f"  [[OK]] {self.name}: 第{chapter_id}章深度提取完成 "
                          f"(情绪走势:{len(deep.emotional_arc_trend)}字, "
                          f"角色弧光:{len(deep.character_arc_evaluation)}个, "
                          f"AI痕迹:{len(deep.deai_concerns)}处)")
            except Exception as e:
                print(f"  [[!]] {self.name}: 深度提取异常(ch{chapter_id}): {e}")

        # ── 3. Persist ──
        try:
            base_path = Path(self.context.workspace.workspace_root) / ".novel" / "story_state.json"
            save_story_state_sharded(story_state, base_path)
        except Exception as e:
            print(f"  [[!]] {self.name}: 持久化失败: {e}")

    # ── apply helpers ──────────────────────────────────────────────────────

    def _apply_light(self, light: LightExtract, state: StoryState, chapter_id: int) -> None:
        """Write LightExtract data back to StoryState."""
        ch = state.chapters.get(chapter_id)
        if ch is None:
            return

        # Plot advances
        if light.plot_advances:
            existing = list(ch.plot_advances)
            for pa in light.plot_advances:
                if not _is_duplicate_light(pa, existing):
                    existing.append(pa)
            ch.plot_advances = existing

        # New information
        if light.new_information:
            existing = list(ch.new_information)
            for ni in light.new_information:
                if not _is_duplicate_light(ni, existing):
                    existing.append(ni)
            ch.new_information = existing

        # Foreshadowing planted
        for fp in light.foreshadowing_planted:
            text = fp.get("text", "") if isinstance(fp, dict) else str(fp)
            if text and not _is_duplicate_light(text, ch.foreshadowing_planted):
                ch.foreshadowing_planted.append(text)

        # Foreshadowing resolved
        for fr in light.foreshadowing_resolved:
            text = fr.get("text", "") if isinstance(fr, dict) else str(fr)
            if text and not _is_duplicate_light(text, ch.foreshadowing_resolved):
                ch.foreshadowing_resolved.append(text)

        # Character state changes
        for char_id, changes in light.character_state_changes.items():
            char = state.characters.get(char_id)
            if char is None:
                continue
            for field, value in changes.items():
                if hasattr(char, field) and value:
                    setattr(char, field, value)
            char.last_appearance_chapter = chapter_id

        # Character knowledge gained (epistemic state)
        for char_id, facts in light.character_knowledge_gained.items():
            char = state.characters.get(char_id)
            if char is None:
                continue
            existing_knowledge = set(char.knowledge or [])
            for fact in facts:
                if fact and fact not in existing_knowledge:
                    char.knowledge.append(fact)
                    existing_knowledge.add(fact)
            # Keep last 30 items to prevent unbounded growth
            if len(char.knowledge) > 30:
                char.knowledge = char.knowledge[-30:]

        # Foreshadowing advancements → write to PlotThread milestones
        for hook_id, adv in light.foreshadowing_advancements.items():
            thread = state.plot_threads.get(hook_id)
            if thread is None:
                continue
            is_real = adv.get("is_real", False)
            progress = adv.get("progress", "")
            if is_real and progress:
                thread.milestones.append({
                    "chapter": chapter_id,
                    "progress": progress,
                })
                thread.last_updated_chapter = chapter_id

    def _apply_deep(self, deep: DeepExtract, state: StoryState, chapter_id: int) -> None:
        """Write DeepExtract results to StoryState."""
        ch = state.chapters.get(chapter_id)
        if ch is None:
            return

        # Store deep analysis markers
        if not ch.quality_scores:
            ch.quality_scores = {}
        ch.quality_scores["emotional_arc_trend"] = 1.0
        ch.quality_scores["hook_quality"] = 1.0
        ch.quality_scores["pacing"] = 1.0

        # Store as chapter notes for future reference
        notes_parts = []
        if deep.emotional_arc_trend:
            notes_parts.append(f"[情绪走势] {deep.emotional_arc_trend}")
        if deep.hook_quality_assessment:
            notes_parts.append(f"[悬念评估] {deep.hook_quality_assessment}")
        if deep.pacing_diagnosis:
            notes_parts.append(f"[节奏诊断] {deep.pacing_diagnosis}")
        if notes_parts:
            ch.notes = (ch.notes or "") + "\n".join(notes_parts)

        # Character arc evaluation
        for char_id, eval_data in deep.character_arc_evaluation.items():
            char = state.characters.get(char_id)
            if char is None:
                continue
            stage = eval_data.get("stage", "")
            progress = eval_data.get("progress", 0)
            if stage:
                char.arc_stage = stage
            if isinstance(progress, (int, float)) and progress > 0:
                char.arc_progress = int(progress)

        # De-AI concerns → forward to shared_state for deai engine
        if deep.deai_concerns:
            existing = self.context.get_shared("deai_concerns", [])
            existing.extend(deep.deai_concerns)
            self.context.set_shared("deai_concerns", existing)

    def _build_story_context(self, state: StoryState) -> str:
        """Build a brief story context string for deep extraction."""
        parts = []
        if state.title:
            parts.append(f"书名: {state.title}")
        if state.genre:
            parts.append(f"题材: {state.genre}")
        active_threads = [t for t in state.plot_threads.values() if t.status == "active"]
        if active_threads:
            parts.append(f"活跃剧情线: {len(active_threads)}条")
        main_chars = [c for c in state.characters.values() if c.role in ("protagonist", "antagonist")]
        if main_chars:
            parts.append(f"主要角色: {len(main_chars)}个")
        return "; ".join(parts)

    def _build_chapter_context(self, state: StoryState, current_ch: int) -> str:
        """Summarize last 10 chapters for deep extraction context."""
        lines = []
        for offset in range(1, 11):
            ch_num = current_ch - offset
            if ch_num < 1:
                break
            ch = state.chapters.get(ch_num)
            if ch is None:
                continue
            parts = [f"第{ch_num}章 {ch.title}"]
            if ch.plot_advances:
                parts.append(f"剧情: {'; '.join(ch.plot_advances[:3])}")
            if ch.emotional_beats:
                parts.append(f"情绪: {' -> '.join(ch.emotional_beats[:3])}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)
