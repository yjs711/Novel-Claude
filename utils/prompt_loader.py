"""
模型专用提示词加载器

为网文写作流程中的每个模型加载对应的 System Prompt。
提示词文件位于 prompts/model-prompts/ 目录。
"""

from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts" / "model-prompts"

# 任务 → 提示词文件 映射
TASK_PROMPT_MAP = {
    "planning":      "planner-opus-35b.md",
    "writing":       "writer-huihui-27b.md",
    "polishing":     "polisher-ud-27b.md",
    "fast_writing":  "writer-fast-35b.md",
    "brainstorm":    "brainstorm-35b-aggressive.md",
    "editing":       "editor-opus-35b.md",
}

# 模型 ID → 提示词文件 映射（精确匹配）
MODEL_PROMPT_MAP = {
    "qwen3.6-35b-opus-reasoning":     "planner-opus-35b.md",
    "qwen3.6-27b-uncensored":         "writer-huihui-27b.md",
    "qwen3.6-27b-ud":                 "polisher-ud-27b.md",
    "qwen3.6-35b-ud":                 "writer-fast-35b.md",
    "qwen3.6-uncensored-aggressive":  "brainstorm-35b-aggressive.md",
}

_cache: dict[str, str] = {}

def load_prompt(task_or_model: str) -> str:
    """
    根据任务名或模型 ID 加载对应的 System Prompt。

    优先按任务名查找，其次按模型 ID 查找。
    找不到时返回默认提示词。
    """
    filename = TASK_PROMPT_MAP.get(task_or_model) or MODEL_PROMPT_MAP.get(task_or_model)
    if filename is None:
        # 尝试模糊匹配：模型 ID 包含关键字符串
        for key, fname in MODEL_PROMPT_MAP.items():
            if key in task_or_model or task_or_model in key:
                filename = fname
                break

    if filename is None:
        return _default_prompt()

    if filename not in _cache:
        filepath = _PROMPT_DIR / filename
        if filepath.exists():
            _cache[filename] = filepath.read_text(encoding="utf-8").strip()
        else:
            _cache[filename] = _default_prompt()

    return _cache[filename]

def _default_prompt() -> str:
    return "你是一个专业的网络小说写作助手。请根据用户的需求进行创作。"

# 便捷别名
def planning_prompt() -> str:
    return load_prompt("planning")

def writing_prompt() -> str:
    return load_prompt("writing")

def polishing_prompt() -> str:
    return load_prompt("polishing")

def fast_writing_prompt() -> str:
    return load_prompt("fast_writing")

def brainstorm_prompt() -> str:
    return load_prompt("brainstorm")

def editing_prompt() -> str:
    return load_prompt("editing")
