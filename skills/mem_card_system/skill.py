"""
mem_card_system — 卡片系统 Skill

从 WenShape 卡片系统移植。YAML + Markdown 双格式。
人物卡/世界观卡/文风卡，自动与 Novel-Claude settings/ 同步。

支持 @DSL 语法: @card:角色名 → 自动注入完整卡片
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from core.base_skill import BaseSkill


class MemCardSystemSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "卡片系统"
        self._cards_dir: Optional[Path] = None

    def on_init(self) -> None:
        novel_dir = Path(self.context.workspace.NOVEL_DIR) if hasattr(self.context.workspace, "NOVEL_DIR") else Path(".novel")
        self._cards_dir = novel_dir / "cards"
        self._cards_dir.mkdir(parents=True, exist_ok=True)
        (self._cards_dir / "characters").mkdir(exist_ok=True)
        (self._cards_dir / "world").mkdir(exist_ok=True)

        # 从 settings 同步初始卡片
        self._sync_from_settings()
        print(f"  [✓] {self.name} 已就绪（{self._cards_dir}）")

    def _sync_from_settings(self):
        """从 Novel-Claude settings/ 同步到卡片目录"""
        settings = Path(self.context.workspace.SETTINGS_DIR) if hasattr(self.context.workspace, "SETTINGS_DIR") else Path(".novel/settings")
        blueprint = settings / "core_blueprint.json"
        if not blueprint.exists():
            return

        with open(blueprint, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 角色卡
        for char in data.get("characters", []):
            name = char.get("name", "unknown")
            card_path = self._cards_dir / "characters" / f"{name}.yaml"
            if not card_path.exists():
                card = {
                    "name": name,
                    "aliases": char.get("aliases", []),
                    "description": self._format_char_card(char),
                    "stars": char.get("stars", 3),
                }
                with open(card_path, "w", encoding="utf-8") as f:
                    yaml.dump(card, f, allow_unicode=True, default_flow_style=False)

        # 世界观卡
        world_setting = settings / "world_setting.json"
        if world_setting.exists():
            with open(world_setting, "r", encoding="utf-8") as f:
                ws = json.load(f)
            for key, value in ws.items():
                card_path = self._cards_dir / "world" / f"{key}.yaml"
                if not card_path.exists():
                    card = {"name": key, "description": str(value)[:2000], "category": "world_setting"}
                    with open(card_path, "w", encoding="utf-8") as f:
                        yaml.dump(card, f, allow_unicode=True, default_flow_style=False)

    def _format_char_card(self, char: dict) -> str:
        parts = []
        if char.get("type"):
            parts.append(f"身份: {char['type']}")
        if char.get("description"):
            parts.append(f"外貌: {char['description']}")
        if char.get("personality"):
            parts.append(f"性格: {char['personality']}")
        if char.get("desire"):
            parts.append(f"动机: {char['desire']}")
        if char.get("arc"):
            parts.append(f"角色弧线: {char['arc']}")
        return "  \n".join(parts) if parts else "待补充"

    def on_before_scene_write(self, prompt_payload: list, beat_data: dict) -> list:
        """处理 @card:角色名 引用"""
        resolved = []
        for item in prompt_payload:
            if isinstance(item, str) and "@card:" in item:
                item = self._resolve_card_refs(item)
            resolved.append(item)
        return resolved

    def _resolve_card_refs(self, text: str) -> str:
        """替换 @card:角色名 为卡片内容"""
        import re
        def replace_card(match):
            full_match = match.group(0)
            card_name = match.group(1).strip()
            card = self.get_card(card_name)
            if card:
                if card_name in self._list_characters():
                    return f"[角色卡: {card_name}]\n{card.get('description', card.get('name', card_name))}\n"
                else:
                    return f"[世界观: {card_name}]\n{card.get('description', str(card))}\n"
            return full_match

        return re.sub(r'@card:([^\s\n]+)', replace_card, text)

    def get_card(self, name: str) -> Optional[dict]:
        """查找卡片（先角色后世界观）"""
        char_path = self._cards_dir / "characters" / f"{name}.yaml"
        if char_path.exists():
            with open(char_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        world_path = self._cards_dir / "world" / f"{name}.yaml"
        if world_path.exists():
            with open(world_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return None

    def _list_characters(self) -> List[str]:
        chars_dir = self._cards_dir / "characters"
        if not chars_dir.exists():
            return []
        return [p.stem for p in chars_dir.glob("*.yaml")]

    def list_cards(self) -> dict:
        """列出所有卡片"""
        result = {"characters": [], "world": []}
        chars_dir = self._cards_dir / "characters"
        if chars_dir.exists():
            result["characters"] = [p.stem for p in chars_dir.glob("*.yaml")]
        world_dir = self._cards_dir / "world"
        if world_dir.exists():
            result["world"] = [p.stem for p in world_dir.glob("*.yaml")]
        return result

    def create_character_card(self, name: str, description: str, **kwargs):
        """创建角色卡片"""
        card = {"name": name, "description": description, "stars": kwargs.get("stars", 3)}
        card.update({k: v for k, v in kwargs.items() if k not in ("name", "description", "stars")})
        card_path = self._cards_dir / "characters" / f"{name}.yaml"
        with open(card_path, "w", encoding="utf-8") as f:
            yaml.dump(card, f, allow_unicode=True, default_flow_style=False)
        print(f"  [✓] 角色卡已创建: {name}")

    def create_world_card(self, name: str, description: str, **kwargs):
        """创建世界观卡片"""
        card = {"name": name, "description": description, "category": kwargs.get("category", "general")}
        card_path = self._cards_dir / "world" / f"{name}.yaml"
        with open(card_path, "w", encoding="utf-8") as f:
            yaml.dump(card, f, allow_unicode=True, default_flow_style=False)
        print(f"  [✓] 世界观卡已创建: {name}")
