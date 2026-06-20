"""
Novel-Claude Fusion Web UI - FastAPI Backend
"""
from __future__ import annotations

import json, os, sys, time, asyncio, io
from pathlib import Path
from typing import Optional, AsyncGenerator

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, Form, WebSocket
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

VERSION = "v0.3"

app = FastAPI(title=f"Novel-Claude Fusion {VERSION}")

# ── Logging: configure ONCE ──
from utils.logger import setup_logging, get_logger, log_step
setup_logging()
webui_logger = get_logger("webui")

# Mount static
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── config helpers ─────────────────────────────────────────────────────

def load_cfg():
    cfg_path = Path(__file__).parent.parent / "config.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_cfg(cfg):
    cfg_path = Path(__file__).parent.parent / "config.json"
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def _build_causal_context(chapter: int) -> str:
    """加载因果图引擎，生成写作前上下文（角色动机+活跃线索）。"""
    try:
        novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
        novel_path = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
        if not (novel_path / "causal_graph.json").exists():
            return ""

        from core.causal_graph import CausalGraphEngine
        engine = CausalGraphEngine(novel_path)
        parts = []

        # 角色动机
        char_ctx = engine.get_active_characters_context(chapter)
        if char_ctx:
            parts.append(f"\n\n【前情与角色状态 (因果引擎)】\n{char_ctx}")

        # 活跃线索
        threads = engine.get_active_threads()
        if threads:
            parts.append(f"\n【请注意以下未闭合的因果线 ({len(threads)}条)】")
            for t in threads[:8]:
                parts.append(f"- {t['summary'][:80]}")

        return "\n".join(parts) if parts else ""
    except Exception:
        return ""


def _build_genre_style_injection(cfg: dict) -> str:
    """从 config 读取 genre/style，构建 prompt 注入文本。
    如果流派/风格未配置或数据库无匹配，返回空字符串。"""
    genre = cfg.get("genre", "")
    style = cfg.get("style", "")
    injection = ""

    if genre:
        try:
            from skills.gen_genre_tags.skill import GENRE_DB
            g = GENRE_DB.get(genre)
            if g:
                injection += f"\n\n[流派: {genre}]\n"
                injection += f"- 反套路模式（严格禁止）: {'、'.join(g.get('antiPatterns', []))}\n"
                injection += f"- 节奏策略: {g.get('pacingStrategy', '')}\n"
                injection += f"- 典型结构: {g.get('typicalStructure', '')}\n"
                if g.get('worldRules'):
                    injection += f"- 世界规则: {'; '.join(g['worldRules'])}\n"
        except Exception:
            pass

    if style:
        try:
            from skills.gen_writing_style.skill import STYLE_DB
            s = STYLE_DB.get(style)
            if s:
                injection += f"\n\n[写作风格: {style}]\n"
                injection += f"{s.get('promptInjection', '')}\n"
                injection += f"- 偏好词汇: {'、'.join(s.get('vocabulary', [])[:8])}\n"
                injection += f"- 禁止: {'、'.join(s.get('avoidPatterns', []))}\n"
                injection += f"- 对话风格: {s.get('dialogueStyle', '')}\n"
                injection += f"- 叙事距离: {s.get('narrativeDistance', '')}\n"
        except Exception:
            pass

    return injection


# ── project management ──────────────────────────────────────────────────

@app.get("/api/projects")
async def list_projects():
    """List all novel projects (directories matching .novel_*)."""
    projects = []
    base = Path(__file__).parent.parent
    for d in sorted(base.iterdir()):
        if d.is_dir() and d.name.startswith(".novel_"):
            name = d.name[7:]  # strip ".novel_"
            if name:
                sp = d / "story_state.json"
                chapters = len(list((d / "manuscripts").rglob("ch_*_final.md"))) if (d / "manuscripts").exists() else 0
                projects.append({
                    "name": name,
                    "dir": str(d),
                    "has_story_state": sp.exists(),
                    "chapters": chapters,
                })
    return {"projects": projects, "active": load_cfg().get("workspace", {}).get("novel_name", "")}

@app.post("/api/projects/switch")
async def switch_project(request: Request):
    """Switch to a different project (or create new one)."""
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return {"error": "项目名不能为空"}

    cfg = load_cfg()
    cfg.setdefault("workspace", {})["novel_name"] = name
    save_cfg(cfg)

    # Ensure directories exist
    novel_dir = Path(__file__).parent.parent / f".novel_{name}"
    for sub in ["settings", "volumes", "manuscripts", "memory", "batch_jobs"]:
        (novel_dir / sub).mkdir(parents=True, exist_ok=True)

    from utils.config import reload_workspace
    reload_workspace()
    return {"ok": True, "name": name}

@app.post("/api/projects/delete")
async def delete_project(request: Request):
    """Delete a project (only its directory, not config)."""
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return {"error": "项目名不能为空"}

    novel_dir = Path(__file__).parent.parent / f".novel_{name}"
    if not novel_dir.exists():
        return {"error": "项目不存在"}

    import shutil
    shutil.rmtree(novel_dir)

    # If this was the active project, clear it
    cfg = load_cfg()
    if cfg.get("workspace", {}).get("novel_name") == name:
        cfg["workspace"]["novel_name"] = ""
        save_cfg(cfg)
        from utils.config import reload_workspace
        reload_workspace()

    return {"ok": True}

# ── routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    tpl = Path(__file__).parent / "templates" / "index.html"
    return tpl.read_text(encoding="utf-8")

@app.get("/api/config")
async def get_config():
    cfg = load_cfg()
    # Frontend expects genres/styles arrays for settings dropdowns
    try:
        from skills.gen_genre_tags.skill import GENRE_DB
        cfg["genres"] = list(GENRE_DB.keys())
    except Exception: cfg["genres"] = ["修仙"]
    try:
        from skills.gen_writing_style.skill import STYLE_DB
        cfg["styles"] = list(STYLE_DB.keys())
    except Exception: cfg["styles"] = ["网文爽文"]
    return cfg

@app.post("/api/config")
async def update_config(request: Request):
    """Update config.json fields. Accepts JSON body with any config keys."""
    cfg = load_cfg()
    data = await request.json()

    # Top-level string fields
    for key in ("novel_name", "genre", "style"):
        if key in data and data[key]:
            if key == "novel_name":
                cfg.setdefault("workspace", {})["novel_name"] = data[key]
            else:
                cfg[key] = data[key]

    # Workflow mode
    if "workflow" in data and data["workflow"]:
        cfg.setdefault("workflow", {})["mode"] = data["workflow"]
    if "max_revision_rounds" in data:
        cfg.setdefault("workflow", {})["max_revision_rounds"] = data["max_revision_rounds"]
    if "quality_threshold" in data:
        cfg.setdefault("workflow", {})["quality_threshold"] = data["quality_threshold"]

    # Generation params (温度、惩罚、采样)
    gen_keys = [
        "temperature", "temperature_planning", "temperature_writing",
        "temperature_reasoning", "temperature_deai",
        "frequency_penalty", "frequency_penalty_writing", "frequency_penalty_deai",
        "frequency_penalty_planning", "frequency_penalty_reasoning",
        "presence_penalty", "presence_penalty_writing", "presence_penalty_deai",
        "presence_penalty_planning", "presence_penalty_reasoning",
        "top_p", "top_p_writing", "top_p_deai", "top_p_planning", "top_p_reasoning",
        "max_tokens", "max_retries", "timeout", "retry_delay",
    ]
    for key in gen_keys:
        if key in data and data[key] is not None:
            cfg.setdefault("generation", {})[key] = data[key]

    save_cfg(cfg)
    return {"ok": True}

@app.get("/api/status")
async def status():
    from core.story_state import load_story_state, current_chapter
    from utils.llm_client import get_provider_info

    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    sp = Path(f".novel_{novel_dir}" if novel_dir else ".novel") / "story_state.json"

    pi = get_provider_info()
    result = {"connected": True, "version": VERSION,
              "provider": pi["provider"],
              "model": pi["model"], "novel_name": novel_dir}

    if sp.exists():
        s = load_story_state(sp)
        result["title"] = s.title or novel_dir
        result["genre"] = s.genre
        result["cur_chapter"] = current_chapter(s)
        result["char_count"] = len(s.characters)
        result["thread_count"] = len(s.plot_threads)
        result["chapter_count"] = len([c for c in s.chapters.values() if c.status != "planned"])
        result["chapters"] = [
            {"num": num, "volume": (num - 1) // 70 + 1,
             "title": ch.title, "status": ch.status, "words": ch.word_count}
            for num, ch in sorted(s.chapters.items())[-20:]
        ]

    # ── New modules status ──
    cfg = load_cfg()
    result["modules"] = {
        "quality_gate": cfg.get("quality_gate", {}).get("enabled", True),
        "quality_gate_threshold": cfg.get("quality_gate", {}).get("pass_threshold", 70),
        "logging": True,
        "log_path": str(Path(os.path.expanduser("~/.novel_claude_logs"))),
        "daily_rotation": True,
    }

    # Last quality gate result
    try:
        from core.quality_gate import get_last_result
        lr = get_last_result()
        if lr:
            result["last_gate"] = {"score": lr.overall_score, "verdict": lr.verdict,
                                    "round": lr.rewrite_round, "critical": lr.continuity_critical}
    except Exception:
        pass

    # Narrative diversity
    try:
        from core.narrative_diversity import diversity_score
        # Load recent chapter fingerprints if available
        result["diversity"] = {"status": "available", "archetypes": 5}
    except Exception:
        pass

    # Story engine status (题材×风格匹配)
    try:
        from core.story_engine import match_storyform
        genre = cfg.get("genre", "")
        style = cfg.get("style", "")
        if genre or style:
            matched = match_storyform(genre, style)
            result["story_engine"] = {
                "genre": genre,
                "style": style,
                "genre_found": matched["genre_found"],
                "style_found": matched["style_found"],
                "constraint_count": len(matched["constraints"]),
            }
    except Exception:
        result["story_engine"] = {"available": False}

    # Legacy storyform status
    try:
        sf_path = sp.parent / "storyform.json" if sp.exists() else Path(".novel/storyform.json")
        result["storyform"] = {"loaded": sf_path.exists()}
    except Exception:
        result["storyform"] = {"loaded": False}

    return result

