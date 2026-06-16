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

app = FastAPI(title="Novel-Claude Fusion")

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

# ── routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    tpl = Path(__file__).parent / "templates" / "index.html"
    return tpl.read_text(encoding="utf-8")

@app.get("/api/config")
async def get_config():
    return load_cfg()

@app.post("/api/config")
async def update_config(novel_name: str = Form(""), genre: str = Form(""),
                         style: str = Form(""), workflow: str = Form("")):
    cfg = load_cfg()
    if novel_name: cfg["workspace"]["novel_name"] = novel_name
    if genre: cfg["genre"] = genre
    if style: cfg["style"] = style
    if workflow: cfg["workflow"]["mode"] = workflow
    save_cfg(cfg)
    return {"ok": True}

@app.get("/api/status")
async def status():
    from core.story_state import load_story_state, current_chapter
    from utils.llm_client import get_provider_info

    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    sp = Path(f".novel_{novel_dir}" if novel_dir else ".novel") / "story_state.json"

    result = {"connected": True, "provider": get_provider_info()["provider"],
              "model": get_provider_info()["model"], "novel_name": novel_dir}

    if sp.exists():
        s = load_story_state(sp)
        result["title"] = s.title or novel_dir
        result["genre"] = s.genre
        result["cur_chapter"] = current_chapter(s)
        result["char_count"] = len(s.characters)
        result["thread_count"] = len(s.plot_threads)
        result["chapter_count"] = len([c for c in s.chapters.values() if c.status != "planned"])
        result["chapters"] = [
            {"num": num, "title": ch.title, "status": ch.status, "words": ch.word_count}
            for num, ch in sorted(s.chapters.items())[-20:]
        ]
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
async def styles():
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
    """SSE streaming chapter generation - streams tokens in real-time."""
    data = await request.json()
    volume = data.get("volume", 1)
    chapter = data.get("chapter", 1)

    async def generate() -> AsyncGenerator[str, None]:
        yield "data: " + json.dumps({"type": "status", "msg": f"正在生成第{volume}卷第{chapter}章..."}, ensure_ascii=False) + "\n\n"

        try:
            from scene_writer import (
                load_chapter_outline, load_entity_cards, load_world_setting,
                load_previous_chapter, load_history_chapters, load_next_chapter_outline,
                load_writing_guide, _load_structured_outline_chapter, _load_foreshadowing_context
            )
            from utils.config import MANUSCRIPTS_DIR
            import json as _json

            client = _get_task_client("writing")  # 正文用 Gemma4
            outline = load_chapter_outline(volume, chapter)
            if not outline:
                yield "data: " + _json.dumps({"type": "error", "msg": "找不到章节大纲"}, ensure_ascii=False) + "\n\n"
                return

            chapter_title = outline.get("title", f"第{chapter}章")
            overview = outline.get("overview", "")
            entity_list = outline.get("entity_list", [])

            entities = load_entity_cards(entity_list)
            world_setting = load_world_setting()
            prev_chapter = load_previous_chapter(volume, chapter)
            history_chapters = load_history_chapters(volume, chapter, count=3)
            next_outline = load_next_chapter_outline(volume, chapter)
            writing_guide = load_writing_guide(volume)

            # Build prompt (same as scene_writer.py)
            prompt_parts = [
                f"【章节大纲】:\n标题：{chapter_title}\n概述：{overview}\n",
                f"【参与者实体】:\n角色：{_json.dumps(entities.get('characters',[]), ensure_ascii=False, indent=2)}\n",
                f"【场景】: {_json.dumps(entities.get('scenes',[]), ensure_ascii=False, indent=2)}\n",
            ]
            if world_setting:
                content = world_setting.get("content", world_setting)
                prompt_parts.append(f"【世界观设定】:\n{content.get('world_view','')}\n")
            if history_chapters:
                prompt_parts.append(f"【历史章节剧情回顾】:\n{history_chapters}\n")
            if prev_chapter:
                prompt_parts.append(f"【前章结尾】:\n{prev_chapter}\n")
            if next_outline:
                prompt_parts.append(f"【下一章预告】:\n{next_outline.get('title','')}：{next_outline.get('overview','')}\n")
            if writing_guide:
                prompt_parts.append(f"【写作指南】:\n{writing_guide}\n")

            # Structured outline detail
            struct_outline = _load_structured_outline_chapter(chapter)
            if struct_outline:
                detail_parts = []
                if struct_outline.get("summary"):
                    detail_parts.append(f"【本章概要】: {struct_outline['summary']}")
                if struct_outline.get("scenes_text") or struct_outline.get("scenes"):
                    scenes = struct_outline.get("scenes_text") or str(struct_outline.get("scenes",""))
                    detail_parts.append(f"【场景细纲】:\n{scenes}")
                if struct_outline.get("satisfaction_beat"):
                    detail_parts.append(f"【本章爽点】: {struct_outline['satisfaction_beat']}")
                if struct_outline.get("ending_hook"):
                    detail_parts.append(f"【章末钩子(必须!)】: {struct_outline['ending_hook']}")
                if detail_parts:
                    prompt_parts.append("【详细细纲 — 严格遵循】:\n" + "\n".join(detail_parts))

            # Foreshadowing
            fs_ctx = _load_foreshadowing_context(chapter)
            if fs_ctx:
                prompt_parts.append(f"【伏笔提醒】:\n{fs_ctx}")

            prompt_parts.append(
                f"【写作要求】:\n1. 第一行必须是格式：# 第{chapter}章 标题名\n"
                f"2. 承前启后，严格执行详细细纲的场景分解\n"
                f"3. 爽点到位，章末保留钩子\n"
                f"4. 如有伏笔提醒务必处理\n5. 约6000字\n\n请开始写作：\n"
            )
            prompt = "\n".join(prompt_parts)

            # Stream generation
            full_content = ""
            stream = client.chat.completions.create(
                model="auto", temperature=0.8, max_tokens=8192, stream=True,
                messages=[{"role":"user","content":prompt}],
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_content += text
                    yield "data: " + _json.dumps({"type": "stream", "text": text}, ensure_ascii=False) + "\n\n"

            # Save
            if full_content:
                ms_dir = Path(MANUSCRIPTS_DIR) / f"vol_{volume:02d}"
                ms_dir.mkdir(parents=True, exist_ok=True)
                ch_file = ms_dir / f"ch_{chapter:03d}_final.md"
                ch_file.write_text(full_content, encoding="utf-8")
                yield "data: " + _json.dumps({"type": "done", "chapter": chapter, "words": len(full_content), "path": str(ch_file)}, ensure_ascii=False) + "\n\n"
                yield "data: " + _json.dumps({"type": "complete", "chapter": chapter, "words": len(full_content)}, ensure_ascii=False) + "\n\n"
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

    from utils.llm_client import get_client_for
    client = _get_task_client("planning")  # 设定/人物策划用 Qwen3.6

    system_prompt = f"""你是专业的中文网文{doc_type}设计师。请生成一份详细的{doc_type}。

小说类型：{genre}
当前主题：{topic}
用户要求：{instructions}

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
                model="auto",
                messages=messages,
                temperature=0.8,
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

    system_prompt = f"""你是一个专业的中文网文编辑。用户在修改一份{doc_type}，需要你的帮助。
你的任务：根据用户的修改指令，输出修改后的完整内容。
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
                model="auto",
                messages=messages,
                temperature=0.7,
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

# ── model discovery & switching ──────────────────────────────────────────

@app.get("/api/models")
async def discover_models():
    """Auto-discover all loaded models by scanning configured LM Studio ports.
    Calls /v1/models on each port, matches against config alt_models keys."""
    import httpx
    cfg = load_cfg()
    scan_ports = cfg.get("llm", {}).get("scan_ports", [1234])
    default_key = cfg.get("llm", {}).get("default_model", "")
    alt = cfg.get("llm", {}).get("alt_models", {})
    models = {}
    discovered_default = None
    # Track seen keys to dedup (prefer shorter model IDs)
    seen_key_ids = {}

    for port in scan_ports:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"http://127.0.0.1:{port}/v1/models")
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("data", []):
                        mid = m.get("id", "")
                        if _is_ignored_model(mid): continue
                        key = _model_key_from_id(mid, port)
                        # Use alt_model label if key matches alt_models
                        label = alt[key]["label"] if key in alt else _model_label(mid)
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
                "port": int(cfg_m.get("base_url", "").split(":")[2].split("/")[0]) if ":" in cfg_m.get("base_url", "") else 0,
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
    return {"models": models, "default": active_default, "task_models": task_models}

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

