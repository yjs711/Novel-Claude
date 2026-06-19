"""
Scene Writer - Chapter content generation with @DSL context injection

Following NovelForge's approach:
1. Generate chapter content from chapter_outline (not beats directly)
2. Use @DSL to inject: world_setting, organization cards, scene cards,
   character cards, previous chapter content, writing guide
3. Add continuation support with word count control
4. Progressive saving and state machine management
"""

import os
import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from utils.config import SETTINGS_DIR, VOLUMES_DIR, MANUSCRIPTS_DIR
from utils.config_loader import get_config
from utils.llm_client import ProgressiveWriter, generate_stream
from core.context_assembler import assemble_context, get_assembler
from core.event_bus import event_bus
from utils.logger import get_logger, log_step

logger = get_logger(__name__)
from utils.chapter_state import get_state_manager, STATE_PENDING, STATE_GENERATING, STATE_COMPLETED, STATE_FAILED


# ============================================================================
# Core Functions
# ============================================================================

def load_chapter_outline(volume_id: int, chapter_id: int) -> Optional[dict]:
    """Load chapter outline from vol_NN_chapters/ch_XXX_outline.json"""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_chapters" / f"ch_{chapter_id:03d}_outline.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_volume_outline(volume_id: int) -> Optional[dict]:
    """Load volume outline from volumes/vol_XX_outline.json"""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_outline.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_previous_chapter(volume_id: int, chapter_id: int) -> Optional[str]:
    """Load previous chapter content for context. 256K: load more."""
    if chapter_id <= 1:
        return None
    prev_chars = get_config("writing.previous_chapter_chars", 4000)
    path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id-1:03d}_final.md"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            return content[-prev_chars:]
    return None


def load_history_chapters(volume_id: int, chapter_id: int, count: int = None) -> str:
    """Load multiple previous chapters for deeper context. 256K: default 15 chapters."""
    if count is None:
        count = get_config("writing.history_chapters_count", 15)

    if chapter_id <= count:
        count = chapter_id - 1
    if count <= 0:
        return ""

    history = []
    for i in range(1, count + 1):
        prev_id = chapter_id - i
        if prev_id < 1:
            break
        path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{prev_id:03d}_final.md"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                # Get key plot points from each chapter (first 200 and last 500 chars)
                content = f.read()
                first_part = content[:200] if len(content) > 200 else content
                last_part = content[-500:] if len(content) > 500 else content
                history.append(f"=== 第{prev_id}章梗概 ===\n{first_part}\n...（中间内容）...\n{last_part}")

    return "\n\n".join(history)


def load_next_chapter_outline(volume_id: int, chapter_id: int) -> Optional[dict]:
    """Load next chapter outline for continuity check."""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_chapters" / f"ch_{chapter_id+1:03d}_outline.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_entity_cards(entity_names: List[str]) -> Dict[str, List[dict]]:
    """Load entity cards (character, scene, organization) matching the given names."""
    result = {
        "characters": [],
        "scenes": [],
        "organizations": []
    }

    blueprint_path = Path(SETTINGS_DIR) / "core_blueprint.json"
    if not blueprint_path.exists():
        return result

    with open(blueprint_path, 'r', encoding='utf-8') as f:
        blueprint = json.load(f)

    content = blueprint.get("content", blueprint)
    entity_name_set = set(entity_names)

    # Filter characters
    for char in content.get("character_cards", []):
        if char.get("name") in entity_name_set:
            result["characters"].append(char)

    # Filter scenes
    for scene in content.get("scene_cards", []):
        if scene.get("name") in entity_name_set:
            result["scenes"].append(scene)

    # Filter organizations
    for org in content.get("organization_cards", []):
        if org.get("name") in entity_name_set:
            result["organizations"].append(org)

    return result


def load_world_setting() -> dict:
    """Load world setting for context."""
    path = Path(SETTINGS_DIR) / "world_setting.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def load_writing_guide(volume_id: int) -> Optional[str]:
    """Load writing guide for the volume if exists."""
    path = Path(VOLUMES_DIR) / f"vol_{volume_id:02d}_writing_guide.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("content", {}).get("content", "")
    return None


