"""
世界观上下文注入器 — 写前自动注入相关世界规则

基于 NovelForge 2026 "故事圣经截断注入" + QMAI "混合检索" 模式
从项目世界观文件中提取与当前章节相关的设定，注入写作 prompt
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Optional

class WorldContextInjector:
    """世界观上下文管理器"""

    @staticmethod
    def _get_project_base(novel_name: str = "") -> Path:
        return Path(f".novel_{novel_name}" if novel_name else ".novel")

    @staticmethod
    def get_world_summary(novel_name: str = "", max_chars: int = 2000) -> str:
        """获取世界观摘要（截断注入）"""
        base = WorldContextInjector._get_project_base(novel_name)
        world_file = base / "世界观.md"
        if not world_file.exists():
            return ""
        content = world_file.read_text(encoding="utf-8")
        if len(content) > max_chars:
            # 智能截断: 取前800字 + 最后200字(通常包含最新设定)
            return content[:max_chars - 200] + "\n\n...\n\n" + content[-200:]
        return content

    @staticmethod
    def get_relevant_settings(novel_name: str, chapter_content: str, max_chars: int = 1500) -> str:
        """
        BM25 风格关键词匹配: 从世界观文件中提取与当前章节相关的设定
        """
        base = WorldContextInjector._get_project_base(novel_name)
        world_file = base / "世界观.md"
        settings_dir = base / "设定"

        relevant_parts = []

        # 1. 从 世界观.md 提取
        if world_file.exists():
            world_text = world_file.read_text(encoding="utf-8")
            # 按 ## 分段
            sections = re.split(r'\n##\s+', world_text)
            if len(sections) > 1:
                header = sections[0]  # 标题段
                sections = sections[1:]  # 内容段

                # 从章节内容中提取关键词
                keywords = set()
                # 修炼相关
                for pat in ["练气","筑基","金丹","元婴","化神","渡劫","大乘","真仙",
                            "灵根","功法","丹药","法宝","灵石","阵法","符箓","剑诀"]:
                    if pat in chapter_content:
                        keywords.add(pat)

                # 匹配相关段落
                matched = []
                for sec in sections:
                    score = sum(1 for kw in keywords if kw in sec)
                    if score > 0:
                        title = sec.split("\n")[0][:40]
                        matched.append((score, title, sec[:300]))

                matched.sort(key=lambda x: -x[0])
                for _, title, text in matched[:4]:
                    relevant_parts.append(f"【{title}】\n{text}")

        # 2. 从 设定/ 目录补充
        if settings_dir.exists():
            for sf in sorted(settings_dir.glob("*.md"))[:5]:
                stext = sf.read_text(encoding="utf-8")[:400]
                relevant_parts.append(f"---\n{stext}")

        result = "\n\n".join(relevant_parts)
        if len(result) > max_chars:
            result = result[:max_chars]
        return result

    @staticmethod
    def inject_context(base_prompt: str, novel_name: str = "", chapter_content: str = "") -> str:
        """注入世界观上下文到 prompt"""
        world = WorldContextInjector.get_world_summary(novel_name)
        if world:
            base_prompt += f"\n\n---\n**世界观设定（故事圣经）**:\n{world[:1200]}"

        relevant = WorldContextInjector.get_relevant_settings(novel_name, chapter_content)
        if relevant:
            base_prompt += f"\n\n---\n**章节相关设定**:\n{relevant}"

        return base_prompt