@app.get("/api/continuity")
async def continuity(chapter: Optional[int] = None):
    from core.story_state import load_story_state
    from core.continuity_engine import run_all

    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    sp = Path(f".novel_{novel_dir}" if novel_dir else ".novel") / "story_state.json"
    if not sp.exists():
        return {"findings": [], "summary": "No StoryState yet"}

    s = load_story_state(sp)
    findings = run_all(s, Path.cwd(), as_of_chapter=chapter)
    return {
        "findings": [{"severity": f.severity, "category": f.category,
                       "message": f.message, "suggestion": f.suggestion,
                       "chapter": f.chapter} for f in findings],
        "critical": sum(1 for f in findings if f.severity == "critical"),
        "warning": sum(1 for f in findings if f.severity == "warning"),
        "info": sum(1 for f in findings if f.severity == "info"),
    }

@app.post("/api/deai")
async def deai(request: Request):
    data = await request.json()
    chapter = data.get("chapter", 1)
    from skills.gen_deai_engine.skill import GenDeaiEngineSkill

    # Find chapter file
    manuscript = Path("manuscripts") if Path("manuscripts").exists() else Path(f".novel/manuscripts")
    content = None
    for vd in manuscript.iterdir() if manuscript.exists() else []:
        if vd.is_dir():
            fp = vd / f"ch_{chapter:03d}_final.md"
            if fp.exists():
                content = fp.read_text(encoding="utf-8")
                break
    if not content:
        return {"error": f"Chapter {chapter} not found"}

    class Ctx:
        def get_shared(self, k, d=None): return d
        def set_shared(self, k, v): pass



    e = GenDeaiEngineSkill(Ctx())
    e.on_init()
    return e.analyze(content)

@app.get("/api/genres")
async def genres():
    from skills.gen_genre_tags.skill import GENRE_DB
    return list(GENRE_DB.keys())

@app.get("/api/styles")
async def styles(genre: str = ""):
    from skills.gen_writing_style.skill import STYLE_DB
    from skills.gen_genre_tags.skill import GENRE_DB
    if genre and genre in GENRE_DB:
        return _compatible_styles(genre)
    return list(STYLE_DB.keys())


# ── genre → style compatibility mapping ──────────────────────────────────

def _compatible_styles(genre: str) -> list:
    """Return styles compatible with the given genre."""
    # Category-based mapping: each genre category has recommended styles
    EASTERN_FANTASY = ["网文爽文", "热血燃向", "金庸武侠", "古龙风格", "说书风", "多视角切换"]
    MODERN = ["网文爽文", "幽默吐槽", "白描纪实", "第一人称口语化", "硬汉冷峻", "现代极简"]
    SCIFI = ["硬核科幻", "暗黑压抑", "白描纪实", "多视角切换", "现代极简"]
    HORROR = ["暗黑压抑", "暗黑哥特", "白描纪实", "第一人称口语化"]
    ROMANCE = ["文艺唯美", "纯文学", "第一人称口语化", "轻小说", "幽默吐槽"]
    HISTORICAL = ["说书风", "金庸武侠", "文艺唯美", "多视角切换", "纯文学"]
    LIGHT = ["轻小说", "幽默吐槽", "第一人称口语化", "剧本风"]
    LITERARY = ["纯文学", "文艺唯美", "意识流", "白描纪实", "现代极简"]

    mapping = {
        "玄幻": EASTERN_FANTASY, "修仙": EASTERN_FANTASY, "洪荒": EASTERN_FANTASY,
        "武侠": ["金庸武侠", "古龙风格", "热血燃向", "说书风"],
        "都市": MODERN, "校园": MODERN, "重生": MODERN, "系统流": MODERN,
        "总裁": ROMANCE + ["网文爽文"], "宫斗": ROMANCE + ["暗黑压抑", "多视角切换"], "快穿": LIGHT + ROMANCE,
        "言情": ROMANCE,
        "科幻": SCIFI, "赛博朋克": SCIFI + ["黑色幽默"], "星际": SCIFI + ["热血燃向"],
        "末世": ["暗黑压抑", "热血燃向", "白描纪实", "第一人称口语化"],
        "废土": ["暗黑压抑", "硬汉冷峻", "白描纪实", "现代极简"],
        "进化": SCIFI + ["暗黑压抑"],
        "悬疑": ["白描纪实", "暗黑压抑", "第一人称口语化", "硬汉冷峻", "黑色幽默"],
        "灵异": HORROR, "盗墓": HORROR + ["第一人称口语化"], "克苏鲁": HORROR + ["意识流"],
        "历史": HISTORICAL, "种田": HISTORICAL + ["白描纪实"],
        "游戏": ["网文爽文", "热血燃向", "幽默吐槽", "轻小说"],
        "竞技": ["热血燃向", "白描纪实", "第一人称口语化", "现代极简"],
        "军事": ["硬汉冷峻", "白描纪实", "多视角切换", "热血燃向"],
        "轻小说": LIGHT,
        "无限流": ["网文爽文", "暗黑压抑", "幽默吐槽", "多视角切换"],
    "规则怪谈": ["暗黑压抑", "白描纪实", "硬汉冷峻", "第一人称口语化"],
    "发疯文": ["幽默吐槽", "第一人称口语化", "意识流", "黑色幽默"],
    "家族修仙": ["说书风", "多视角切换", "热血燃向", "文艺唯美"],
    }
    if genre in mapping:
        return mapping[genre]
    from skills.gen_writing_style.skill import STYLE_DB
    return list(STYLE_DB.keys())

@app.get("/api/formulas")
async def formulas():
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    fd = Path(f".novel_{novel_dir}" if novel_dir else ".novel") / "formulas"
    if fd.exists():
        return [p.stem for p in fd.glob("*.json")]
    return []

# ── streaming chapter write ────────────────────────────────────────────

