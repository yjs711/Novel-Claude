"""
模型专用提示词加载器

为网文写作流程中的每个模型加载对应的 System Prompt。
提示词文件位于 prompts/model-prompts/ 目录。
风格参照文本位于 prompts/style-references/ 目录。
"""

from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts" / "model-prompts"
_STYLE_DIR = Path(__file__).resolve().parent.parent / "prompts" / "style-references"

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

_MAPPING_FILE = Path(__file__).resolve().parent.parent / "prompts" / "style_mapping.json"
_cache: dict[str, str] = {}
_style_map: dict[str, str] | None = None

def _get_style_map() -> dict[str, str]:
	"""加载风格→参照文件的映射表。"""
	global _style_map
	if _style_map is None:
		import json
		if _MAPPING_FILE.exists():
			_style_map = json.loads(_MAPPING_FILE.read_text(encoding="utf-8"))
		else:
			_style_map = {}
	# 过滤掉 _alt 后缀的条目
	return {k: v for k, v in _style_map.items() if not k.endswith("_alt")}

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


def load_style_reference(style_name: str) -> str | None:
	"""加载指定风格的参照文本（人类写作示例）。"""
	filepath = _STYLE_DIR / f"{style_name}.md"
	if filepath.exists():
		return filepath.read_text(encoding="utf-8").strip()
	return None


def match_style_reference(style: str, genre: str = "") -> str | None:
	"""
	根据用户选定的风格和流派，自动匹配对应的参照文本。

	优先级：精确匹配 style_mapping → 模糊匹配 → None
	"""
	mapping = _get_style_map()
	ref_key = mapping.get(style)
	if ref_key:
		ref = load_style_reference(ref_key)
		if ref:
			# 可选的流派前缀
			genre_ref = load_style_reference(f"{ref_key}-{genre}")
			if genre_ref:
				ref = ref + "\n\n" + genre_ref
			return ref
	return None


def list_styles() -> list[str]:
	"""列出所有可用的风格参照。"""
	return [p.stem for p in _STYLE_DIR.glob("*.md")]


def inject_style_reference(base_prompt: str, style: str, genre: str = "") -> str:
	"""
	将匹配的风格参照注入到提示词末尾。
	返回 base_prompt + 风格参照（如果有匹配）。
	"""
	ref = match_style_reference(style, genre)
	if ref:
		disclaimer = (
			"---\n"
			"**风格参照（学习节奏/句式/留白，但以下内容严禁模仿）：**\n"
			"- 不要学比喻结构（像/仿佛/如同/犹如）。真人用比喻是说不清楚才用，AI用比喻是装饰。\n"
			"- 直接写感受，不要给感受找替身。\n\n"
		)
		return base_prompt + "\n\n" + disclaimer + ref
	return base_prompt


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
