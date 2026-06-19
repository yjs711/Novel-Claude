"""
wf_mo_shen_workflow — 三档工作流切换 Skill

从 Mo-Shen graph/setup.py 移植。
quick:  单 LLM 调用链（原逻辑，不改动）
standard: 5 Agent 独立 worker（Architect→Scribe→Editor→Polisher→Gatekeeper）
deep:   standard + 重写循环（Gatekeeper 评分 < 70 则 Editor→Polisher 重试，最多3轮）

每个 Agent 使用独立的 model/temperature/penalty 配置，
Agent 间通过结构化 JSON 传递上下文。
"""

import json
from pathlib import Path
from core.base_skill import BaseSkill

WORKFLOW_MODES = {
    "quick": {
        "agents": ["Planner", "OutlineAgent", "ChapterWriter"],
        "description": "快速模式 — 3 Agent（单LLM链），适合试写验证",
        "max_revision_rounds": 0,
        "quality_threshold": 0,
    },
    "standard": {
        "agents": ["Architect", "Scribe", "Editor", "Polisher", "Gatekeeper"],
        "description": "标准模式 — 5 Agent 独立 worker（结构化JSON传递），含去AI味+质量把关",
        "max_revision_rounds": 1,
        "quality_threshold": 70,
    },
    "deep": {
        "agents": ["Architect", "Scribe", "Editor", "Polisher", "Gatekeeper"],
        "description": "深度模式 — 5 Agent + 重写循环（Gatekeeper<70→Editor→Polisher, 最多3轮）",
        "max_revision_rounds": 3,
        "quality_threshold": 70,
    },
}

# Agent 系统提示词
ARCHITECT_SYSTEM = """
<role>资深网文架构师。只做场景分解，不写正文。</role>

<rules>
P0: 每个场景结束必须有价值/情绪翻转(+/-)。外部冲突和内部冲突双螺旋推进。
P1: 标注伏笔(埋/回收)和章末钩子位置。钩子必须断在精彩处——动作中断/信息半露/新危机/两难抉择。
</rules>

<output_format>
JSON: {"chapter_title":"标题","emotion_curve":"+/-翻转描述","scenes":[{"summary":"场景","pov":"视角","emotion_start":"+","emotion_end":"-","external_conflict":"外部","internal_conflict":"内部","advances":"推进点"}],"foreshadowing_plant":[],"foreshadowing_resolve":[],"chapter_hook_end":"钩子","word_count_target":6000}
</output_format>"""

SCRIBE_SYSTEM = """<role>资深网文写手。文字有骨有肉，读者不是来看漂亮话的。</role>

<craft>
按网文社区实测优先级（2025-2026，V4实测验证）：
1. 句长有变化——长句铺氛围，短句打情绪，不要全是一种节奏
2. 真实细节 > 流畅废话——写声响、触感、气味、光线
3. 角色交谈/对峙时必须用「」写出完整对话，禁止把对话改成叙述
4. 章末不写情绪词——让读者从动作环境自己感受
5. 禁用：前所未有/一股XX/猛地一震/倒吸一口凉气/心头一震/顿时/不由得/忍不住/不是A而是B/不仅A更是B/嘴角上扬/身躯一震/心中一沉/心头一暖
</craft>

<output_format>直接输出正文，不要任何解释和说明。</output_format>
"""

EDITOR_SYSTEM = """
<role>起点责任编辑。只审阅找问题，不写正文。</role>

<rules>
按起点编辑真实审稿优先级（2025-2026）：
1. 章末钩子 — 平稳收束=死罪。读者读完这章，心里有没有一个非追不可的问题？
2. 情绪展示 — 禁止"他感到愤怒/恐惧/激动"。必须写具体动作："他攥紧拳头，指甲掐进掌心"。
3. 视角锁定 — 禁止透视配角内心。禁止上帝视角旁白跳出来解释总结。
4. 说教句式 — 原来…/这说明…/他明白了…/人生就是这样…/归根结底…（AI最顽固痕迹）
5. 对话 — 不说教、不哲学讨论、不解释剧情。允许答非所问。
</rules>

<output_format>
JSON: {"overall_score":75,"issues":[{"severity":"critical|major|minor","type":"logic|pacing|character|dialogue|style|narrative|pov|moralizing|cliche","location":"位置","problem":"描述","suggestion":"建议"}],"pacing_ok":true,"character_consistency_ok":true,"hook_effective":true,"needs_rewrite":false}
</output_format>"""

