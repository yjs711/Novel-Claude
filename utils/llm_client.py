"""
LLM Client — provider-agnostic, LM Studio first.

Supports:
  - lmstudio / ollama / openai_compatible (any /v1/chat/completions endpoint)
  - openai / anthropic / deepseek / zhipu (native SDKs)
  - Provider + model read from config.json → [llm] section
  - Env-var overrides: NOVEL_CLAUDE_PROVIDER, NOVEL_CLAUDE_MODEL,
                       NOVEL_CLAUDE_BASE_URL, NOVEL_CLAUDE_API_KEY

Backward-compatible: ProgressiveWriter, generate_json, extract_entities all kept.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from openai import OpenAI
from openai import APIError, APITimeoutError
from pydantic import ValidationError
from rich.live import Live
from rich.markdown import Markdown

try:
    from openai import ConnectionError as OpenAIConnectionError
except ImportError:
    OpenAIConnectionError = Exception


# ── config loading ──────────────────────────────────────────────────────────

def _load_config_json() -> dict:
    """Read Novel-Claude config.json once."""
    cfg_path = Path(__file__).parent.parent / "config.json"
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _llm_section() -> dict:
    return _load_config_json().get("llm", {})


# ── provider resolution ─────────────────────────────────────────────────────

# Convenience aliases: name → (base_url, default_model, env_key_name)
PROVIDER_ALIASES: Dict[str, tuple] = {
    "lmstudio":  ("http://localhost:1234/v1",  "local-model",                 "LMSTUDIO_API_KEY"),
    "ollama":    ("http://localhost:11434/v1",  "llama3.2",                   "OLLAMA_API_KEY"),
    "deepseek":  ("https://api.deepseek.com/v1","deepseek-chat",              "DEEPSEEK_API_KEY"),
    "zhipu":     ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash",     "ZHIPU_API_KEY"),
    "moonshot":  ("https://api.moonshot.cn/v1", "moonshot-v1-8k",            "MOONSHOT_API_KEY"),
    "groq":      ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile","GROQ_API_KEY"),
    "together":  ("https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo", "TOGETHER_API_KEY"),
    "openrouter":("https://openrouter.ai/api/v1","openai/gpt-4o",            "OPENROUTER_API_KEY"),
    "mistral":   ("https://api.mistral.ai/v1",   "mistral-large-latest",     "MISTRAL_API_KEY"),
    "fireworks": ("https://api.fireworks.ai/inference/v1", "accounts/fireworks/models/llama-v3p3-70b-instruct", "FIREWORKS_API_KEY"),
}


def resolve_provider() -> str:
    """Priority: env NOVEL_CLAUDE_PROVIDER → config.json [llm].provider → lmstudio."""
    env = os.environ.get("NOVEL_CLAUDE_PROVIDER")
    if env:
        return env.lower()
    cfg = _llm_section().get("provider")
    if cfg:
        return cfg.lower()
    return "lmstudio"


def resolve_model(provider: str) -> str:
    """Priority: env → config → alias default → 'local-model'."""
    env = os.environ.get("NOVEL_CLAUDE_MODEL")
    if env:
        return env
    cfg = _llm_section().get("model")
    if cfg:
        return cfg
    if provider in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[provider][1]
    return "local-model"


def resolve_flash_model(provider: str) -> str:
    """Quick / cheap model for entity extraction. Falls back to main model."""
    env = os.environ.get("NOVEL_CLAUDE_FLASH_MODEL")
    if env:
        return env
    cfg = _llm_section().get("flash_model")
    if cfg:
        return cfg
    return resolve_model(provider)


def resolve_base_url(provider: str) -> str:
    """Priority: env → config → alias default."""
    env = os.environ.get("NOVEL_CLAUDE_BASE_URL")
    if env:
        return env
    cfg = _llm_section().get("base_url")
    if cfg:
        return cfg
    if provider in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[provider][0]
    return "http://localhost:1234/v1"


def resolve_api_key(provider: str) -> str:
    """Priority: env → config → alias env var → 'not-needed'."""
    env = os.environ.get("NOVEL_CLAUDE_API_KEY")
    if env:
        return env
    cfg = _llm_section().get("api_key")
    if cfg:
        return cfg
    if provider in PROVIDER_ALIASES:
        key_env = PROVIDER_ALIASES[provider][2]
        from_env = os.environ.get(key_env)
        if from_env:
            return from_env
    # For local providers (lmstudio, ollama) no key is needed
    if provider in ("lmstudio", "ollama"):
        return "not-needed"
    return os.environ.get("OPENAI_API_KEY", "not-needed")


# ── client singleton ─────────────────────────────────────────────────────────

_client: Optional[OpenAI] = None
_current_provider: str = ""
_current_base_url: str = ""
_current_api_key: str = ""


def _get_client() -> OpenAI:
    global _client, _current_provider, _current_base_url, _current_api_key

    provider = resolve_provider()
    base_url = resolve_base_url(provider)
    api_key = resolve_api_key(provider)
    timeout_val = _llm_section().get("timeout", 120)

    # Rebuild if config changed
    if _client is None or provider != _current_provider or base_url != _current_base_url or api_key != _current_api_key:
        _client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_val)
        _current_provider = provider
        _current_base_url = base_url
        _current_api_key = api_key

    return _client


def get_provider_info() -> dict:
    """Return current provider info for diagnostics."""
    provider = resolve_provider()
    default_model = _llm_section().get("default_model", "qwen3.6")
    alt_models = _llm_section().get("alt_models", {})
    return {
        "provider": provider,
        "model": resolve_model(provider),
        "flash_model": resolve_flash_model(provider),
        "base_url": resolve_base_url(provider),
        "default_model": default_model,
        "alt_models": alt_models,
    }


# ── multi-model support ───────────────────────────────────────────────────

_alt_clients: Dict[str, OpenAI] = {}

def list_models() -> Dict[str, dict]:
    """Return all configured models with their labels and base_urls."""
    section = _llm_section()
    alt = section.get("alt_models", {})
    default_key = section.get("default_model", "qwen3.6")
    result = {}
    for key, cfg in alt.items():
        result[key] = {
            "key": key,
            "label": cfg.get("label", key),
            "base_url": cfg.get("base_url", "http://localhost:1235/v1"),
            "is_default": key == default_key,
        }
    return result

def get_client_for(model_key: str = None) -> OpenAI:
    """Get (or create) an OpenAI client for a specific model.
    If model_key is None, returns default client.
    Uses cached client instances for performance."""
    global _alt_clients

    section = _llm_section()
    alt_models = section.get("alt_models", {})
    default_key = model_key or section.get("default_model", "qwen3.6")

    cfg = alt_models.get(default_key)
    if not cfg:
        # Fallback to default client
        return _get_client()

    base_url = cfg.get("base_url", section.get("base_url", "http://localhost:1235/v1"))
    api_key = section.get("api_key", "lm-studio-no-auth-needed")
    timeout_val = section.get("timeout", 120)

    if default_key not in _alt_clients:
        _alt_clients[default_key] = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_val)

    return _alt_clients[default_key]

def get_task_client(task: str) -> OpenAI:
    """Get an OpenAI client configured for a specific task type.

    Task types map to model keys via config.json llm.task_models:
      - "planning" → outline/settings/character design (default: qwen3.6)
      - "writing"  → prose/chapter generation (default: gemma4)
      - "reasoning" → analysis/detection (default: coder_next)

    Falls back to default client if task_models not configured.
    """
    section = _llm_section()
    task_models = section.get("task_models", {})
    model_key = task_models.get(task)
    if model_key:
        return get_client_for(model_key)
    return get_client_for()

def switch_default_model(model_key: str, base_url: str = None) -> bool:
    """Switch the default model. Clears all client caches. Returns True if successful."""
    global _client, _alt_clients
    models = list_models()
    # If base_url provided, use it; otherwise look up from config
    if not base_url:
        if model_key in models:
            base_url = models[model_key].get("base_url", "http://localhost:1235/v1")
        else:
            return False

    cfg = _load_config_json()
    cfg.setdefault("llm", {})["default_model"] = model_key
    cfg.setdefault("llm", {})["base_url"] = base_url
    # Also update/add to alt_models
    cfg.setdefault("llm", {}).setdefault("alt_models", {})[model_key] = {
        "base_url": base_url,
        "label": model_key
    }
    cfg_path = Path(__file__).parent.parent / "config.json"
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    # Clear all client caches
    _client = None
    _alt_clients = {}
    return True


# ── helpers ──────────────────────────────────────────────────────────────────

def _clean_response_content(content: str) -> str:
    if not content:
        return ""
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


def _llm_retry_config() -> tuple:
    """Return (max_retries, retry_delay) from config."""
    gen = _llm_section().get("generation", {})
    max_retries = gen.get("max_retries", 3)
    retry_delay = gen.get("retry_delay", 5)
    return max_retries, retry_delay


def _llm_temperature() -> float:
    return _llm_section().get("temperature", 0.85)


# ── public API ───────────────────────────────────────────────────────────────

def generate_json(prompt: str, schema_model, system_message: str = "你是一个专业的数据结构化助手。") -> dict:
    """模式 A: JSON 结构化输出，带重试机制"""
    max_retries, retry_delay = _llm_retry_config()
    provider = resolve_provider()
    model = resolve_model(provider)

    for attempt in range(max_retries):
        try:
            schema_str = json.dumps(schema_model.model_json_schema(), ensure_ascii=False)
            messages = [
                {"role": "system", "content": system_message + "\n请严格输出 JSON 格式，不要包含任何额外的 explanations。遵循以下 JSON Schema:\n" + schema_str},
                {"role": "user", "content": prompt}
            ]
            response = _get_client().chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1
            )
            content = _clean_response_content(response.choices[0].message.content)
            parsed_data = json.loads(content)
            schema_model.model_validate(parsed_data)
            return parsed_data

        except (json.JSONDecodeError, ValidationError) as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to generate valid JSON after {max_retries} attempts. Error: {str(e)}")
            prompt += f"\n\n上一次的输出存在格式错误：{str(e)}。请修正后重新输出纯净的 JSON。"
        except (APIError, APITimeoutError, OpenAIConnectionError) as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"API中断后重试失败: {str(e)}")
            print(f"\n[⚠️ API 中断] 第 {attempt + 1}/{max_retries} 次尝试失败，等待重试...")
            time.sleep(retry_delay * (attempt + 1))


class ProgressiveWriter:
    """
    流式生成器，支持渐进式保存。
    每生成一定字数就调用回调函数保存。
    """

    def __init__(self, on_progress=None, chunk_size: int = 1000, task: str = None):
        self.on_progress = on_progress
        self.chunk_size = chunk_size
        self.accumulated = []
        self.last_callback_count = 0
        self.task = task  # "planning" / "writing" / "reasoning" — None = default

    def write(self, prompt, system_message: str = "你是一个顶尖的网络小说执笔打字机。", chapter_id: int = None):
        """
        执行渐进式写作。
        Returns: 完整内容
        """
        max_retries, retry_delay = _llm_retry_config()

        for attempt in range(max_retries):
            try:
                return self._write_impl(prompt, system_message, chapter_id)
            except (APIError, APITimeoutError, OpenAIConnectionError) as e:
                print(f"\n[⚠️ API 中断] 第 {attempt + 1}/{max_retries} 次尝试失败: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    print(f"[⏳] 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(f"[🚨] 已达到最大重试次数 {max_retries}，放弃本次生成")
                    raise RuntimeError(f"API中断后重试失败: {str(e)}")

    def _write_impl(self, prompt, system_message: str, chapter_id: int = None):
        """内部实现"""
        if isinstance(prompt, list):
            prompt_content = "\n".join(prompt)
        else:
            prompt_content = str(prompt)

        provider = resolve_provider()
        model = resolve_model(provider)
        temperature = _llm_temperature()

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt_content}
        ]

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }

        response = (get_task_client(self.task) if self.task else _get_client()).chat.completions.create(**kwargs)

        self.accumulated = []
        self.last_callback_count = 0

        with Live(auto_refresh=False, vertical_overflow="visible") as live:
            for chunk in response:
                delta = chunk.choices[0].delta

                if hasattr(delta, 'content') and delta.content:
                    self.accumulated.append(delta.content)
                    accumulated_text = "".join(self.accumulated)

                    if self.on_progress and len(accumulated_text) - self.last_callback_count >= self.chunk_size:
                        self.last_callback_count = len(accumulated_text)
                        self.on_progress(chapter_id, accumulated_text, len(accumulated_text))

                    live.update(Markdown(accumulated_text), refresh=True)

        final_result = "".join(self.accumulated)

        if self.on_progress:
            self.on_progress(chapter_id, final_result, len(final_result))

        return final_result


def generate_stream(prompt, system_message: str = "你是一个顶尖的网络小说执笔打字机。", tools: list = None):
    """兼容旧接口的流式生成"""
    writer = ProgressiveWriter()
    return writer.write(prompt, system_message, None)


def extract_entities(prompt: str) -> List[str]:
    """模式 C: 实体提取"""
    provider = resolve_provider()
    flash_model = resolve_flash_model(provider)

    messages = [
        {"role": "system", "content": "你是一个轻量级的实体提取引擎。请提取用户文本中的人名、特殊功法名、重要法宝名、核心地名。直接输出 JSON 列表，结构如 [\"林动\", \"玄重尺\"]。不要解释，不要额外输出！"},
        {"role": "user", "content": f"提取以下网文大纲中的核心实体：\n{prompt}"}
    ]

    try:
        response = _get_client().chat.completions.create(
            model=flash_model,
            messages=messages,
            temperature=0.1
        )
        content = _clean_response_content(response.choices[0].message.content)
    except Exception as e:
        if "1301" in str(e):
            return []
        print(f"[WARN] 实体提取失败: {e}")
        return []

    try:
        entities = json.loads(content)
        if isinstance(entities, list):
            return entities
        return []
    except json.JSONDecodeError:
        return [e.strip() for e in content.split(",") if e.strip()]


def simple_complete(system: str, user: str, temperature: float = None) -> str:
    """Single-turn completion, no streaming. Good for short structured outputs."""
    provider = resolve_provider()
    model = resolve_model(provider)
    temp = temperature if temperature is not None else _llm_temperature()

    response = _get_client().chat.completions.create(
        model=model,
        temperature=temp,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""