@app.post("/api/write-stream")
async def write_stream(request: Request):
    """SSE streaming chapter generation with full parameter support.
    Query params: ?mode=agent (standard/deep 模式使用多 Agent 流水线)"""
    data = await request.json()
    volume = data.get("volume", 1)
    chapter = data.get("chapter", 1)
    use_agent = request.query_params.get("mode") == "agent"

    async def generate() -> AsyncGenerator[str, None]:
        import json as _json

        cfg = load_cfg()
        gen = cfg.get("generation", {})
        wf_mode = cfg.get("workflow", {}).get("mode", "quick")

        yield "data: " + _json.dumps({"type": "status", "msg": f"正在生成第{volume}卷第{chapter}章... (模式: {wf_mode})"}, ensure_ascii=False) + "\n\n"

        try:
            from scene_writer import build_chapter_prompt
            from utils.config import MANUSCRIPTS_DIR
            from utils.llm_client import _get_client, get_task_client, get_task_model, _llm_temperature, _llm_frequency_penalty, _llm_presence_penalty, _llm_top_p

            # ── 多 Agent 流水线（standard/deep 模式） ──
            if use_agent and wf_mode in ("standard", "deep"):
                yield "data: " + _json.dumps({"type": "status", "msg": "启动多 Agent 协作流水线..."}, ensure_ascii=False) + "\n\n"

                from scene_writer import load_chapter_outline
                outline = load_chapter_outline(volume, chapter)
                if not outline:
                    yield "data: " + _json.dumps({"type": "error", "msg": "找不到章节大纲"}, ensure_ascii=False) + "\n\n"
                    return

                # 按阶段输出进度
                stages = ["Architect", "Scribe", "Editor", "Polisher", "Gatekeeper"]
                for i, stage in enumerate(stages):
                    yield "data: " + _json.dumps({"type": "agent_progress", "stage": stage, "progress": (i+1)/len(stages)}, ensure_ascii=False) + "\n\n"

                # 注入流派/风格到 outline，Agent 流水线各阶段都会看到
                genre_style = _build_genre_style_injection(cfg)
                if genre_style:
                    outline["_genre_style_injection"] = genre_style
                # 注入因果图上下文
                causal_ctx = _build_causal_context(chapter)
                if causal_ctx:
                    outline["_causal_context"] = causal_ctx

                from skills.wf_mo_shen_workflow.skill import WfMoShenWorkflowSkill
                from core.novel_context import NovelContext
                from utils.workspace import WorkspaceManager
                ctx = NovelContext(WorkspaceManager())
                wf = WfMoShenWorkflowSkill(ctx)
                wf._config = cfg
                wf.current_mode = wf_mode
                loop = asyncio.get_event_loop()
                pipeline_result = await loop.run_in_executor(None, wf.run_agent_pipeline, outline, chapter)

                full_content = pipeline_result["final_text"]
                gatekeeper = pipeline_result["gatekeeper_score"]
                yield "data: " + _json.dumps({
                    "type": "agent_result",
                    "score": gatekeeper.get("final_score", 0),
                    "dimensions": gatekeeper.get("dimensions", {}),
                    "revision_rounds": pipeline_result["revision_rounds"],
                }, ensure_ascii=False) + "\n\n"

                # Post-processing (hooks + quality gate)
                from scene_writer import post_process_chapter
                ch_file, gate_verdict, gate_guidance = post_process_chapter(
                    volume, chapter, full_content)
                yield "data: " + _json.dumps({
                    "type": "complete", "chapter": chapter,
                    "words": len(full_content), "path": str(ch_file),
                    "gate_verdict": gate_verdict or "none",
                }, ensure_ascii=False) + "\n\n"
                return

            # ── 单 LLM 流水线（quick 模式） ──
            client = get_task_client("writing")
            model = get_task_model("writing")
            prompt = build_chapter_prompt(volume, chapter)
            if not prompt:
                yield "data: " + _json.dumps({"type": "error", "msg": "找不到章节大纲"}, ensure_ascii=False) + "\n\n"
                return

            # 使用新参数
            temp = _llm_temperature("writing")
            freq_pen = _llm_frequency_penalty("writing")
            pres_pen = _llm_presence_penalty("writing")
            top_p = _llm_top_p("writing")

            from utils.prompt_loader import writing_prompt, inject_style_reference
            system_prompt = writing_prompt() + _build_genre_style_injection(cfg)
            system_prompt = inject_style_reference(system_prompt, cfg.get("style", ""), cfg.get("genre", ""))
            system_prompt += _build_causal_context(chapter)
            # 用 Queue 在线程和事件循环之间传递 token
            token_queue: asyncio.Queue = asyncio.Queue()

            def sync_stream():
                """在线程中运行同步流式调用"""
                try:
                    stream = client.chat.completions.create(
                        model=model, temperature=temp,
                        frequency_penalty=freq_pen, presence_penalty=pres_pen,
                        top_p=top_p, max_tokens=8192, stream=True,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                        timeout=300,  # 5分钟超时
                    )
                    for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            token_queue.put_nowait(("token", chunk.choices[0].delta.content))
                    token_queue.put_nowait(("done", None))
                except Exception as e:
                    token_queue.put_nowait(("error", str(e)))

            # 在线程池中运行
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(None, sync_stream)

            # 从主事件循环消费 token
            timeout_seconds = 360  # 6分钟总超时
            deadline = asyncio.get_event_loop().time() + timeout_seconds
            full_content = ""

            try:
                while True:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        yield "data: " + _json.dumps({"type": "error", "msg": "生成超时（6分钟）"}, ensure_ascii=False) + "\n\n"
                        break
                    try:
                        kind, value = await asyncio.wait_for(token_queue.get(), timeout=min(remaining, 30))
                    except asyncio.TimeoutError:
                        # 30秒没新 token，检查是否完成，发心跳保活
                        if future.done():
                            break
                        yield ": heartbeat\n\n"
                        continue
                    if kind == "token":
                        full_content += value
                        yield "data: " + _json.dumps({"type": "stream", "text": value}, ensure_ascii=False) + "\n\n"
                    elif kind == "done":
                        break
                    elif kind == "error":
                        yield "data: " + _json.dumps({"type": "error", "msg": value}, ensure_ascii=False) + "\n\n"
                        return
            except Exception as e:
                yield "data: " + _json.dumps({"type": "error", "msg": f"生成异常: {str(e)}"}, ensure_ascii=False) + "\n\n"
                return

            # Post-processing
            if full_content:
                def sync_post():
                    from scene_writer import post_process_chapter
                    return post_process_chapter(volume, chapter, full_content)
                ch_file, gate_verdict, _ = await asyncio.to_thread(sync_post)
                yield "data: " + _json.dumps({
                    "type": "done", "chapter": chapter, "words": len(full_content),
                    "path": str(ch_file), "gate_verdict": gate_verdict or "none",
                }, ensure_ascii=False) + "\n\n"
                yield "data: " + _json.dumps({
                    "type": "complete", "chapter": chapter, "words": len(full_content),
                }, ensure_ascii=False) + "\n\n"
            else:
                yield "data: " + _json.dumps({"type": "error", "msg": "生成返回空内容"}, ensure_ascii=False) + "\n\n"
        except Exception as e:
            yield "data: " + _json.dumps({"type": "error", "msg": str(e)}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── file editing (世界观 / 大纲 / 人物) ─────────────────────────────────

_WORKSPACE_FILES = ["世界观.md", "大纲.md", "人物.md"]

@app.get("/api/files/list")
async def list_files():
    """List editable markdown files in the workspace"""
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    files = []
    # Look for .md files in base dir + subdirs
    for md in sorted(base.rglob("*.md")):
        rel = str(md.relative_to(base))
        size = md.stat().st_size if md.exists() else 0
        files.append({"name": rel, "path": str(md), "size": size})
    # Also look for templates in the workspace root
    for fn in _WORKSPACE_FILES:
        fp = base / fn
        if fp.exists() and fn not in [f["name"] for f in files]:
            files.append({"name": fn, "path": str(fp), "size": fp.stat().st_size})
    return {"files": files}

@app.get("/api/files/read")
async def read_file(name: str = ""):
    """Read a markdown file from the workspace"""
    if not name:
        return {"error": "name required"}
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    fp = base / name
    # Security: ensure path stays within workspace
    try:
        fp.resolve().relative_to(base.resolve())
    except ValueError:
        return {"error": "invalid path"}
    if not fp.exists():
        return {"content": "", "name": name}
    return {"content": fp.read_text(encoding="utf-8"), "name": name}

@app.post("/api/files/write")
async def write_file(request: Request):
    """Write content to a markdown file. Auto-compiles 世界观 if writing to 设定/*"""
    data = await request.json()
    name = data.get("name", "")
    content = data.get("content", "")
    if not name:
        return {"error": "name required"}
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    fp = base / name
    try:
        fp.resolve().relative_to(base.resolve())
    except ValueError:
        return {"error": "invalid path"}
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")

    # Auto-compile: if writing to 设定/*, rebuild 世界观.md
    if name.startswith("设定/") and not name.endswith("世界观.md"):
        _compile_world(base)

    return {"ok": True, "name": name, "size": len(content)}

def _compile_world(base: Path):
    """Auto-compile 设定/*.md into 世界观.md"""
    settings_dir = base / "设定"
    world_file = base / "世界观.md"
    header = ""
    if world_file.exists():
        # Keep header (before first ##) from existing 世界观
        old = world_file.read_text(encoding="utf-8")
        header_end = old.find("\n## ")
        if header_end > 0:
            header = old[:header_end].strip()
    if not header:
        novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
        header = f"# 世界观: {novel_dir}\n\n> 自动编译自 设定/ 目录 · {_now()}"

    sections = []
    # Read all .md files in 设定/, sorted by name
    if settings_dir.exists():
        for fp in sorted(settings_dir.glob("*.md")):
            text = fp.read_text(encoding="utf-8").strip()
            if text:
                sections.append(text)

    compiled = header + "\n\n" + "\n\n---\n\n".join(sections) if sections else header
    world_file.write_text(compiled, encoding="utf-8")

def _extract_port(base_url: str) -> int:
    """Safely extract port from a URL string."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(base_url)
        if parsed.port:
            return parsed.port
        # Fallback: try to parse from netloc
        return 0
    except Exception:
        return 0

def _now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M")

@app.post("/api/files/generate")
async def generate_file(request: Request):
    """AI generates content for a setting or character file, streaming back.
    Body: { name, topic, genre?, instructions? }"""
    data = await request.json()
    name = data.get("name", "")
    topic = data.get("topic", "")
    instructions = data.get("instructions", "")
    genre = data.get("genre", load_cfg().get("genre", "玄幻"))

    # Determine type
    if "人物/" in name:
        doc_type = "人物档案"
        example = CHARACTER_EXAMPLE
    elif "设定/" in name:
        doc_type = "世界观设定"
        example = ""
    elif "大纲" in name:
        doc_type = "小说大纲"
        example = ""
    else:
        doc_type = "文档"
        example = ""

    from utils.llm_client import get_client_for, get_task_model, _llm_temperature, _llm_frequency_penalty, _llm_presence_penalty, _llm_top_p
    client = _get_task_client("planning")  # 设定/人物策划用 Qwen3.6

    planning_ref = _planning_ref()
    planning_context = f"\n\n**写作参考（市场趋势+写作技巧+叙事手法，必须参考融入设计）:**\n{planning_ref[:3000]}" if planning_ref else ""

    from utils.prompt_loader import planning_prompt
    system_prompt = planning_prompt() + f"""

当前任务：生成一份详细的{doc_type}

小说类型：{genre}
当前主题：{topic}
用户要求：{instructions}
{planning_context}

要求：
- 结构完整，参考网文行规
- 细节丰富，不要空洞
- 如果是人物：含基本信息、外貌、心理、背景、成长路线、金手指、战斗风格、关键关系
- 如果是世界观设定：按设定主题展开，如修炼体系要有境界划分、功法等级、突破规则
- 如果是大纲：三幕结构，每章概要
{example}

直接输出完整的{doc_type}内容，不要解释。"""

    async def generate():
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if instructions:
                messages.append({"role": "user", "content": f"生成一份{genre}小说的{doc_type}：{topic}\n\n具体要求：{instructions}"})
            else:
                messages.append({"role": "user", "content": f"生成一份{genre}小说的{doc_type}：{topic}"})

            stream = client.chat.completions.create(
                model=get_task_model("planning"),
                temperature=_llm_temperature("planning"),
                frequency_penalty=_llm_frequency_penalty("planning"),
                presence_penalty=_llm_presence_penalty("planning"),
                top_p=_llm_top_p("planning"),
                messages=messages,
                max_tokens=4096,
                stream=True,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

CHARACTER_EXAMPLE = """
示例参考（完整人物档案）：

# 角色档案: 萧炎

## 基本信息
- **全名**: 萧炎
- **别名/称号**: 炎帝、药尊者传人
- **年龄**: 15→25
- **身份/职业**: 萧家三少爷 → 炎盟盟主 → 炎帝
- **角色定位**: 主角
- **所处境界**: 斗者→斗帝

## 外貌特征
- **身高体型**: 修长挺拔，习武之人体态
- **容貌特征**: 清秀中带着坚毅，黑发黑瞳
- **标志性装扮**: 黑袍，背负玄重尺
- **气质/第一印象**: 初见沉稳内敛，实则锋芒暗藏

## 心理特征
- **核心欲望**: 变强，夺回失去的一切，守护所爱之人
- **外在目标**: 收集异火，突破斗帝
- **深层恐惧**: 再次失去力量沦为废人
- **性格优点**: 坚韧不拔、重情重义、智勇双全
- **性格缺点**: 有时过于冒险、对敌人不够狠辣
- **盲点**: 容易低估自己的影响力

## 背景故事
- **出身**: 乌坦城萧家三少爷，天才少年
- **关键事件**: 11岁成为斗者 → 12岁突然失去斗气沦为废材 → 遇药老觉醒 → 三年之约
- **核心创伤**: 从天才坠落为废材，被未婚妻退婚的耻辱

## 成长路线
- **起点状态**: 废材少爷，被所有人嘲笑
- **关键转折**: 遇到药老，觉醒炼药天赋，重获力量
- **最终状态**: 炎帝，大陆最强者

## 关键关系
| 角色 | 关系 | 互动模式 | 当前状态 |
| 药老 | 师徒 | 亦师亦友，灵魂寄居 | 灵魂体 |
| 萧熏儿 | 青梅竹马→恋人 | 互相守护 | 古族 |
| 纳兰嫣然 | 前未婚妻→和解 | 三年之约→释怀 | 云岚宗 |
| 美杜莎 | 敌人→盟友→妻子 | 从对峙到信任 | 蛇人族女王 |

## 特殊能力 / 金手指
- **能力名称**: 焚诀 + 炼药术
- **来源**: 药老传授
- **效果**: 可吞噬异火进化功法
- **限制/代价**: 每次吞噬异火需承受极大痛苦

## 战斗风格
- **常用招式**: 八极崩、焰分噬浪尺、佛怒火莲
- **战斗习惯**: 越级挑战，绝境爆发
- **弱点**: 前期斗气不足时易被消耗战拖垮

## 语言风格
- **口头禅**: "三十年河东三十年河西，莫欺少年穷"
- **说话节奏**: 平时淡然，战斗时凌厉
"""


@app.post("/api/files/delete")
async def delete_file(name: str = ""):
    """Delete a file from the workspace"""
    if not name:
        return {"error": "name required"}
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    fp = base / name
    try:
        fp.resolve().relative_to(base.resolve())
    except ValueError:
        return {"error": "invalid path"}
    if fp.exists():
        fp.unlink()
        return {"ok": True, "deleted": name}
    return {"ok": True, "deleted": name, "note": "file did not exist"}

@app.post("/api/files/revise")
async def revise_file(request: Request):
    """AI iterative revision — user sends current content + instruction,
    model streams back revised version. Supports multi-turn conversation."""
    data = await request.json()
    name = data.get("name", "")
    current_content = data.get("content", "")
    instruction = data.get("instruction", "")
    history = data.get("history", [])  # previous turns: [{role, content}, ...]
    if not instruction:
        return {"error": "instruction required"}

    # Determine document type for better prompting
    doc_type = "文档"
    if "世界观" in name or "world" in name.lower():
        doc_type = "世界观设定"
    elif "大纲" in name or "outline" in name.lower():
        doc_type = "小说大纲"
    elif "人物" in name or "char" in name.lower():
        doc_type = "人物档案"
    elif "章节" in name or "chapter" in name.lower() or "ch_" in name:
        doc_type = "小说章节"

    from utils.llm_client import get_client_for
    client = _get_task_client("writing")  # 正文修改用 Gemma4

    from utils.prompt_loader import editing_prompt
    system_prompt = editing_prompt() + f"""

当前任务：用户要修改一份{doc_type}文档。
规则：
1. 只修改用户指定的部分，其他部分保持不变
2. 如果用户要求润色/扩展某个段落，保留原有结构
3. 输出完整的修改后文档，不要省略
4. 如果是人物档案，注意保持网文风格（含修炼境界、金手指等元素）
5. 如果是世界观，注意保持修炼体系、势力分布等设定的一致性
6. 直接输出修改后的内容，不要解释你改了什么"""

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-6:]:  # last 6 turns for context
        messages.append(h)
    messages.append({"role": "user", "content": f"当前{doc_type}内容：\n\n{current_content[-8000:]}\n\n修改指令：{instruction}\n\n请输出修改后的完整{doc_type}："})

    async def generate():
        try:
            stream = client.chat.completions.create(
                model=get_task_model("planning"),
                temperature=_llm_temperature("planning"),
                frequency_penalty=_llm_frequency_penalty("planning"),
                presence_penalty=_llm_presence_penalty("planning"),
                top_p=_llm_top_p("planning"),
                messages=messages,
                max_tokens=4096,
                stream=True,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

# ── model cache ──────────────────────────────────────────────────────────
_models_cache: dict = {}
_models_cache_ts: float = 0.0
_MODELS_CACHE_TTL: float = 30.0  # 30 秒内不重复扫描端口


# ── model discovery & switching ──────────────────────────────────────────

@app.get("/api/models")
async def discover_models():
    """Auto-discover all loaded models by scanning configured LM Studio ports.
    Calls /v1/models on each port, matches against config alt_models keys.
    结果缓存 30 秒，避免每次打开页面都扫描端口。"""
    global _models_cache, _models_cache_ts
    import time as _time
    now = _time.time()

    # 缓存命中：直接返回
    if _models_cache and (now - _models_cache_ts) < _MODELS_CACHE_TTL:
        return _models_cache

    import httpx
    cfg = load_cfg()
    scan_ports = cfg.get("llm", {}).get("scan_ports", [61183])
    default_key = cfg.get("llm", {}).get("default_model", "")
    alt = cfg.get("llm", {}).get("alt_models", {})
    models = {}
    discovered_default = None
    # Track seen keys to dedup (prefer shorter model IDs)
    seen_key_ids = {}

    for port in scan_ports:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"http://127.0.0.1:{port}/v1/models")
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("data", []):
                        mid = m.get("id", "")
                        if _is_ignored_model(mid): continue
                        key = _model_key_from_id(mid, port)
                        # Use alt_model label if key matches alt_models
                        label = mid  # use original model ID directly
                        # Dedup: prefer shorter model_id (e.g. 'qwen3.6-27b' over 'qwen/qwen3.6-27b')
                        if key in seen_key_ids:
                            prev = seen_key_ids[key]
                            if len(mid) < len(prev):
                                models[key] = {
                                    "key": key, "id": mid, "label": label,
                                    "port": port, "base_url": f"http://127.0.0.1:{port}/v1",
                                }
                                seen_key_ids[key] = mid
                            # else: keep previous (shorter id)
                            continue
                        models[key] = {
                            "key": key, "id": mid, "label": label,
                            "port": port, "base_url": f"http://127.0.0.1:{port}/v1",
                        }
                        seen_key_ids[key] = mid
                        if not discovered_default:
                            discovered_default = key
        except Exception:
            pass

    # Fallback: only use hardcoded alt_models if scan found nothing
    if not models:
        for key, cfg_m in alt.items():
            models[key] = {
                "key": key,
                "id": cfg_m.get("id", key),
                "label": cfg_m.get("label", key),
                "port": _extract_port(cfg_m.get("base_url", "")),
                "base_url": cfg_m.get("base_url", ""),
            }

    # Determine default
    if default_key and default_key in models:
        active_default = default_key
    elif discovered_default:
        active_default = discovered_default
    else:
        active_default = list(models.keys())[0] if models else ""

    task_models = cfg.get("llm", {}).get("task_models", {})
    result = {"models": models, "default": active_default, "task_models": task_models}
    # 写入缓存
    _models_cache = result
    _models_cache_ts = now
    return result

def _model_key_from_id(model_id: str, port: int) -> str:
    """Derive a short key from a model ID, preferring config alt_models match."""
    # Common prefixes to strip
    prefixes = ["openai/", "qwen/", "lmstudio-community/", "bartowski/",
                "tripolskypetr/", "HauhauCS/", "wcn123/", "kldzj/", "huggingface/"]
    mid = model_id.lower()
    for p in prefixes:
        mid = mid.replace(p, "")
    mid = mid.replace("-gguf", "")
    parts = mid.split("-")
    # Match against alt_models keywords
    alt_match = _match_alt_model(mid)
    if alt_match:
        return alt_match
    # Use first 2-3 meaningful segments
    short = "-".join(parts[:3]) if len(parts) >= 3 else "-".join(parts)
    return short.replace("_", "-")

def _match_alt_model(model_id_lower: str) -> str | None:
    """Try to match a discovered model ID to a config alt_models key.
    Returns the alt_model key if matched, None otherwise."""
    cfg = load_cfg()
    alt = cfg.get("llm", {}).get("alt_models", {})
    mid = model_id_lower
    # Ordered matching: more specific patterns first
    patterns = [
        ("coder_next", ["coder-next"]),
        ("coder_next", ["qwen3-coder-next"]),
        ("qwen3.6", ["qwen3.6", "27b"]),  # standard dense 27B (not aggressive variant)
        ("qwen3.6_aggressive", ["qwen3.6", "uncensored", "aggressive"]),
        ("gemma4", ["gemma4"]),
    ]
    for alt_key, must_have in patterns:
        if alt_key in alt and all(kw in mid for kw in must_have):
            return alt_key
    return None

def _get_task_client(task: str):
    """Get LLM client for a specific task type (planning/writing/reasoning).
    Delegates to llm_client.get_task_client()."""
    from utils.llm_client import get_task_client
    return get_task_client(task)

def _is_ignored_model(model_id: str) -> bool:
    """Filter out models that are useless for writing (embeddings, etc)."""
    ignore_kw = ["embedding", "nomic", "embed", "text-embedding"]
    mid = model_id.lower()
    for kw in ignore_kw:
        if kw in mid:
            return True
    return False

@app.post("/api/models/switch")
async def switch_model(request: Request):
    """Switch the active model. Updates config.json with model key and base_url."""
    data = await request.json()
    model_key = data.get("model", "")
    if not model_key:
        return {"error": "model key required"}

    # Re-discover models to get the port for this key
    cfg = load_cfg()
    scan_ports = cfg.get("llm", {}).get("scan_ports", [61183])

    # First check alt_models
    alt = cfg.get("llm", {}).get("alt_models", {})
    if model_key in alt:
        base_url = alt[model_key].get("base_url", "")
    else:
        # Try to find from scan
        import httpx
        base_url = ""
        for port in scan_ports:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"http://127.0.0.1:{port}/v1/models")
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("data", []):
                            if _model_key_from_id(m["id"], port) == model_key:
                                base_url = f"http://127.0.0.1:{port}/v1"
                                break
                if base_url:
                    break
            except Exception:
                pass

    if not base_url:
        return {"error": f"cannot find port for model: {model_key}"}

    from utils.llm_client import switch_default_model
    ok = switch_default_model(model_key, base_url)
    if ok:
        return {"ok": True, "active_model": model_key, "base_url": base_url}
    return {"error": "switch failed"}

@app.post("/api/models/task")
async def update_task_model(request: Request):
    """Update the model assigned to a specific task (planning/writing/reasoning).
    Setting model to null/empty removes the override (falls back to task_models default)."""
    data = await request.json()
    task = data.get("task", "")
    model_key = data.get("model")  # None or "" means clear override

    if task not in ("planning", "writing", "reasoning"):
        return {"error": "task must be planning/writing/reasoning"}

    cfg = load_cfg()
    task_models = cfg.setdefault("llm", {}).setdefault("task_models", {})

    if model_key:
        task_models[task] = model_key
    else:
        task_models.pop(task, None)  # Clear override

    # Write back to config.json
    cfg_path = Path(__file__).parent.parent / "config.json"
    import json as _json
    with open(cfg_path, "w", encoding="utf-8") as f:
        _json.dump(cfg, f, ensure_ascii=False, indent=2)

    return {"ok": True, "task": task, "model": model_key, "task_models": task_models}

# ── structured outline (JSON + Markdown) ───────────────────────────────

def _outline_path(base: Path) -> tuple:
    """Returns (json_path, md_path) for outline."""
    return base / "大纲.json", base / "大纲.md"

def _default_outline(chapter_target=3000):
    return {
        "title": "",
        "chapter_target_words": chapter_target,
        "total_target_words": 0,
        "volumes": [
            {"number": 1, "name": "第一卷", "chapter_count": 200,
             "chapter_start": 1, "purpose": "",
             "chapters_list": [_empty_chapter(i, chapter_target) for i in range(1, 201)]},
        ]
    }

def _empty_chapter(num, target_words=3000):
    return {
        "number": num, "title": "", "pov": "", "status": "planned",
        "word_target": target_words, "summary": "",
        "scenes": [], "satisfaction_beat": "", "emotional_beat": "", "ending_hook": "",
        "plot_advances": [], "character_moments": {}
    }

def _outline_to_markdown(outline):
    """Convert structured JSON outline to readable Markdown."""
    total_words = outline.get("total_target_words", 0)
    total_words_str = f"{total_words:,}字" if total_words > 0 else "未设置上限"
    total_chaps = sum(v.get("chapter_count", 0) for v in outline.get("volumes", []))
    lines = [
        f"# 大纲: {outline.get('title', '')}",
        f"**总目标字数**: {total_words_str} | **总章节数**: {total_chaps}章 | **每章目标**: {outline.get('chapter_target_words', 3000)}字",
        ""
    ]
    for vol in outline.get("volumes", []):
        done = sum(1 for c in vol.get("chapters_list", []) if c.get("summary"))
        lines.append(f"## {vol.get('name', '')} ({vol.get('chapter_start', 1)}-{vol.get('chapter_start', 1) + vol.get('chapter_count', 0) - 1}章)")
        if vol.get("purpose"):
            lines.append(f"**目的**: {vol['purpose']}")
        lines.append(f"**进度**: {done}/{vol.get('chapter_count', 0)}")
        lines.append("")
        lines.append("| 章 | 标题 | POV | 概要 | 爽点 | 钩子 | 状态 |")
        lines.append("|---|------|-----|------|------|------|------|")
        for ch in vol.get("chapters_list", []):
            status = {"planned":"计划","outlined":"已规划","detailed":"细纲","writing":"写作中","done":"完成"}.get(ch.get("status",""), ch.get("status",""))
            lines.append(f"| {ch['number']} | {ch.get('title','')[:15]} | {ch.get('pov','')[:8]} | {ch.get('summary','')[:30]} | {ch.get('satisfaction_beat','')[:15]} | {ch.get('ending_hook','')[:20]} | {status} |")
        lines.append("")
    return "\n".join(lines)

@app.get("/api/outline")
async def get_outline():
    """Get structured outline as JSON."""
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    jp, mp = _outline_path(base)
    if jp.exists():
        return json.loads(jp.read_text(encoding="utf-8"))
    # Fallback: try markdown
    if mp.exists():
        return {"_source": "markdown", "markdown": mp.read_text(encoding="utf-8")}
    return _default_outline()

@app.post("/api/outline")
async def save_outline(request: Request):
    """Save structured outline + auto-generate markdown. Skips write if unchanged."""
    import hashlib
    data = await request.json()
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    jp, mp = _outline_path(base)
    # Remove _source marker
    data.pop("_source", None)
    data.pop("markdown", None)
    new_json = json.dumps(data, ensure_ascii=False, indent=2)
    # 对比哈希，无变化则跳过写盘
    if jp.exists():
        old_hash = hashlib.sha256(jp.read_bytes()).hexdigest()
        new_hash = hashlib.sha256(new_json.encode("utf-8")).hexdigest()
        if old_hash == new_hash:
            return {"ok": True, "unchanged": True}
    jp.write_text(new_json, encoding="utf-8")
    # Auto-generate markdown
    md = _outline_to_markdown(data)
    mp.write_text(md, encoding="utf-8")
    return {"ok": True}

@app.post("/api/outline/generate-chapter")
async def generate_chapter_outline(request: Request):
    """AI generates detailed outline for a single chapter. SSE streaming."""
    data = await request.json()
    chap_num = data.get("chapter", 1)
    genre = load_cfg().get("genre", "玄幻")
    novel_title = load_cfg().get("workspace", {}).get("novel_name", "")

    # Read world context
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    world_ctx = ""
    world_file = base / "世界观.md"
    if world_file.exists():
        world_ctx = world_file.read_text(encoding="utf-8")[:2000]

    from utils.llm_client import get_client_for, get_task_model, _llm_temperature, _llm_frequency_penalty, _llm_presence_penalty, _llm_top_p
    client = _get_task_client("planning")  # 设定/人物策划用 Qwen3.6

    planning_ref = _planning_ref()
    planning_context = f"\n\n写作参考（市场趋势+技巧+叙事）：\n{planning_ref[:3000]}" if planning_ref else ""

    system_prompt = f"""你是专业的网文细纲设计师。为第{chap_num}章生成详细写作细纲。

小说：{novel_title} | 类型：{genre}
世界观参考：{world_ctx[:1500]}{planning_context}

输出格式：
# 第{chap_num}章: [章节标题]

## 本章概要
[2-3句话概括本章核心剧情]

## 场景分解
### 场景1: [场景名]
- **地点**:
- **角色出席**:
- **POV视角**:
- **目标**:
- **冲突**:
- **结局**:
- **字数分配**: ~[800]字

### 场景2: [场景名]
...

## 本章爽点
- [列出本章的读者爽点/燃点]

## 情感节奏
- [情绪曲线：开端→发展→高潮→回落]

## 伏笔管理
- **埋下**:
- **回收**:

## 章末钩子
[悬念/反转/期待——让读者必须点下一章]

## 写作提示
- 对话占40-60%
- 节奏：快→慢→快
- 注意：不要写成流水账，每个场景要有冲突和推进"""

    async def generate():
        try:
            user_msg = f"请为第{chap_num}章生成详细写作细纲。字数目标：3000字。"
            stream = client.chat.completions.create(
                model=get_task_model("planning"),
                temperature=_llm_temperature("planning"),
                frequency_penalty=_llm_frequency_penalty("planning"),
                presence_penalty=_llm_presence_penalty("planning"),
                top_p=_llm_top_p("planning"),
                max_tokens=3072, stream=True,
                messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_msg}],
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield f"data: {json.dumps({'text': chunk.choices[0].delta.content}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/outline/add-volume")
async def add_volume(request: Request):
    """Add a new volume to the outline."""
    data = await request.json()
    name = data.get("name", "")
    chapter_count = data.get("chapter_count", 100)

    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    jp, mp = _outline_path(base)

    outline = {}
    if jp.exists():
        outline = json.loads(jp.read_text(encoding="utf-8"))
    else:
        outline = _default_outline()

    volumes = outline.get("volumes", [])
    last_vol = volumes[-1] if volumes else None
    start_chap = (last_vol["chapter_start"] + last_vol["chapter_count"]) if last_vol else 1
    vol_num = len(volumes) + 1

    cpt = outline.get("chapter_target_words", 3000)
    new_vol = {
        "number": vol_num, "name": name or f"第{vol_num}卷",
        "chapter_count": chapter_count, "chapter_start": start_chap,
        "purpose": data.get("purpose", ""),
        "chapters_list": [_empty_chapter(i, cpt) for i in range(start_chap, start_chap + chapter_count)]
    }
    volumes.append(new_vol)
    outline["volumes"] = volumes

    jp.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
    mp.write_text(_outline_to_markdown(outline), encoding="utf-8")
    return {"ok": True, "volume": vol_num, "chapters": f"{start_chap}-{start_chap + chapter_count - 1}"}

# ── foreshadowing management ────────────────────────────────────────────

def _foreshadowing_path(base: Path):
    return base / "伏笔.json"

def _load_foreshadowing(base: Path):
    fp = _foreshadowing_path(base)
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8"))
    return {"items": []}

def _save_foreshadowing(base: Path, data):
    _foreshadowing_path(base).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

@app.get("/api/foreshadowing")
async def get_foreshadowing():
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    data = _load_foreshadowing(base)
    items = data.get("items", [])
    # Stats
    planted = sum(1 for i in items if i.get("status") == "planted")
    resolved = sum(1 for i in items if i.get("status") == "resolved")
    abandoned = sum(1 for i in items if i.get("status") == "abandoned")
    return {"items": items, "stats": {"planted": planted, "resolved": resolved, "abandoned": abandoned, "total": len(items)}}

@app.post("/api/foreshadowing")
async def save_foreshadowing(request: Request):
    data = await request.json()
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    _save_foreshadowing(base, data)
    return {"ok": True}

@app.get("/api/foreshadowing/for-chapter")
async def foreshadowing_for_chapter(chapter: int = 0):
    """Get foreshadowing relevant to a chapter: planted here + needing resolution + recently resolved"""
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    items = _load_foreshadowing(base).get("items", [])
    relevant = {
        "planted_here": [i for i in items if i.get("planted_in") == chapter],
        "needs_resolve": [i for i in items if i.get("status") == "planted" and i.get("target_resolve", 9999) <= chapter],
        "upcoming": [i for i in items if i.get("status") == "planted" and i.get("target_resolve", 0) <= chapter + 10 and i.get("target_resolve", 0) > chapter],
    }
    return relevant

@app.post("/api/foreshadowing/generate")
async def generate_foreshadowing(request: Request):
    """AI scans a chapter for potential foreshadowing and suggests entries."""
    data = await request.json()
    chapter_num = data.get("chapter", 0)
    chapter_content = data.get("content", "")

    if not chapter_content:
        return {"error": "chapter content required"}

    from utils.llm_client import get_client_for, get_task_model, _llm_temperature, _llm_frequency_penalty, _llm_presence_penalty, _llm_top_p
    client = get_task_client("reasoning")  # 伏笔检测用推理模型

    system_prompt = f"""你是专业的网文编辑，擅长识别和管理伏笔。请扫描以下第{chapter_num}章内容，找出其中可能埋下的伏笔。

对每个伏笔：
- 简短描述（20字以内）
- 类型：人物身世/功法秘密/势力伏笔/感情线/未解之谜/其他
- 建议回收章节（估算）

输出JSON格式：
[{{"description":"...","type":"...","target_resolve":数字}}]

如果没有明显伏笔，返回空数组 []。"""

    try:
        response = client.chat.completions.create(
            model=get_task_model("reasoning"),
            temperature=_llm_temperature("reasoning"),
            frequency_penalty=_llm_frequency_penalty("reasoning"),
            presence_penalty=_llm_presence_penalty("reasoning"),
            top_p=_llm_top_p("reasoning"),
            max_tokens=1024,
            messages=[
                {"role":"system","content":system_prompt},
                {"role":"user","content":chapter_content[-6000:]}
            ],
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        content = response.choices[0].message.content
        # Try to parse JSON from response
        import re
        match = re.search(r'\[[\s\S]*\]', content)
        if match:
            suggestions = json.loads(match.group())
            # Save them
            novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
            base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
            all_data = _load_foreshadowing(base)
            items = all_data.get("items", [])
            for s in suggestions:
                items.append({
                    "id": f"fs_{len(items) + 1:04d}",
                    "description": s.get("description", ""),
                    "type": s.get("type", "其他"),
                    "planted_in": chapter_num,
                    "target_resolve": s.get("target_resolve", chapter_num + 50),
                    "resolved_in": None,
                    "status": "planted",
                    "related_chars": [],
                    "notes": "",
                    "created": _now(),
                    "resolved_date": None,
                })
            all_data["items"] = items
            _save_foreshadowing(base, all_data)
            return {"ok": True, "found": len(suggestions), "suggestions": suggestions}
        return {"ok": True, "found": 0, "raw": content[:500]}
    except Exception as e:
        return {"error": str(e)}

# ── search & export ─────────────────────────────────────────────────────

@app.get("/api/search")
async def search_chapters(q: str = "", limit: int = 30):
    """Full-text search across all manuscript chapters."""
    if not q or len(q) < 1:
        return {"results": [], "total": 0, "query": q}

    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    ms_dir = base / "manuscripts"
    if not ms_dir.exists():
        return {"results": [], "total": 0, "query": q}

    results = []
    for vol_dir in sorted(ms_dir.iterdir()):
        if not vol_dir.is_dir(): continue
        vol_name = vol_dir.name.replace("vol_", "")
        for ch_file in sorted(vol_dir.glob("ch_*_final.md")):
            content = ch_file.read_text(encoding="utf-8")
            num = int(ch_file.stem.split("_")[1])
            # Case-insensitive search
            idx = content.lower().find(q.lower())
            if idx >= 0:
                # Extract context snippet (100 chars before and after)
                start = max(0, idx - 80)
                end = min(len(content), idx + len(q) + 80)
                snippet = content[start:end]
                if start > 0: snippet = "..." + snippet
                if end < len(content): snippet = snippet + "..."

                # Count total occurrences
                count = content.lower().count(q.lower())

                # Find chapter title
                title = ""
                for line in content.split("\n"):
                    if line.startswith("# ") and "章" in line:
                        title = line.strip("# ").strip()
                        break

                results.append({
                    "volume": f"第{vol_name}卷" if vol_name.isdigit() else vol_name,
                    "chapter": num,
                    "title": title,
                    "file": ch_file.name,
                    "snippet": snippet,
                    "match_count": count,
                    "position": idx,
                })

    results.sort(key=lambda r: (r["volume"], r["chapter"]))
    total = len(results)
    results = results[:limit]

    return {"results": results, "total": total, "query": q, "shown": len(results)}

@app.get("/api/export")
async def export_novel(fmt: str = "md"):
    """Export entire novel as a single file."""
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    title = load_cfg().get("workspace", {}).get("novel_name", "未命名小说")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    ms_dir = base / "manuscripts"

    if not ms_dir.exists():
        return {"error": "no manuscripts found"}

    # Collect all chapters in order
    all_chapters = []
    total_words = 0
    for vol_dir in sorted(ms_dir.iterdir()):
        if not vol_dir.is_dir(): continue
        for ch_file in sorted(vol_dir.glob("ch_*_final.md")):
            content = ch_file.read_text(encoding="utf-8")
            all_chapters.append(content)
            total_words += len(content.replace(" ", "").replace("\n", ""))

    if fmt == "txt":
        output = "\n\n".join(all_chapters)
        media = "text/plain; charset=utf-8"
        filename = f"{title}.txt"
    else:
        # Markdown with table of contents
        toc = [f"# {title}", "", "## 目录", ""]
        for vol_dir in sorted(ms_dir.iterdir()):
            if not vol_dir.is_dir(): continue
            vol_name = f"第{vol_dir.name.replace('vol_', '')}卷"
            toc.append(f"### {vol_name}")
            for ch_file in sorted(vol_dir.glob("ch_*_final.md")):
                content = ch_file.read_text(encoding="utf-8")
                num = int(ch_file.stem.split("_")[1])
                title_line = ""
                for line in content.split("\n"):
                    if line.startswith("# ") and "章" in line:
                        title_line = line.strip("# ").strip()
                        break
                toc.append(f"- [第{num}章 {title_line}](#第{num}章)")
            toc.append("")
        output = "\n".join(toc) + "\n\n---\n\n" + "\n\n".join(all_chapters)
        media = "text/markdown; charset=utf-8"
        filename = f"{title}.md"

    from fastapi.responses import Response
    return Response(
        content=output.encode("utf-8"),
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ── chapter directory (browse completed chapters) ───────────────────────

@app.get("/api/chapters")
async def list_chapter_files(page: int = 0, size: int = 50):
    """List all written chapter files with metadata. Supports pagination with ?page=N&size=M.
    page=0 (default) returns all chapters (backward compat). page>=1 enables pagination."""
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    ms_dir = base / "manuscripts"
    if not ms_dir.exists():
        return {"volumes": [], "total_chapters": 0, "total_words": 0, "page": page, "has_more": False}

    # 收集全部章节
    all_volumes = []
    total_words = 0
    for vol_dir in sorted(ms_dir.iterdir()):
        if not vol_dir.is_dir(): continue
        chapters = []
        for ch_file in sorted(vol_dir.glob("ch_*_final.md")):
            content = ch_file.read_text(encoding="utf-8")
            num = int(ch_file.stem.split("_")[1])
            title = ""
            for line in content.split("\n"):
                if line.startswith("# ") and "章" in line:
                    title = line.strip("# ").strip()
                    break
            word_count = len(content.replace(" ", "").replace("\n", ""))
            total_words += word_count
            chapters.append({
                "number": num, "file": ch_file.name, "title": title,
                "word_count": word_count, "size": ch_file.stat().st_size,
                "last_modified": ch_file.stat().st_mtime,
            })
        if chapters:
            vol_num = vol_dir.name.replace("vol_", "")
            all_volumes.append({
                "name": f"第{int(vol_num)}卷" if vol_num.isdigit() else vol_dir.name,
                "dir": vol_dir.name,
                "chapters": chapters,
            })

    total_chapters = sum(len(v.get("chapters",[])) for v in all_volumes)

    # 分页模式：按章节平铺截取
    if page >= 1:
        # 将所有章节平铺为 (volume_index, chapter_index) 列表
        flat = []
        for vi, vol in enumerate(all_volumes):
            for ci, ch in enumerate(vol["chapters"]):
                flat.append((vi, ci))
        start = (page - 1) * size
        end = start + size
        page_items = flat[start:end]
        # 重建 volumes 结构（只含本页章节）
        paged_volumes = []
        last_vi = -1
        for vi, ci in page_items:
            if vi != last_vi:
                paged_volumes.append({
                    "name": all_volumes[vi]["name"],
                    "dir": all_volumes[vi]["dir"],
                    "chapters": [],
                })
                last_vi = vi
            paged_volumes[-1]["chapters"].append(all_volumes[vi]["chapters"][ci])
        return {
            "volumes": paged_volumes, "total_chapters": total_chapters,
            "total_words": total_words, "page": page, "has_more": end < len(flat),
        }

    return {"volumes": all_volumes, "total_chapters": total_chapters, "total_words": total_words, "page": 0, "has_more": False}

@app.get("/api/chapters/read")
async def read_chapter_file(vol: str = "", num: int = 0):
    """Read a specific chapter file."""
    if not vol or not num:
        return {"error": "vol and num required"}
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    fp = base / "manuscripts" / vol / f"ch_{num:03d}_final.md"
    if not fp.exists():
        return {"error": "file not found", "content": ""}
    content = fp.read_text(encoding="utf-8")
    # Find previous and next chapters
    prev_chap = base / "manuscripts" / vol / f"ch_{num-1:03d}_final.md"
    next_chap = base / "manuscripts" / vol / f"ch_{num+1:03d}_final.md"
    return {
        "content": content,
        "word_count": len(content.replace(" ", "").replace("\n", "")),
        "has_prev": prev_chap.exists(),
        "has_next": next_chap.exists(),
        "vol": vol, "number": num,
    }

# ── 因果图引擎 Web API ─────────────────────────────────────

@app.get("/api/causal-graph/summary")
async def causal_graph_summary():
    """获取因果图引擎概览"""
    try:
        novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
        novel_path = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
        if not (novel_path / "causal_graph.json").exists():
            return {"available": False}

        from core.causal_graph import CausalGraphEngine
        engine = CausalGraphEngine(novel_path)
        return {"available": True, **engine.get_summary()}
    except Exception as e:
        return {"available": False, "error": str(e)}


@app.get("/api/causal-graph/characters")
async def causal_graph_characters():
    """获取角色关系图数据（用于 D3 力导向图）"""
    try:
        novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
        novel_path = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
        if not (novel_path / "causal_graph.json").exists():
            return {"available": False}

        from core.causal_graph import CausalGraphEngine
        engine = CausalGraphEngine(novel_path)
        engine._ensure_characters_from_events()

        nodes = []
        links = []
        for c in engine.characters.values():
            nodes.append({
                "id": c.id,
                "name": c.name,
                "role": c.role or "unknown",
                "goalCount": len([g for g in c.goals if g.status == "active"]),
                "firstAppearance": c.first_appearance,
                "lastAppearance": c.last_appearance,
            })
            for rid, rel in c.relationships.items():
                if rid in engine.characters and c.id < rid:  # 避免重复边
                    links.append({
                        "source": c.id,
                        "target": rid,
                        "type": rel.rel_type,
                        "intensity": rel.intensity,
                        "historyCount": len(rel.history),
                    })

        return {"available": True, "nodes": nodes, "links": links}
    except Exception as e:
        return {"available": False, "error": str(e)}


@app.get("/api/causal-graph/events")
async def causal_graph_events(chapter: int = 0):
    """获取事件因果图数据"""
    try:
        novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
        novel_path = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
        if not (novel_path / "causal_graph.json").exists():
            return {"available": False}

        from core.causal_graph import CausalGraphEngine
        engine = CausalGraphEngine(novel_path)

        if chapter > 0:
            events = engine.get_chapter_events(chapter)
        else:
            events = sorted(engine.events.values(), key=lambda e: (e.chapter, e.id))[-50:]

        nodes = []
        links = []
        event_ids = set()
        for e in events:
            event_ids.add(e.id)
            nodes.append({
                "id": e.id,
                "chapter": e.chapter,
                "stac": e.stac_type,
                "summary": e.summary[:50],
                "participants": e.participants[:3],
                "emotional": e.emotional_valence,
            })

        # 边（只展示在所选集内的事件之间的因果链接）
        for e in events:
            for cause_id in e.causes:
                if cause_id in event_ids:
                    links.append({"source": cause_id, "target": e.id})

        threads = engine.get_active_threads()
        return {"available": True, "nodes": nodes, "links": links, "activeThreads": len(threads)}
    except Exception as e:
        return {"available": False, "error": str(e)}


# ── 通用改写（去AI味 + 自定义要求） ────────────────────────────

@app.post("/api/deai-rewrite")
async def deai_rewrite(request: Request):
    """AI rewrites selected text. When prompt is empty, defaults to de-AI rewrite.
    Otherwise user's instruction takes priority, de-AI analysis runs as reference."""
    data = await request.json()
    chapter_num = data.get("chapter", 1)
    content = data.get("content", "")
    full_text = data.get("full_text", content)
    user_prompt = data.get("prompt", "")
    if not full_text:
        return {"error": "content required"}

    # Run detection first
    import sys
    deai_path = Path(__file__).parent.parent
    if str(deai_path) not in sys.path:
        sys.path.insert(0, str(deai_path))
    from skills.gen_deai_engine.skill import GenDeaiEngineSkill

    class Ctx:
        def get_shared(self, k, d=None): return d
        def set_shared(self, k, v): pass

    engine = GenDeaiEngineSkill(Ctx())
    engine.on_init()
    detection = engine.analyze(full_text)

    # Build rewrite instructions based on detection (六层分析)
    issues = []
    for word, count in detection.get("flagged_words", {}).items():
        if count >= 3:
            issues.append(f"「{word}」出现{count}次，AI高频词")
    for pattern in list(detection.get("flagged_patterns", {}).keys())[:5]:
        issues.append(f"句式「{pattern}」模板化严重")
    # L3-L6 issues
    if detection.get("adj_density", {}).get("score", 100) < 50:
        issues.append(f"修饰词密度过高({detection['adj_density']['density']}/300字)")
    if detection.get("idiom_density", {}).get("score", 100) < 50:
        issues.append(f"四字成语堆砌({detection['idiom_density']['density']}/500字)")
    for issue in detection.get("para_variation", {}).get("issues", []):
        issues.append(issue)
    for issue in detection.get("punct_rhythm", {}).get("issues", []):
        issues.append(issue)

    issues_text = "\n".join(f"- {i}" for i in issues[:12]) if issues else "无显著问题"
    has_issues = len(issues) > 0

    from utils.llm_client import get_task_client, get_task_model, _llm_temperature, _llm_frequency_penalty, _llm_presence_penalty, _llm_top_p
    client = get_task_client("writing")
    model = get_task_model("writing")

    from utils.prompt_loader import polishing_prompt, inject_style_reference

    # ── 根据是否有用户 prompt 决定主任务 ──
    if user_prompt:
        # 用户自定义改写为主
        task_header = f"**当前任务：按作者要求改写文本**"
        user_section = f"""
**改写要求**：{user_prompt}
请优先满足此要求，这是本次改写的核心目标。"""
        deai_section = ""
        if has_issues:
            deai_section = f"""

**文本质检参考（非必需，如有帮助可参考）**：
{issues_text}

去AI味技巧（在满足改写要求的前提下酌情使用）：
- 删除AI高频词（不禁/缓缓/微微/顿时/忽然/仿佛/某种 等）
- 打破模板句式（嘴角上扬/心中一震/深吸一口气 等）
- 动作留白：只保留关键帧
- 情绪不直说，用动作和环境呈现"""

        system_prompt = polishing_prompt() + f"""
{task_header}
{user_section}
{deai_section}

输出原则：
- 保持原文剧情走向
- 只输出改写后的选中文本，不要解释"""
    else:
        # 默认：纯去AI味改写
        system_prompt = polishing_prompt() + f"""

**当前任务：去AI味改写**

检测到的问题（六层检测）：
{issues_text}

改写原则：
1. 删除AI高频词（不禁/缓缓/微微/顿时/忽然/仿佛/某种 等）
2. 打破模板句式（嘴角上扬/心中一震/深吸一口气/倒吸一口凉气 等）
3. 动作留白：只保留关键帧，删除中间过渡动作
4. 感官侵入：多写触觉/嗅觉/温度，少用视觉描述
5. 对话必须有意推进，每轮承载事实/规矩/代价之一
6. 情绪不直说，用动作和环境呈现
7. 保持原文剧情走向，直接输出改写后的完整正文"""

    system_prompt = inject_style_reference(system_prompt, cfg.get("style", ""), cfg.get("genre", ""))

    async def generate():
        try:
            mode = "按用户要求改写" if user_prompt else "去AI味改写"
            yield f"data: {json.dumps({'status': f'检测完成（发现 {len(issues)} 个AI特征）。{mode}，调用 {model}...'}, ensure_ascii=False)}\n\n"
            temp = _llm_temperature("deai")
            freq = _llm_frequency_penalty("deai")
            pres = _llm_presence_penalty("deai")
            tp = _llm_top_p("deai")
            stream = client.chat.completions.create(
                model=model, temperature=temp, frequency_penalty=freq,
                presence_penalty=pres, top_p=tp, max_tokens=min(len(full_text) * 2, 8192),
                stream=True,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"全文上下文（供参考，不需要改写）：\n{full_text[-3000:]}\n\n---\n请改写以下选中文本（只输出改写后的选中部分，保持与上下文的连贯）：\n\n{content[:8000]}"}
                ],
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield f"data: {json.dumps({'text': chunk.choices[0].delta.content}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'detection': detection}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/deai-rewrite/save")
async def save_deai_rewrite(request: Request):
    """Save deAI rewritten content directly to the manuscript file."""
    data = await request.json()
    chapter = data.get("chapter", 0)
    content = data.get("content", "")
    if not chapter or not content:
        return {"error": "chapter and content required"}
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    ms_dir = base / "manuscripts"
    if not ms_dir.exists():
        ms_dir.mkdir(parents=True, exist_ok=True)
    # Find which volume this chapter belongs to
    ch_num = int(chapter)
    for vol_dir in sorted(ms_dir.iterdir()):
        if not vol_dir.is_dir(): continue
        existing = sorted(vol_dir.glob("ch_*_final.md"))
        if existing:
            nums = [int(f.stem.split("_")[1]) for f in existing]
            if nums and min(nums) <= ch_num <= max(nums) + 1:
                fp = vol_dir / f"ch_{ch_num:03d}_final.md"
                fp.write_text(content, encoding="utf-8")
                return {"ok": True, "saved_to": str(fp)}
    # Fallback: use vol_01
    vol_dir = ms_dir / "vol_01"
    vol_dir.mkdir(parents=True, exist_ok=True)
    fp = vol_dir / f"ch_{ch_num:03d}_final.md"
    fp.write_text(content, encoding="utf-8")
    return {"ok": True, "saved_to": str(fp)}