def _model_label(model_id: str) -> str:
    """Create a human-readable label from model ID"""
    mid = model_id.lower()
    # Ordered from most specific to least specific
    known = [
        ("coder-next", "Coder-Next 推理"),
        ("qwen3-coder-next", "Coder-Next 推理"),
        ("qwen3-coder-30b", "Coder-30B 编程"),
        ("qwen3-coder", "Coder 编程"),
        ("qwen3.6-uncensored-aggressive", "Qwen3.6 激进无审查"),
        ("qwen3.6-uncensored", "Qwen3.6 无审查"),
        ("qwen3.6-27b", "Qwen3.6 大纲策划"),
        ("qwen3.6", "Qwen3.6 大纲策划"),
        ("qwen3.5", "Qwen3.5 写手"),
        ("gemma4", "Gemma4 正文执笔"),
        ("gemma-4", "Gemma4 正文执笔"),
        ("gpt-oss", "GPT-OSS 超大杯"),
        ("deepseek", "DeepSeek 推理"),
    ]
    for kw, label in known:
        if kw in mid:
            return label
    return model_id[:40]

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
    scan_ports = cfg.get("llm", {}).get("scan_ports", [1234])

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
    """Save structured outline + auto-generate markdown."""
    data = await request.json()
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    jp, mp = _outline_path(base)
    # Remove _source marker
    data.pop("_source", None)
    data.pop("markdown", None)
    jp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
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

    from utils.llm_client import get_client_for
    client = _get_task_client("planning")  # 设定/人物策划用 Qwen3.6

    system_prompt = f"""你是专业的网文细纲设计师。为第{chap_num}章生成详细写作细纲。

小说：{novel_title} | 类型：{genre}
世界观参考：{world_ctx[:1500]}

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
                model="auto", temperature=0.7, max_tokens=3072, stream=True,
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

    from utils.llm_client import get_client_for
    client = _get_task_client("planning")  # 设定/人物策划用 Qwen3.6

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
            model="auto", temperature=0.5, max_tokens=1024,
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
async def list_chapter_files():
    """List all written chapter files with metadata."""
    novel_dir = load_cfg().get("workspace", {}).get("novel_name", "")
    base = Path(f".novel_{novel_dir}" if novel_dir else ".novel")
    ms_dir = base / "manuscripts"
    if not ms_dir.exists():
        return {"volumes": [], "total_chapters": 0, "total_words": 0}

    volumes = []
    total_words = 0
    for vol_dir in sorted(ms_dir.iterdir()):
        if not vol_dir.is_dir(): continue
        chapters = []
        for ch_file in sorted(vol_dir.glob("ch_*_final.md")):
            content = ch_file.read_text(encoding="utf-8")
            num = int(ch_file.stem.split("_")[1])
            title = ""
            # Extract title from first heading
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
            # Extract volume number from dir name
            vol_num = vol_dir.name.replace("vol_", "")
            volumes.append({
                "name": f"第{int(vol_num)}卷" if vol_num.isdigit() else vol_dir.name,
                "dir": vol_dir.name,
                "chapters": chapters,
            })

    return {"volumes": volumes, "total_chapters": sum(len(v.get("chapters",[])) for v in volumes), "total_words": total_words}

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

# ── deAI rewrite (AI-driven de-AI-ification) ────────────────────────────

@app.post("/api/deai-rewrite")
async def deai_rewrite(request: Request):
    """AI rewrites chapter to remove AI-sounding patterns. SSE streaming.
    Uses the currently selected model with specific de-AI instructions."""
    data = await request.json()
    chapter_num = data.get("chapter", 1)
    content = data.get("content", "")
    full_text = data.get("full_text", content)
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

    # Build rewrite instructions based on detection
    issues = []
    for word, count in detection.get("word_counts", {}).items():
        if count >= 3:
            issues.append(f"「{word}」出现{count}次，属于AI高频用词，请替换或删除大部分")
    for pattern, label in detection.get("pattern_matches", []):
        issues.append(f"句式「{label}」模板化严重，请改写自然")

    issues_text = "\n".join(f"- {i}" for i in issues[:10]) if issues else "无显著问题"

    from utils.llm_client import get_client_for
    client = _get_task_client("writing")  # 去AI改写用 Gemma4

    system_prompt = f"""你是一个专业的中文网文编辑，擅长**去AI味**改写。
你的任务是：把AI生成的模板化文本，改写成**像人写的**网文。

改写原则：
1. 删除所有「不禁」「缓缓」「竟然」「顿时」「不由得」「仿佛」等AI高频词
2. 打破「嘴角上扬」「心中一震」「深吸一口气」等模板句式
3. 对话要自然，不同人物有不同说话风格
4. 动作描写要具体，不要用模糊的套话
5. 保持原文的剧情走向和核心信息不变
6. 保留网文的爽感和节奏

检测到的问题：
{issues_text}

请直接输出改写后的完整章节，不要解释你改了什么。章节号保持不变。"""

    async def generate():
        try:
            stream = client.chat.completions.create(
                model="auto", temperature=0.7, max_tokens=min(len(full_text) * 2, 8192), stream=True,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请重写以下章节，去除AI味：\n\n{full_text[-12000:]}"}
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

            system = f"""你是一位资深的网络小说策划师，擅长帮作者把模糊的灵感打磨成完整的故事方案。

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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
