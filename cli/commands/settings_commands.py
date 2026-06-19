"""Settings commands for Novel-Claude CLI."""
import json
import os
from pathlib import Path
from typing import List, Any, Dict


CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def handle(args: List[str]) -> Dict[str, Any]:
    """Handle settings command with no subcommand."""
    return {'message': 'Use: settings show, settings set <key> <value>'}


def show(args: List[str]) -> Dict[str, Any]:
    """Show current settings from config.json."""
    try:
        from utils.config import NOVEL_NAME, NOVEL_DIR
        cfg = _load_config()
        llm = cfg.get("llm", {})

        output = ["Current Configuration:"]
        output.append(f"  Provider: {llm.get('provider', 'lmstudio')}")
        output.append(f"  Model: {llm.get('model', 'auto')}")
        output.append(f"  Base URL: {llm.get('base_url', 'auto')}")
        output.append(f"  Novel: {NOVEL_NAME or '(not set)'}")
        output.append(f"  Novel Dir: {NOVEL_DIR}")
        output.append(f"  Genre: {cfg.get('genre', '(not set)')}")
        output.append(f"  Workflow Mode: {cfg.get('workflow', {}).get('mode', 'quick')}")
        output.append(f"  Quality Gate: {'enabled' if cfg.get('quality_gate', {}).get('enabled') else 'disabled'}")

        return {'message': '\n'.join(output)}
    except Exception as e:
        return {'error': f'settings show failed: {e}'}


def set_value(args: List[str]) -> Dict[str, Any]:
    """Set a config value in config.json (dot-notation: 'llm.provider' or 'genre')."""
    if len(args) < 2:
        return {'error': 'Usage: settings set <key> <value>'}

    key = args[0]
    value = args[1]

    # Auto-convert values
    if isinstance(value, str):
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        else:
            try:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                pass  # keep as string

    try:
        cfg = _load_config()

        # Dot-notation: "llm.model" -> cfg["llm"]["model"]
        parts = key.split(".")
        target = cfg
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value

        _save_config(cfg)
        from utils.config_loader import reload_config
        reload_config()
        return {'message': f'{key} = {value} (saved to config.json)'}
    except Exception as e:
        return {'error': f'settings set failed: {e}'}