# ── init / plan ─────────────────────────────────────────────────────────

# ── 章节诊断 — 后置分析引擎 ────────────────────────────────────────────

@app.post("/api/chapter-analysis")
async def chapter_analysis(request: Request):
    """Run structural audit on a chapter using local 27B model.
    Returns foreshadowing, causality, conflict, pacing analysis."""
    data = await request.json()
    chapter_text = data.get("content", "")
    chapter_num = data.get("chapter", 0)
    genre = data.get("genre", load_cfg().get("genre", ""))

    if not chapter_text or len(chapter_text) < 100:
        return {"error": "章节内容过短，至少需要100字"}

    try:
        from core.chapter_analyzer import (
            build_analysis_prompt, parse_analysis, gate_evaluation,
            ANALYSIS_SYSTEM_PROMPT,
        )
        from utils.llm_client import get_task_client, get_task_model, _llm_temperature

        # 使用推理模型（分析任务）
        client = get_task_client("reasoning")
        model = get_task_model("reasoning")
        prompt = build_analysis_prompt(chapter_text, genre=genre, chapter_num=chapter_num)

        start = time.time()
        response = client.chat.completions.create(
            model=model,
            temperature=0.3,  # 低温确保分析一致性
            max_tokens=2048,
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            extra_body={"chat_template_kwargs": {"enable_thinking": True}},
        )
        elapsed = round(time.time() - start, 1)
        raw = response.choices[0].message.content

        analysis = parse_analysis(raw, chapter_id=f"ch{chapter_num}")
        gate = gate_evaluation(analysis)

        return {
            "ok": True,
            "elapsed_s": elapsed,
            "chapter": chapter_num,
            "analysis": {
                "summary": analysis.summary,
                "foreshadows_planted": [
                    {"desc": f.description, "type": f.type, "target_ch": f.target_chapter}
                    for f in analysis.foreshadows_planted
                ],
                "foreshadows_paid": [
                    {"desc": f.description, "type": f.type}
                    for f in analysis.foreshadows_paid
                ],
                "scenes": [
                    {"name": s.name, "causality": s.causality,
                     "conflict": s.conflict_level, "beat": s.satisfaction_beat,
                     "chars": s.char_count}
                    for s in analysis.scenes
                ],
                "causality_chain": analysis.causality_chain,
                "pacing_curve": analysis.pacing_curve,
                "tension_peak": analysis.tension_peak_chapter_position,
                "dialogue_pct": analysis.dialogue_ratio_pct,
                "satisfaction_density": analysis.satisfaction_density,
                "overall_score": analysis.overall_score,
                "suggestions": analysis.suggestions,
            },
            "gate": gate,
        }
    except Exception as e:
        webui_logger.error(f"chapter_analysis error: {e}")
        return {"error": str(e)}