def _load_structured_outline_chapter(chapter_id: int) -> dict:
    """Load per-chapter structured outline detail (scenes, beats, hooks) from 大纲.json."""
    try:
        config = _load_config()
        novel_name = config.get("workspace", {}).get("novel_name", "")
        from pathlib import Path
        outline_path = Path(f".novel_{novel_name}" if novel_name else ".novel") / "大纲.json"
        if not outline_path.exists():
            return {}
        with open(outline_path, 'r', encoding='utf-8') as f:
            outline = json.load(f)
        for vol in outline.get("volumes", []):
            for ch in vol.get("chapters_list", []):
                if ch.get("number") == chapter_id:
                    return ch
    except Exception:
        pass
    return {}


def _load_foreshadowing_context(chapter_id: int) -> str:
    """Load foreshadowing data relevant to this chapter."""
    try:
        config = _load_config()
        novel_name = config.get("workspace", {}).get("novel_name", "")
        from pathlib import Path
        fs_path = Path(f".novel_{novel_name}" if novel_name else ".novel") / "伏笔.json"
        if not fs_path.exists():
            return ""
        with open(fs_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        items = data.get("items", [])
        parts = []
        planted_here = [i for i in items if i.get("planted_in") == chapter_id and i.get("status") != "resolved"]
        needs_resolve = [i for i in items if i.get("status") == "planted" and i.get("target_resolve", 9999) <= chapter_id]
        if planted_here:
            parts.append("本章需埋入的伏笔: " + ", ".join(i["description"] for i in planted_here))
        if needs_resolve:
            parts.append("⚠️ 本章必须回收的伏笔: " + ", ".join(f"{i['description']}(第{i['planted_in']}章埋入)" for i in needs_resolve))
        return "\n".join(parts) if parts else ""
    except Exception:
        return ""


def build_chapter_prompt(volume_id: int, chapter_id: int, chapter_title: str = None,
                         overview: str = None, entities: dict = None) -> str:
    """Build the full writing prompt for a chapter. Shared between CLI and WebUI.
    All parameters are optional — if not provided, they are loaded from disk."""
    # Load from disk if not provided
    entity_list = []
    if chapter_title is None or overview is None:
        outline = load_chapter_outline(volume_id, chapter_id)
        if outline:
            chapter_title = chapter_title or outline.get("title", f"第{chapter_id}章")
            overview = overview or outline.get("overview", "")
            entity_list = outline.get("entity_list", [])
        else:
            chapter_title = chapter_title or f"第{chapter_id}章"
            overview = overview or ""

    if entities is None:
        entities = load_entity_cards(entity_list)

    prev_chapter = load_previous_chapter(volume_id, chapter_id)
    history_chapters = load_history_chapters(volume_id, chapter_id, count=3)
    next_outline = load_next_chapter_outline(volume_id, chapter_id)

    # ── Build prompt: one chapter = one clear goal ──
    # Principle: emotional goal > plot outline > constraints
    # Information budget: minimal. Skill injections handle the rest via hooks.
    prompt_parts = []

    # 1. Entity context (lightweight — who is in this scene)
    prompt_parts.append(f"【本章大纲】\n{overview}\n")
    if entities:
        chars = entities.get('characters', [])
        if chars:
            prompt_parts.append(f"【出场角色】{', '.join(c.get('name','?') for c in chars[:5])}\n")

    if prev_chapter:
        prompt_parts.append(f"【前章结尾（接续点）】\n{prev_chapter}\n")

    if history_chapters:
        prompt_parts.append(f"【近期剧情回顾】\n{history_chapters}\n")

    if next_outline:
        next_title = next_outline.get("title", "")
        next_overview = next_outline.get("overview", "")
        prompt_parts.append(f"【下一章预告】:\n{next_title}：{next_overview}\n")

    # Structured outline (scene-level beats — AI: detail in = detail out)
    # Unlike human authors (who may lose inspiration from over-planning),
    # AI models produce BETTER output with MORE detailed outlines.
    structured_outline = _load_structured_outline_chapter(chapter_id)
    if structured_outline:
        detail_parts = []
        if structured_outline.get("summary"):
            detail_parts.append(f"概要: {structured_outline['summary']}")
        if structured_outline.get("emotional_beat"):
            detail_parts.append(f"本章情绪目标: {structured_outline['emotional_beat']}")
        if structured_outline.get("satisfaction_beat"):
            detail_parts.append(f"本章爽点(必须写到): {structured_outline['satisfaction_beat']}")
        if structured_outline.get("ending_hook"):
            detail_parts.append(f"章末钩子: {structured_outline['ending_hook']}")
        if structured_outline.get("scenes_text") or structured_outline.get("scenes"):
            scenes = structured_outline.get("scenes_text") or "\n".join(
                f"- {s.get('name','')}: POV={s.get('pov','主角')} | 目标={s.get('goal','')} | 冲突={s.get('conflict','')} | 字数≈{s.get('word_target','?')}字"
                for s in (structured_outline.get("scenes", []) if isinstance(structured_outline.get("scenes"), list) else [])
            )
            detail_parts.append(f"场景分解 (POV锁死，禁止透视配角内心):\n{scenes}")
        if detail_parts:
            prompt_parts.append("【细纲 — 本章执行指南（AI模型：越详细输出越精准）】\n" + "\n".join(detail_parts) + "\n")
    else:
        # No structured outline — inject minimal goal from overview
        logger.info("No structured_outline for chapter %d, using overview as fallback", chapter_id)

    fs_ctx = _load_foreshadowing_context(chapter_id)
    if fs_ctx:
        prompt_parts.append(f"【伏笔提醒】{fs_ctx}\n")

    # Minimal constraints — the model needs freedom, not a rulebook
    prompt_parts.append(
        "【要求】承接前章情绪，本章至少有一个爽点/钩子。约3000字。直接输出正文。\n"
    )

    return "\n".join(prompt_parts)


def generate_chapter_content(volume_id: int, chapter_id: int, state_manager=None,
                              rewrite_guidance: str = None) -> str:
    """
    Generate chapter content from chapter outline using @DSL context injection.
    Supports progressive saving via state_manager.
    If rewrite_guidance is provided, injects it as quality gate feedback.
    """
    if rewrite_guidance:
        print(f"\n[REWRITE] 第 {volume_id} 卷第 {chapter_id} 章 — 质量门控重写 (guidance: {rewrite_guidance[:80]}...)")
    else:
        print(f"\n[INFO] 正在生成第 {volume_id} 卷第 {chapter_id} 章...")

    # Load chapter outline
    outline = load_chapter_outline(volume_id, chapter_id)
    if not outline:
        print(f"[ERROR] 找不到章节大纲: vol_{volume_id:02d} ch_{chapter_id:03d}")
        return ""

    chapter_title = outline.get("title", f"第{chapter_id}章")
    overview = outline.get("overview", "")
    entity_list = outline.get("entity_list", [])

    print(f"  章节: {chapter_title}")
    print(f"  概述: {overview[:50]}...")
    print(f"  参与者: {', '.join(entity_list)}")

    # Load entities for display
    entities = load_entity_cards(entity_list)

    # Build prompt using shared function
    prompt = build_chapter_prompt(volume_id, chapter_id, chapter_title, overview, entities)

    # ── Style Reference Injection (Human-Reference Anchoring, POLARIS 2026) ──
    # Must be at TOP of prompt — style target must be seen before instructions
    try:
        from core.style_reference import build_style_prompt
        from utils.config_loader import get_config
        genre_name = get_config("genre", default="")
        if not genre_name:
            from core.genre_knowledge import match_genre
            genre_name = "修仙"
        style_prompt = build_style_prompt(genre_name)
        if style_prompt:
            prompt = style_prompt + "\n" + prompt
    except Exception as e:
        logger.debug("Style reference injection skipped: %s", e)

    # Inject rewrite guidance if provided
    if rewrite_guidance:
        prompt += f"\n\n[Quality Gate Rewrite — Previous attempt issues to fix]\n{rewrite_guidance}\n"

    # Narrative diversity injection DISABLED — archetypes are unverified working hypotheses.
    # Will re-enable after web-verifying archetype definitions against published taxonomy.
    # See: core/narrative_diversity.py [待验证] markers.

    # Inject storyform constraints (verified Dramatica examples: Hamlet + Star Wars)
    try:
        from core.storyform import Storyform
        from utils.config_loader import get_config
        novel_name = get_config("workspace.novel_name", default="")
        sf_path = Path(".novel") / f"{novel_name}" / "storyform.json" if novel_name else None
        if not sf_path or not sf_path.exists():
            sf_path = Path(".novel") / "storyform.json"
        if sf_path.exists():
            import json
            sf_data = json.loads(sf_path.read_text(encoding="utf-8"))
            sf = Storyform.from_dict(sf_data)
            sf_context = sf.to_writing_context()
            if sf_context:
                prompt += sf_context
    except Exception as e:
        logger.debug("Storyform injection skipped: %s", e)

    # Inject genre knowledge — slim: only this chapter's relevant hooks + mistakes
    try:
        from core.genre_knowledge import get_genre_knowledge
        from utils.config_loader import get_config
        genre_name = get_config("genre", default="")
        if genre_name:
            gk = get_genre_knowledge(genre_name)
            if gk:
                hook_str = " | ".join(gk.hook_templates[:3]) if gk.hook_templates else ""
                avoid_str = " | ".join(gk.common_mistakes[:3]) if gk.common_mistakes else ""
                slim = f"\n[{gk.name}] 可用钩子: {hook_str}. 避免: {avoid_str}.\n"
                prompt += slim
    except Exception as e:
        logger.debug("Genre knowledge skipped: %s", e)

    # Mark unified injections so duplicate skills skip themselves
    # (context is shared across all skills via event_bus subscribers)
    for skill in event_bus.subscribers:
        try:
            skill.context.set_shared("unified_style_injected", True)
            skill.context.set_shared("unified_genre_injected", True)
        except Exception:
            pass

    # Emit hook for skill injection (memories, constraints, state)
    beat_data = {"chapter_id": chapter_id, "title": chapter_title, "overview": overview}
    prompt_parts = [prompt]
    prompt_parts = event_bus.emit_pipeline("on_before_scene_write", prompt_parts, beat_data)
    prompt = "\n".join(prompt_parts)

    # Progressive saving callback
    def on_progress(ch_id, accumulated, char_count):
        if state_manager and ch_id:
            state_manager.update_progress(ch_id, char_count)
            # Save to temp file
            temp_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{ch_id:03d}_temp.md"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(accumulated)

    # Generate content with progressive saving
    writer = ProgressiveWriter(on_progress=on_progress, chunk_size=get_config("writing.progress_chunk_size", 1000), task="writing")
    content = writer.write(prompt, chapter_id=chapter_id)

    return content


def review_chapter_content(volume_id: int, chapter_id: int, content: str, outline: dict) -> str:
    """
    Review chapter content for:
    1. Missing title - add from outline
    2. Word count check (using config.json settings)
    3. Content too short - flag for rewrite

    Returns tuple: (reviewed_content, needs_rewrite, issues)
    """
    issues = []

    # Get config values
    target_word_count = get_config("writing.target_word_count", 6000)
    min_word_count = get_config("writing.min_word_count", 4000)
    max_word_count = get_config("writing.max_word_count", 9000)
    auto_fix_title = get_config("review.auto_fix_title", True)
    word_count_check = get_config("review.word_count_check", True)

    # Check if title exists (first line should be # 第X章 xxx)
    title_pattern = r'^#\s*第\d+章\s+.+'
    if not re.match(title_pattern, content.strip()):
        if auto_fix_title:
            chapter_title = outline.get("title", f"第{chapter_id}章") if outline else f"第{chapter_id}章"
            content = f"# 第{chapter_id}章 {chapter_title}\n\n{content}"
            issues.append(f"[审阅] 缺少章节标题，已自动添加：第{chapter_id}章 {chapter_title}")
        else:
            issues.append(f"[审阅] 缺少章节标题")

    # Check word count (code-based)
    if word_count_check:
        word_count = count_chinese_words(content)
        if word_count < min_word_count:
            issues.append(f"[审阅] 字数不足（{word_count}字），低于{min_word_count}字下限")
            return content, True, issues
        elif word_count > max_word_count:
            issues.append(f"[审阅] 字数过多（{word_count}字），超过{max_word_count}字上限")
            return content, True, issues
        elif word_count < target_word_count * 0.9:
            issues.append(f"[审阅] 字数偏少（{word_count}字），目标{target_word_count}字")
        else:
            issues.append(f"[审阅] 字数检查通过（{word_count}字）")

    # Check for obvious logical issues
    first_lines = content.strip().split('\n')[:5]
    if len(first_lines) < 3:
        issues.append("[审阅] 正文开头内容过少")
        return content, True, issues

    return content, False, issues


def count_chinese_words(text: str) -> int:
    """
    Count words in mixed Chinese/English text.
    - Chinese characters: each character counts as one word
    - English words: split by whitespace, each word counts as one
    - Punctuation is ignored
    """
    import re

    # Remove markdown title if present
    text = re.sub(r'^#\s*第\d+章\s+.+\n?', '', text)

    # Count Chinese characters (each Chinese char is a word)
    chinese_chars = len(re.findall(r'[一-鿿　-〿＀-￯]', text))

    # Count English words (sequences of letters/digits)
    english_words = len(re.findall(r'[a-zA-Z0-9]+', text))

    # Total word count
    return chinese_chars + english_words


def deep_review_chapter(content: str, outline: dict, entity_list: List[str]) -> dict:
    """
    Deep review of chapter content vs outline.
    Returns: {needs_rewrite: bool, guidance: str, issues: List[str]}
    """
    # Check if deep review is enabled
    if not get_config("review.deep_review_enabled", True):
        return {"needs_rewrite": False, "issues": [], "guidance": "", "missing_events": [], "wrong_events": []}

    from utils.llm_client import generate_json
    from pydantic import BaseModel
    from typing import List

    class ReviewResult(BaseModel):
        needs_rewrite: bool
        issues: List[str]
        guidance: str
        missing_events: List[str]
        wrong_events: List[str]

    prompt = f"""你是网络小说编辑。请审阅以下章节内容，与大纲进行对比。

【章节大纲】：
标题：{outline.get('title', '')}
概述：{outline.get('overview', '')}

【章节正文】：
{content[:3000]}...（正文已截断）

【参与者实体】：
{', '.join(entity_list)}

请检查：
1. 大纲中的核心事件是否在正文中出现
2. 正文是否有偏离大纲设定的事件
3. 角色行为是否与设定矛盾
4. 场景描写是否符合要求

输出JSON：
{{"needs_rewrite": true/false, "issues": ["问题1", "问题2"], "guidance": "重新写作的指导建议", "missing_events": ["遗漏事件1"], "wrong_events": ["偏离事件1"]}}
"""

    try:
        result = generate_json(prompt, ReviewResult)
        if hasattr(result, 'model_dump'):
            return result.model_dump()
        return result if isinstance(result, dict) else {"needs_rewrite": False, "issues": [], "guidance": "", "missing_events": [], "wrong_events": []}
    except Exception as e:
        print(f"[WARN] 深度审阅失败: {e}")
        return {"needs_rewrite": False, "issues": [], "guidance": "", "missing_events": [], "wrong_events": []}


def post_process_chapter(volume_id: int, chapter_id: int, content: str,
                         outline: dict = None) -> tuple:
    """
    Shared post-generation pipeline: save -> emit hooks -> quality gate.
    Called by BOTH CLI (run_scene_writer) and WebUI (/api/write-stream).

    Returns: (final_path: str, gate_verdict: str, gate_guidance: str)
      gate_verdict: "PASS" | "REWRITE" | "BLOCK" | None (no gate)
    """
    # Save
    save_result = save_chapter_content(volume_id, chapter_id, content, outline)
    if isinstance(save_result, tuple):
        final_path, needs_rewrite, basic_guidance = save_result
    else:
        final_path = save_result
        needs_rewrite = False
        basic_guidance = ""

    # Emit full hook chain
    beat_data = {
        "chapter_id": chapter_id, "beats": [],
        "needs_rewrite": needs_rewrite, "guidance": basic_guidance,
    }
    event_bus.emit("on_after_scene_write", beat_data, content)
    event_bus.emit("on_post_chapter_continuity", chapter_id)
    event_bus.emit("on_chapter_render", content, chapter_id)
    event_bus.emit("on_after_chapter_complete", chapter_id, content)

    # Check quality gate result
    from core.quality_gate import get_last_result
    gate_result = get_last_result()
    gate_verdict = gate_result.verdict if gate_result else None
    gate_guidance = gate_result.rewrite_guidance if gate_result else ""

    return final_path, gate_verdict, gate_guidance


def save_chapter_content(volume_id: int, chapter_id: int, content: str, outline: dict = None):
    """Save chapter content to file, with review."""
    save_dir = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}"
    save_dir.mkdir(parents=True, exist_ok=True)

    # Load outline if not provided
    if outline is None:
        outline = load_chapter_outline(volume_id, chapter_id)

    entity_list = outline.get("entity_list", []) if outline else []

    # Basic review: check title, content length
    reviewed_content, basic_needs_rewrite, basic_issues = review_chapter_content(volume_id, chapter_id, content, outline)

    # Log basic issues
    for issue in basic_issues:
        print(f"  {issue}")

    # Deep review for content coherence (only if basic check passed)
    deep_review_result = {"needs_rewrite": False, "issues": [], "guidance": ""}
    if not basic_needs_rewrite:
        deep_review_result = deep_review_chapter(reviewed_content, outline, entity_list)
        if deep_review_result.get("needs_rewrite"):
            print(f"  [审阅] 发现严重问题：{', '.join(deep_review_result.get('issues', []))}")
            print(f"  [审阅] 指导意见：{deep_review_result.get('guidance', '')}")

    # Determine if rewrite is needed
    final_needs_rewrite = basic_needs_rewrite or deep_review_result.get("needs_rewrite", False)

    # Save content
    final_path = save_dir / f"ch_{chapter_id:03d}_final.md"
    with open(final_path, 'w', encoding='utf-8') as f:
        f.write(reviewed_content)

    if final_needs_rewrite:
        print(f"[⚠] 第 {chapter_id} 章标记为需要检查")
        return str(final_path), True, deep_review_result.get("guidance", "")
    else:
        print(f"[✓] 第 {chapter_id} 章成稿已保存至 {final_path}")
        return str(final_path), False, ""


