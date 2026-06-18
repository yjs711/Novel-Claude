"""
mem_working_memory — 三层记忆管理 Skill (256K优化版)

L1 Working: 最近3章即时上下文（256K下可放全文）
L2 Episodic: 过去50章情节摘要（从10→50）
L3 Semantic: 世界观规则 + 角色关系 + 剧情线状态
"""

from core.base_skill import BaseSkill


class MemWorkingMemorySkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "三层记忆系统"
        self.l2_range = 50    # 256K: 10→50章
        self.l1_full_chapters = 3   # 最近3章全文
        self.l1_limit = 8000  # Working: 8000字

    def on_init(self) -> None:
        print(f"  [✓] {self.name} 已就绪 (256K优化: L1=3章全文, L2=50章, L3=世界观+剧情)")

    def on_before_scene_write(self, prompt_payload: list, beat_data: dict) -> list:
        chapter_id = beat_data.get("chapter_id") or self.context.current_chapter_id
        story_state = self.context.get_shared("story_state")
        memory_block = []

        # L1: Working Memory — 最近3章全文
        if story_state and chapter_id > 1:
            l1 = self._build_working_memory(story_state, chapter_id)
            if l1:
                memory_block.append("[L1 工作记忆 · 最近3章]\n" + l1)

        # L2: Episodic Memory — 过去50章摘要
        if story_state:
            l2 = self._build_episodic_memory(story_state, chapter_id)
            if l2:
                memory_block.append("[L2 情景记忆 · 50章范围]\n" + l2)

        # L3: Semantic Memory — 世界观 + 角色 + 剧情线
        if story_state:
            l3 = self._build_semantic_memory(story_state)
            if l3:
                memory_block.append("[L3 语义记忆 · 世界观+剧情线]\n" + l3)

        if memory_block:
            prompt_payload.append("\n".join(memory_block))
        return prompt_payload

    def _build_working_memory(self, story_state, current_ch: int) -> str:
        """L1: 最近3章的即时状态"""
        parts = []
        for offset in range(1, self.l1_full_chapters + 1):
            ch_num = current_ch - offset
            if ch_num < 1: break
            ch = story_state.chapters.get(ch_num)
            if not ch: continue

            parts.append(f"\n--- 第{ch_num}章 {ch.title} ---")
            if ch.location:
                parts.append(f"场景: {ch.location}")
            if ch.pov_character:
                parts.append(f"视角: {ch.pov_character}")
            if ch.plot_advances:
                parts.append(f"推进: {'; '.join(ch.plot_advances)}")
            if ch.emotional_beats:
                parts.append(f"情绪: {' → '.join(ch.emotional_beats)}")
            if ch.hooks_end:
                parts.append(f"章末悬念: {'; '.join(ch.hooks_end[-3:])}")
            if ch.foreshadowing_planted:
                parts.append(f"新埋伏笔: {'; '.join(ch.foreshadowing_planted)}")
            if ch.foreshadowing_resolved:
                parts.append(f"回收伏笔: {'; '.join(ch.foreshadowing_resolved)}")

        return "\n".join(parts) if parts else ""

    def _build_episodic_memory(self, story_state, current_ch: int) -> str:
        """L2: 过去50章情节摘要"""
        lines = []
        for offset in range(self.l1_full_chapters + 1, self.l2_range + 1):
            ch_num = current_ch - offset
            if ch_num < 1: break
            ch = story_state.chapters.get(ch_num)
            if not ch: continue

            parts = []
            if ch.plot_advances:
                parts.append(f"剧情: {', '.join(ch.plot_advances[:3])}")
            if ch.new_information:
                parts.append(f"新信息: {', '.join(ch.new_information[:2])}")
            if ch.emotional_beats:
                parts.append(f"情绪: {' → '.join(ch.emotional_beats[:2])}")
            if ch.foreshadowing_planted:
                parts.append(f"伏笔: {', '.join(ch.foreshadowing_planted[:2])}")

            # 越近的章越详细
            if offset <= 10:
                # 详细摘要
                line = f"第{ch_num}章 {ch.title}: {'; '.join(parts)}"
            elif offset <= 30:
                # 中等摘要
                line = f"第{ch_num}章 {ch.title}: {', '.join(ch.plot_advances[:2] or ['略'])}"
            else:
                # 简要
                line = f"第{ch_num}章 {ch.title}"

            lines.append(line)

        return "\n".join(lines) if lines else ""

    def _build_semantic_memory(self, story_state) -> str:
        """L3: 世界观 + 角色关系 + 剧情线"""
        parts = []

        if story_state.genre:
            parts.append(f"题材: {story_state.genre}")
        if story_state.title:
            parts.append(f"书名: {story_state.title}")

        # 风格
        sp = story_state.style_profile
        if sp.name and sp.name != "default":
            parts.append(f"风格: {sp.name} | 视角: {sp.point_of_view} | 时态: {sp.tense} | 语调: {sp.tone}")

        # 主要角色
        chars = story_state.characters.values()
        if chars:
            main = [c for c in chars if c.role in ("protagonist", "antagonist")]
            supp = [c for c in chars if c.role == "supporting"]
            parts.append("\n角色:")
            for c in main:
                parts.append(f"  ★ {c.full_name} ({c.role})")
                parts.append(f"    目标: {c.external_goal or '?'} | 渴望: {c.internal_desire or '?'}")
                parts.append(f"    恐惧: {c.fear or '?'} | 弱点: {c.weakness or '?'}")
                parts.append(f"    弧光: {c.arc_stage}({c.arc_progress}%) | 位置: {c.current_location or '?'}")
            if supp:
                names = ", ".join(f"{c.full_name}({c.role})" for c in supp[:8])
                parts.append(f"  配角: {names}")

            # ── 认知状态注入（Epistemic State） ──
            # 防止角色"重新发现"已知信息
            all_chars = list(main) + list(supp)
            knowledge_lines = []
            for c in all_chars:
                if c.knowledge:
                    known = c.knowledge[-10:]  # Last 10 known facts
                    knowledge_lines.append(f"  {c.full_name}已知: {'; '.join(known)}")
            if knowledge_lines:
                parts.append("\n[角色已知信息 — 避免重复发现]\n" + "\n".join(knowledge_lines))

        # 活跃剧情线
        active = [t for t in story_state.plot_threads.values() if t.status == "active"]
        if active:
            parts.append("\n活跃剧情线:")
            for t in active[:8]:
                parts.append(f"  ▸ {t.name} (P{t.priority}): {t.description[:60]}")
                if t.target_resolution_chapter:
                    parts.append(f"    收束目标: 第{t.target_resolution_chapter}章")

        return "\n".join(parts) if parts else ""