# ── 灵感工坊 — 对话式头脑风暴 ─────────────────────────────────────────

@app.post("/api/workshop/chat")
async def workshop_chat(request: Request):
    """SSE streaming chat for story brainstorming. Uses planning model."""
    data = await request.json()
    messages = data.get("messages", [])
    if not messages:
        return {"error": "messages required"}

    async def generate() -> AsyncGenerator[str, None]:
        try:
            from utils.llm_client import get_task_client, _llm_temperature
            client = get_task_client("planning")
            temp = _llm_temperature()
            cfg = load_cfg()
            model = cfg.get("llm", {}).get("model", "auto")
            genre = cfg.get("genre", "")
            style = cfg.get("style", "")
            novel_dir = cfg.get("workspace", {}).get("novel_name", "")
            base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")

            from utils.prompt_loader import brainstorm_prompt
            system = brainstorm_prompt() + """

你的工作方式：
- 先理解作者的核心创意，问 1-2 个关键问题帮助聚焦
- 逐步讨论：主线冲突 → 世界观特色 → 主角设定 → 修炼/力量体系 → 开篇钩子
- 每次只深入一个方面，不要一下子全抛出来
- 用具体的例子和建议，不要说空话
- 当作者对某个方向满意后，再推进到下一个方面
- 最终引导出一个清晰的策划方案

当前项目信息："""
            if genre: system += f"\n小说流派：{genre}"
            if style: system += f"\n写作风格：{style}"
            if base and base.exists():
                world_md = base / "世界观.md"
                if world_md.exists():
                    system += "\n世界观已建立，请参考现有设定进行讨论"
                outline_json = base / "大纲.json"
                if outline_json.exists():
                    system += "\n大纲已存在，请注意与现有大纲保持一致"

            full_messages = [{"role": "system", "content": system}] + messages

            stream = client.chat.completions.create(
                model=model, messages=full_messages,
                temperature=temp, stream=True
            )

            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield f"data: {json.dumps({'token': delta.content}, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/init")