def run_scene_writer(volume_id: int, start_chapter: int, end_chapter: int):
    """
    Main entry point for scene writing.
    Generates chapters from start_chapter to end_chapter.
    Uses state machine for progress tracking and supports resume from interruption.
    """
    state_manager = get_state_manager(volume_id)
    completed = 0
    failed = 0

    # Register chapters that need to be generated
    for chapter_id in range(start_chapter, end_chapter + 1):
        state = state_manager.get_state(chapter_id)
        if state.state == STATE_COMPLETED:
            # Check if file actually exists
            save_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id:03d}_final.md"
            if save_path.exists() and save_path.stat().st_size > 1000:
                print(f"[Skip] 第 {chapter_id} 章已完成，跳过")
                continue
            else:
                # File doesn't exist, mark as pending
                state.state = STATE_PENDING

    for chapter_id in range(start_chapter, end_chapter + 1):
        state = state_manager.get_state(chapter_id)

        # Skip if already completed
        save_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id:03d}_final.md"
        if save_path.exists() and save_path.stat().st_size > 1000:
            print(f"[Skip] 第 {chapter_id} 章已存在，跳过")
            continue

        # Check for temp file (resume from interruption)
        temp_path = Path(MANUSCRIPTS_DIR) / f"vol_{volume_id:02d}" / f"ch_{chapter_id:03d}_temp.md"
        if temp_path.exists():
            print(f"[Resume] 检测到第 {chapter_id} 章的临时文件，将继续生成")
            # Delete temp file to restart fresh
            temp_path.unlink()

        print(f"\n{'='*60}")
        print(f"[INFO] 启动场景子智能体集群，目标：卷 {volume_id} 章 {chapter_id}")
        print(f"{'='*60}")

        # Mark as generating
        state_manager.mark_generating(chapter_id)

        try:
            # ── Quality Gate rewrite loop ──
            gate_round = 0
            max_gate_rounds = 3
            content = ""
            guidance = ""

            while gate_round < max_gate_rounds:
                gate_round += 1

                # Generate chapter content (with progressive saving + guidance injection)
                content = generate_chapter_content(volume_id, chapter_id, state_manager,
                                                   rewrite_guidance=guidance if guidance else None)

                if not content:
                    break

                # Save + emit hooks + run quality gate (shared pipeline)
                log_step("Chapter post-process", chapter_id=chapter_id, volume_id=volume_id,
                         words=len(content), round=gate_round)
                final_path, gate_verdict, gate_guidance = post_process_chapter(
                    volume_id, chapter_id, content)

                if gate_verdict == "PASS" or gate_verdict is None:
                    log_step("Chapter PASS", chapter_id=chapter_id, round=gate_round)
                    if gate_verdict == "PASS":
                        print(f"  [OK] Quality Gate: PASS (round {gate_round})")
                    else:
                        print(f"  [OK] Quality Gate: no gate result (round {gate_round})")
                    break
                elif gate_verdict == "REWRITE" and gate_round < max_gate_rounds:
                    guidance = gate_guidance
                    logger.warning("Quality Gate: REWRITE round %d/%d, chapter %d",
                                   gate_round, max_gate_rounds, chapter_id)
                    log_step("Chapter REWRITE", chapter_id=chapter_id, round=gate_round)
                    for sk in event_bus.subscribers:
                        if hasattr(sk, 'record_rewrite'):
                            sk.record_rewrite(chapter_id)
                            break
                elif gate_verdict == "BLOCK":
                    logger.error("Quality Gate: BLOCKED chapter %d after %d rounds",
                                 chapter_id, gate_round)
                    log_step("Chapter BLOCKED", chapter_id=chapter_id, rounds=gate_round)
                    break
                else:
                    logger.error("Quality Gate: max rounds exceeded, chapter %d", chapter_id)
                    gate_verdict = "BLOCK"
                    break

            if content:
                # Mark as completed (or blocked)
                if gate_verdict == "BLOCK":
                    state_manager.mark_failed(chapter_id, f"Quality Gate BLOCKED after {gate_round} rounds")
                    failed += 1
                else:
                    state_manager.mark_completed(chapter_id)
                    completed += 1

                # Delete temp file if exists
                if temp_path.exists():
                    temp_path.unlink()

                # Track entity states for this chapter
                from core.entity_tracker import track_chapter_entities
                track_chapter_entities(volume_id, chapter_id)
            else:
                state_manager.mark_failed(chapter_id, "content empty")
                failed += 1
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] 第 {chapter_id} 章生成失败: {error_msg}")
            state_manager.mark_failed(chapter_id, error_msg)
            failed += 1

    print(f"\n{'='*60}")
    print(f"[INFO] 本批次生成完成：成功 {completed} 章，失败 {failed} 章")
    print(f"[INFO] 可通过重新运行命令继续生成失败的章节")
    print(f"{'='*60}")