POLISHER_SYSTEM = """
<role>专业网文润色师。修复编辑指出的问题，不改剧情结构。</role>

<rules>
按去AI味社区共识优先级（2025-2026）：
1. 心理描写外化 — "他很紧张"→"他的手在抖"。用动作/细节替代直接情绪词。
2. 删结尾升华 — AI最顽固痕迹。章末禁止总结/感慨/点题。
3. 句式去套路 — 删"不是A而是B""仿佛/犹如""带着XX"。
4. 禁用词替换 — 前所未有/一股/猛地一震/倒吸一口凉气/心头一震/顿时/不由得/忍不住/嘴角上扬/心中一沉/心头一暖。
5. 节奏打碎 — 段落长短交错，有单句段。打破均匀工整感。
</rules>

<output_format>直接输出润色后正文。</output_format>"""

GATEKEEPER_SYSTEM = """
<role>网文质量守门人。最终评分，决定是否通过。</role>

<rules>
5维评分(每维0-100)，按起点编辑优先级：
  1. 追读力 — 读者读完本章是否必然点下一章（章末钩子+全程期待感）
  2. AI味 — 越低越好。>30必须重写。
  3. 对话自然度 — 是否像活人说话（不说教、不解释、有潜台词）
  4. 感官密度 — 每段是否有至少1个具体感官细节（声响/触感/气味/光线）
  5. 节奏 — 有无3章以上持续平淡（无冲突/无反转/无新信息）

P0红线: AI味>30→重写。追读力<40→重写。
</rules>

<output_format>
JSON: {"final_score":85,"dimensions":{"reader_retention":82,"ai_flavor":15,"dialogue_naturalness":83,"sensory_richness":75,"pacing":80},"passed":true,"remaining_issues":[]}
</output_format>"""

DEFAULT_MODE = "quick"


def _resolve_model_for_agent(agent_role: str, config: dict) -> str:
    """根据 Agent 角色解析模型。"""
    task_models = config.get("llm", {}).get("task_models", {})
    role_to_task = {
        "Architect": "planning",
        "Scribe": "writing",
        "Editor": "reasoning",
        "Polisher": "writing",
        "Gatekeeper": "reasoning",
    }
    task = role_to_task.get(agent_role)
    if task and task in task_models:
        return task_models[task]
    return config.get("llm", {}).get("default_model", "qwen3.6-27b-uncensored")


class WfMoShenWorkflowSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "三档工作流"
        self.current_mode = DEFAULT_MODE
        self._config = {}

    def on_init(self) -> None:
        cfg = Path(__file__).parent.parent.parent / "config.json"
        if cfg.exists():
            with open(cfg, "r", encoding="utf-8") as f:
                self._config = json.load(f)
                wf = self._config.get("workflow", {})
                self.current_mode = wf.get("mode", DEFAULT_MODE)
                cfg_mode = WORKFLOW_MODES.get(self.current_mode, WORKFLOW_MODES[DEFAULT_MODE])
                cfg_mode["max_revision_rounds"] = wf.get("max_revision_rounds", cfg_mode["max_revision_rounds"])
                cfg_mode["quality_threshold"] = wf.get("quality_threshold", cfg_mode["quality_threshold"])

        mode_info = WORKFLOW_MODES.get(self.current_mode, WORKFLOW_MODES[DEFAULT_MODE])
        self.context.set_shared("workflow_mode", self.current_mode)
        self.context.set_shared("workflow_config", mode_info)
        print(f"  [✓] {self.name} 已就绪（模式: {self.current_mode} — {mode_info['description']}）")

    def on_volume_planning(self, outline_draft: dict) -> dict:
        mode = self.context.get_shared("workflow_mode", DEFAULT_MODE)
        if mode == "quick":
            outline_draft["_skip_worldbuilding"] = True
            outline_draft["_skip_character_design"] = True
        elif mode in ("standard", "deep"):
            outline_draft["_skip_worldbuilding"] = False
            outline_draft["_skip_character_design"] = False
        if mode == "deep":
            outline_draft["_enable_revision_loop"] = True
            outline_draft["_max_revision_rounds"] = WORKFLOW_MODES["deep"]["max_revision_rounds"]
        return outline_draft

    def set_mode(self, mode: str):
        if mode in WORKFLOW_MODES:
            self.current_mode = mode
            self.context.set_shared("workflow_mode", mode)
            self.context.set_shared("workflow_config", WORKFLOW_MODES[mode])
            print(f"  [✓] 工作流切换为: {mode}")
        else:
            print(f"  [=1] 未知模式: {mode}，可用: {list(WORKFLOW_MODES.keys())}")

    # ── 多 Agent 编排 ────────────────────────────────────────────────────────

    def run_agent_pipeline(self, chapter_outline: dict, chapter_id: int) -> dict:
        """
        执行多 Agent 写作流水线。

        返回: {
            "final_text": str,
            "architect_plan": dict,
            "editor_review": dict,
            "gatekeeper_score": dict,
            "revision_rounds": int,
            "passed": bool,
        }
        """
        mode_info = WORKFLOW_MODES.get(self.current_mode, WORKFLOW_MODES[DEFAULT_MODE])
        max_rounds = mode_info.get("max_revision_rounds", 1)
        quality_threshold = mode_info.get("quality_threshold", 70)

        # 提取流派/风格注入（由 WebUI 传入）
        genre_style_injection = chapter_outline.pop("_genre_style_injection", "")

        # ── 1. Architect: 场景分解 ──
        architect_user = f"大纲: {json.dumps(chapter_outline, ensure_ascii=False)}"
        if genre_style_injection:
            architect_user += f"\n\n[流派/风格指令——请严格遵守以下约束进行场景规划]\n{genre_style_injection}"
        architect_user += "\n\n为本章生成详细的场景分解方案。"
        architect_plan = self._call_agent(
            "Architect", ARCHITECT_SYSTEM, architect_user,
            **self._agent_params("Architect")
        )
        scenes = architect_plan.get("scenes", [])
        print(f"  [Architect] 场景分解完成 ({len(scenes)} 个场景)")

        # ── 2. Scribe: 正文执笔 ──
        scribe_system = SCRIBE_SYSTEM
        if genre_style_injection:
            scribe_system += f"\n\n[必须严格遵守的流派/风格约束]\n{genre_style_injection}"

        # Inject memory context from skill pipeline (L1/L2/L3 + genre knowledge)
        memory_context = self._get_memory_context(chapter_id)
        scribe_prompt = (f"场景分解方案:\n{json.dumps(architect_plan, ensure_ascii=False, indent=2)}\n\n"
                         f"{memory_context}"
                         f"根据以上方案写出本章正文。")
        chapter_text = self._call_agent_text(
            "Scribe", scribe_system, scribe_prompt,
            **self._agent_params("Scribe")
        )
        print(f"  [Scribe] 初稿完成 ({len(chapter_text)} 字)")

        # ── 重写循环 ──
        editor_review = {}
        gatekeeper_score = {"final_score": 0, "passed": False}
        revision_rounds = 0

        for round_num in range(max_rounds + 1):
            revision_rounds = round_num

            # ── 3. Editor: 审阅 ──
            editor_review = self._call_agent(
                "Editor", EDITOR_SYSTEM,
                f"大纲: {json.dumps(chapter_outline, ensure_ascii=False)}\n\n正文:\n{chapter_text[:8000]}",
                **self._agent_params("Editor")
            )
            issues = editor_review.get("issues", [])
            print(f"  [Editor] 审阅完成 — 评分 {editor_review.get('overall_score', '?')}，{len(issues)} 个问题")

            # 没有 critical 问题且不需要重写就跳出
            criticals = [i for i in issues if i.get("severity") == "critical"]
            if not editor_review.get("needs_rewrite", False) and len(criticals) == 0:
                break

            # ── 4. Polisher: 润色 ──
            polish_prompt = f"编辑审阅意见:\n{json.dumps(editor_review, ensure_ascii=False, indent=2)}\n\n正文:\n{chapter_text}"
            chapter_text = self._call_agent_text(
                "Polisher", POLISHER_SYSTEM, polish_prompt,
                **self._agent_params("Polisher")
            )
            print(f"  [Polisher] 润色完成 (第 {round_num + 1} 轮)")

        # ── 5. Gatekeeper: 最终评分 ──
        gatekeeper_score = self._call_agent(
            "Gatekeeper", GATEKEEPER_SYSTEM,
            f"大纲: {json.dumps(chapter_outline, ensure_ascii=False)}\n\n正文:\n{chapter_text[:8000]}",
            **self._agent_params("Gatekeeper")
        )
        passed = gatekeeper_score.get("final_score", 0) >= quality_threshold
        status = "通过" if passed else "未达标"
        print(f"  [Gatekeeper] 最终评分: {gatekeeper_score.get('final_score', '?')}/100 {status}")

        # Run shared post-processing pipeline (hooks + quality gate)
        self._run_post_process(chapter_text, chapter_id)

        return {
            "final_text": chapter_text,
            "architect_plan": architect_plan,
            "editor_review": editor_review,
            "gatekeeper_score": gatekeeper_score,
            "revision_rounds": revision_rounds,
            "passed": passed,
        }

    def _get_memory_context(self, chapter_id: int) -> str:
        """Inject L1/L2/L3 memory context into Scribe prompt (shared pipeline)."""
        story_state = self.context.get_shared("story_state")
        if not story_state:
            return ""
        try:
            from skills.mem_working_memory.skill import MemWorkingMemorySkill
            mem = MemWorkingMemorySkill(self.context)
            # Build memory blocks
            l1 = mem._build_working_memory(story_state, chapter_id)
            l2 = mem._build_episodic_memory(story_state, chapter_id)
            l3 = mem._build_semantic_memory(story_state)
            parts = [p for p in [l1, l2, l3] if p]
            if parts:
                return "[Memory Context]\n" + "\n".join(parts) + "\n\n"
        except Exception:
            pass
        return ""

    def _run_post_process(self, chapter_text: str, chapter_id: int) -> None:
        """Run shared post-processing pipeline (hooks + quality gate).
        Called after agent pipeline completes to ensure continuity checks,
        DeAI detection, memory sedimentation, and quality gate all run."""
        try:
            from scene_writer import post_process_chapter
            vol_id = getattr(self.context, 'current_volume_id', 1)
            post_process_chapter(vol_id, chapter_id, chapter_text)
        except Exception as e:
            print(f"  [wf] post_process_chapter failed: {e}")

    def _agent_params(self, role: str) -> dict:
        """从 config 获取 Agent 的推理参数，config 有则用，无则用默认值。

        Agent → task_type 映射：
          Architect → planning,  Scribe → writing,  Editor → reasoning,
          Polisher → deai,       Gatekeeper → reasoning
        """
        role_to_task = {
            "Architect": "planning", "Scribe": "writing", "Editor": "reasoning",
            "Polisher": "deai", "Gatekeeper": "reasoning",
        }
        task = role_to_task.get(role, "reasoning")
        try:
            from utils.llm_client import _llm_temperature, _llm_frequency_penalty, _llm_presence_penalty, _llm_top_p
            return {
                "temperature": _llm_temperature(task),
                "freq_pen": _llm_frequency_penalty(task),
                "pres_pen": _llm_presence_penalty(task),
                "top_p": _llm_top_p(task),
            }
        except Exception:
            # 回退：无法导入时用内置默认值
            DEFAULTS = {
                "Architect":  {"temperature": 0.6, "freq_pen": 0.1, "pres_pen": 0.0, "top_p": 0.9},
                "Scribe":     {"temperature": 0.9, "freq_pen": 0.3, "pres_pen": 0.2, "top_p": 0.95},
                "Editor":     {"temperature": 0.5, "freq_pen": 0.1, "pres_pen": 0.0, "top_p": 0.85},
                "Polisher":   {"temperature": 0.7, "freq_pen": 0.4, "pres_pen": 0.3, "top_p": 0.92},
                "Gatekeeper": {"temperature": 0.5, "freq_pen": 0.1, "pres_pen": 0.0, "top_p": 0.85},
            }
            return DEFAULTS.get(role, DEFAULTS["Editor"])

    def _call_agent(self, role: str, system: str, user: str, **params) -> dict:
        """调用 Agent 获取结构化 JSON 输出。"""
        task_map = {"Architect": "planning", "Scribe": "writing", "Editor": "reasoning", "Polisher": "writing", "Gatekeeper": "reasoning"}
        task = task_map.get(role, "reasoning")
        try:
            from utils.llm_client import get_task_client, get_task_model
            client = get_task_client(task)
            model = get_task_model(task)
        except Exception:
            from utils.llm_client import _get_client, resolve_model, resolve_provider
            client = _get_client()
            model = resolve_model(resolve_provider())

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=params.get("temperature", 0.7),
            frequency_penalty=params.get("freq_pen", 0.2),
            presence_penalty=params.get("pres_pen", 0.1),
            top_p=params.get("top_p", 0.9),
        )
        content = response.choices[0].message.content or "{}"
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            return {"raw_output": content, "parse_error": True}

    def _call_agent_text(self, role: str, system: str, user: str, **params) -> str:
        """调用 Agent 获取自由文本输出。"""
        task_map = {"Architect": "planning", "Scribe": "writing", "Editor": "reasoning", "Polisher": "writing", "Gatekeeper": "reasoning"}
        task = task_map.get(role, "writing")
        try:
            from utils.llm_client import get_task_client, get_task_model
            client = get_task_client(task)
            model = get_task_model(task)
        except Exception:
            from utils.llm_client import _get_client, resolve_model, resolve_provider
            client = _get_client()
            model = resolve_model(resolve_provider())

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=params.get("temperature", 0.7),
            frequency_penalty=params.get("freq_pen", 0.2),
            presence_penalty=params.get("pres_pen", 0.1),
            top_p=params.get("top_p", 0.9),
        )
        return response.choices[0].message.content or ""