async def init_novel(request: Request):
    data = await request.json()
    logline = data.get("logline", "")
    if not logline:
        return {"error": "logline required"}

    import subprocess
    result = subprocess.run(
        [sys.executable, "cli.py", "init", logline],
        capture_output=True, text=True, cwd=str(Path(__file__).parent.parent), timeout=300
    )
    return {"ok": True, "output": result.stdout + result.stderr}

@app.post("/api/plan")
async def plan_novel(request: Request):
    data = await request.json()
    volume = data.get("volume")
    import subprocess
    args = [sys.executable, "cli.py", "plan"]
    if volume:
        args.extend(["--volume", str(volume)])
    result = subprocess.run(args, capture_output=True, text=True,
                            cwd=str(Path(__file__).parent.parent), timeout=300)
    return {"ok": True, "output": result.stdout + result.stderr}


# ── new module endpoints ─────────────────────────────────────────────────────

@app.get("/api/quality-gate")
async def quality_gate_status():
    """Get last quality gate evaluation result."""
    from core.quality_gate import get_last_result
    result = get_last_result()
    if not result:
        return {"available": False}
    return {"available": True, "result": result.to_dict(),
            "formatted": result.format_report(0)}


@app.get("/api/storyform")
async def get_storyform():
    """Get current NCP storyform."""
    from core.storyform import Storyform, STORYFORM_TEMPLATES
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    sf_path = base / "storyform.json"
    if sf_path.exists():
        sf = Storyform.from_dict(json.loads(sf_path.read_text(encoding="utf-8")))
        return {"available": True, "storyform": sf.to_dict(),
                "context": sf.to_writing_context()}
    return {"available": False, "templates": list(STORYFORM_TEMPLATES.keys())}