# ============================================================================

# ============================================================================
# Batch Mode (for compatibility)
# ============================================================================

def generate_batch_jsonl(volume_id: int, start_chap: int, end_chap: int, output_jsonl: str):
    """Generate batch JSONL for chapter outlines (not beats)."""
    requests = []

    for chapter_id in range(start_chap, end_chap + 1):
        outline = load_chapter_outline(volume_id, chapter_id)
        if not outline:
            continue

        custom_id = f"v{volume_id:02d}_ch{chapter_id:03d}"

        # Build prompt similar to generate_chapter_content
        prompt_parts = [
            f"【章节大纲】:\n标题：{outline.get('title', '')}\n概述：{outline.get('overview', '')}\n",
        ]

        # Inject entity context
        entity_list = outline.get("entity_list", [])
        entities = load_entity_cards(entity_list)
        if entities["characters"]:
            prompt_parts.append(f"【角色】: {json.dumps(entities['characters'], ensure_ascii=False)}\n")
        if entities["scenes"]:
            prompt_parts.append(f"【场景】: {json.dumps(entities['scenes'], ensure_ascii=False)}\n")

        # Add writing guide
        writing_guide = load_writing_guide(volume_id)
        if writing_guide:
            prompt_parts.append(f"【写作指南】: {writing_guide}\n")

        prompt_parts.append("请根据章节大纲创作正文，约6000字。直接输出正文。")

        request_obj = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v4/chat/completions",
            "body": {
                "model": "glm-4",
                "messages": [{"role": "user", "content": "\n".join(prompt_parts)}],
                "temperature": 0.85
            }
        }
        requests.append(request_obj)

    with open(output_jsonl, 'w', encoding='utf-8') as f:
        for req in requests:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")

    print(f"[✓] 已生成包含 {len(requests)} 个请求的 Batch 文件: {output_jsonl}")


def process_batch_results(result_jsonl: str):
    """Process batch results and save chapters."""
    if not os.path.exists(result_jsonl):
        print(f"[ERROR] 找不到结果文件: {result_jsonl}")
        return

    chapters_map = {}

    with open(result_jsonl, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            custom_id = data["custom_id"]
            try:
                content = data["response"]["body"]["choices"][0]["message"]["content"]
            except (KeyError, TypeError):
                content = "（该段场景生成失败）"

            chapters_map[custom_id] = content

    for custom_id, content in chapters_map.items():
        # Parse custom_id: v01_ch001
        parts = custom_id.split("_")
        vol_id = int(parts[0][1:])
        ch_id = int(parts[1][2:])

        save_chapter_content(vol_id, ch_id, content)


def get_world_context() -> str:
    """Get world context for backward compatibility."""
    from core.context_assembler import assemble_context
    path = Path(SETTINGS_DIR) / "world_setting.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""