@app.post("/api/storyform")
async def save_storyform(request: Request):
    """Save or create a storyform. Body: {template: 'revenge'} or full storyform dict."""
    from core.storyform import Storyform, STORYFORM_TEMPLATES
    data = await request.json()
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    base.mkdir(parents=True, exist_ok=True)
    sf_path = base / "storyform.json"

    # Use template
    if "template" in data and data["template"] in STORYFORM_TEMPLATES:
        sf = STORYFORM_TEMPLATES[data["template"]]
    elif "objective_story" in data:
        sf = Storyform.from_dict(data)
    else:
        return {"error": "Provide 'template' name or full storyform data"}

    sf.title = data.get("title", sf.title)
    sf_path.write_text(sf.to_json(), encoding="utf-8")
    log_step("Storyform saved", template=data.get("template", "custom"), title=sf.title)
    return {"ok": True, "storyform": sf.to_dict()}


# ── story engine (题材×风格 自动匹配) ──────────────────────────────────────

@app.get("/api/story-engine")
async def get_story_engine():
    """Get story engine constraints for current genre × style combo."""
    from core.story_engine import (
        build_writing_context, match_storyform,
        list_genres, list_styles, GENRE_ENGINES, STYLE_MODES,
    )
    cfg = load_cfg()
    genre = cfg.get("genre", "")
    style = cfg.get("style", "")

    result = {
        "genres": list_genres(),
        "styles": list_styles(),
        "current_genre": genre,
        "current_style": style,
        "matched": None,
        "constraints_text": "",
    }

    if genre or style:
        matched = match_storyform(genre, style)
        result["matched"] = {
            "genre_found": matched["genre_found"],
            "style_found": matched["style_found"],
            "constraints": matched["constraints"],
        }
        result["constraints_text"] = build_writing_context(genre, style)

    # Also expose engine metadata for UI display
    if genre and genre in GENRE_ENGINES:
        ge = GENRE_ENGINES[genre]
        result["genre_meta"] = {
            "upgrade_chain": ge.upgrade_chain,
            "core_appeal": ge.core_appeal,
            "pace_reference": ge.pace_reference,
        }
    if style and style in STYLE_MODES:
        sm = STYLE_MODES[style]
        result["style_meta"] = {
            "emotion_curve": sm.emotion_curve,
            "pacing_rule": sm.pacing_rule,
            "dialogue_ratio": sm.dialogue_ratio,
        }

    return result


# ── export ────────────────────────────────────────────────────────────────────

@app.get("/api/export/check")
async def export_check():
    """Check if pandoc is available for export."""
    from utils.exporter import check_pandoc
    return check_pandoc()


@app.post("/api/export")
async def export_manuscript_api(request: Request):
    """Export manuscript to EPUB/PDF."""
    data = await request.json()
    fmt = data.get("format", "epub")
    volume = data.get("volume")
    author = data.get("author", "")
    cover = data.get("cover", "")
    from utils.exporter import export_manuscript, export_all_volumes
    from utils.config import MANUSCRIPTS_DIR
    cfg = load_cfg()
    title = cfg.get("workspace", {}).get("novel_name", "Novel")

    if volume:
        result = export_manuscript(MANUSCRIPTS_DIR, title, ".", fmt, author, cover, volume)
    else:
        results = export_all_volumes(MANUSCRIPTS_DIR, title, ".", fmt, author, cover)
        result = results[0] if results else None
        if not results:
            result = export_manuscript(MANUSCRIPTS_DIR, title, ".", fmt, author, cover)

    if result:
        return {"ok": True, "path": str(result), "size_kb": round(result.stat().st_size / 1024, 1)}
    return {"ok": False, "error": "Export failed (pandoc not found or no chapters)"}


# ── analyze ───────────────────────────────────────────────────────────────────

@app.get("/api/analyze")
async def analyze_manuscript_api(volume: int = None):
    """Get full manuscript analysis report."""
    from core.manuscript_analyzer import analyze_manuscript
    from utils.config import MANUSCRIPTS_DIR
    cfg = load_cfg()
    title = cfg.get("workspace", {}).get("novel_name", "Manuscript")
    report = analyze_manuscript(MANUSCRIPTS_DIR, title, volume)
    if not report:
        return {"ok": False, "error": "No chapters found"}
    return {"ok": True, "report": report.to_dict()}


# ── snapshots ─────────────────────────────────────────────────────────────────

@app.get("/api/snapshots")
async def list_snapshots_api():
    """List all revision snapshots."""
    from core.revision_snapshot import list_snapshots
    return {"snapshots": list_snapshots()}


@app.post("/api/snapshots")
async def save_snapshot_api(request: Request):
    """Save a new revision snapshot."""
    data = await request.json()
    from core.revision_snapshot import save_snapshot
    from utils.config import MANUSCRIPTS_DIR
    snap = save_snapshot(MANUSCRIPTS_DIR, data.get("label", ""), data.get("volume"))
    if snap:
        return {"ok": True, "snapshot": snap.to_dict()}
    return {"ok": False, "error": "No chapters to snapshot"}


@app.post("/api/snapshots/diff")
async def diff_snapshots_api(request: Request):
    """Compare two snapshots, return HTML diff."""
    data = await request.json()
    from core.revision_snapshot import diff_snapshots
    html = diff_snapshots(
        data.get("snap1", ""), data.get("snap2", ""),
        data.get("chapter", 1), "html",
    )
    if html:
        return {"ok": True, "html": html}
    return {"ok": False, "error": "Snapshots not found"}


@app.delete("/api/snapshots/{snapshot_id}")
async def delete_snapshot_api(snapshot_id: str):
    """Delete a snapshot."""
    from core.revision_snapshot import delete_snapshot
    ok = delete_snapshot(snapshot_id)
    return {"ok": ok}


@app.get("/api/logs")
async def get_logs(lines: int = 50, level: str = None):
    """Get recent log entries from the daily log file."""
    from utils.logger import get_log_path, LOG_DIR
    log_path = get_log_path()
    if not log_path.exists():
        # Try listing available log files
        files = sorted(LOG_DIR.glob("novel_claude*"), key=lambda p: p.stat().st_mtime, reverse=True)
        return {"available": False, "files": [f.name for f in files[:5]]}

    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    if level:
        level_upper = level.upper()
        all_lines = [l for l in all_lines if f"| {level_upper} " in l]

    recent = all_lines[-lines:]
    total = len(all_lines)
    size = log_path.stat().st_size

    return {"available": True, "path": str(log_path), "total_lines": total,
            "size_kb": round(size / 1024, 1), "lines": [l.rstrip() for l in recent]}


@app.get("/api/diversity")
async def get_diversity():
    """Get narrative diversity assessment for recent chapters."""
    from core.narrative_diversity import (NARRATIVE_ARCHETYPES, fingerprint_chapter,
                                           diversity_score, suggest_archetype)
    from utils.config import MANUSCRIPTS_DIR

    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    result = {"archetypes": [a.name for a in NARRATIVE_ARCHETYPES], "chapters": []}

    # Find recent chapter files
    manuscript = Path(MANUSCRIPTS_DIR)
    chapters = sorted(manuscript.rglob("ch_*_final.md"))[-10:]
    fps = []
    for ch_path in chapters:
        try:
            ch_num = int(ch_path.stem.split("_")[1])
            text = ch_path.read_text(encoding="utf-8")
            fp = fingerprint_chapter(text, ch_num)
            fps.append(fp)
            result["chapters"].append({
                "num": ch_num,
                "protagonist_resolves": fp.protagonist_resolves,
                "explicit_theme": fp.explicit_theme,
                "philosophical_dialogue": fp.philosophical_dialogue,
                "single_pov": fp.single_pov,
                "linear_time": fp.linear_time,
                "subplot_advance": fp.subplot_advance,
            })
        except Exception:
            pass

    if len(fps) >= 2:
        score, issues = diversity_score(fps)
        result["score"] = score
        result["issues"] = issues
        result["suggestion"] = suggest_archetype(fps)
    else:
        result["score"] = 100
        result["issues"] = ["需要更多章节才能评估多样性"]

    return result


def _load_prompt_refs(*fnames: str) -> str:
    """Load specified reference files and join them."""
    parts = []
    for fname in fnames:
        ref_path = Path(__file__).parent.parent / "prompts" / fname
        if ref_path.exists():
            parts.append(ref_path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)

def _planning_ref() -> str:
    """Market references unified into genre_knowledge.py + style_reference.py"""
    return ""

def _writing_ref() -> str:
    """Market references unified into genre_knowledge.py + style_reference.py"""
    return ""

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
