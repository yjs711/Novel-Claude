"""
wf_writing_formula — 写法提取与复用 Skill

从 AI-Novel-Writing-Assistant WritingFormulaService 移植。
从已有文本提取写法特征 → 保存为可复用资产 → 注入到新章节。
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from core.base_skill import BaseSkill


class WfWritingFormulaSkill(BaseSkill):
    def __init__(self, context):
        super().__init__(context)
        self.name = "写法引擎"
        self._formulas: Dict[str, dict] = {}
        self._formulas_dir: Optional[Path] = None

    def on_init(self) -> None:
        novel_dir = Path(self.context.workspace.NOVEL_DIR) if hasattr(self.context.workspace, "NOVEL_DIR") else Path(".novel")
        self._formulas_dir = novel_dir / "formulas"
        self._formulas_dir.mkdir(parents=True, exist_ok=True)

        # 加载已有写法
        for f in self._formulas_dir.glob("*.json"):
            with open(f, "r", encoding="utf-8") as fh:
                formula = json.load(fh)
                self._formulas[f.stem] = formula

        self.context.set_shared("writing_formulas", {
            "available": list(self._formulas.keys()),
            "active": None,
        })
        print(f"  [✓] {self.name} 已就绪（{len(self._formulas)}个已保存写法）")

    def on_before_scene_write(self, prompt_payload: list, beat_data: dict) -> list:
        """注入活跃写法"""
        formula_config = self.context.get_shared("writing_formulas", {})
        active_name = formula_config.get("active")
        if active_name and active_name in self._formulas:
            formula = self._formulas[active_name]
            block = self._format_formula_injection(formula)
            prompt_payload.insert(0, f"[写法: {active_name}]\n{block}\n")
        return prompt_payload

    def extract_formula(self, text: str, name: str) -> dict:
        """从文本中提取写法特征"""
        formula = {
            "name": name,
            "extracted_at": "",
            "features": {},
        }

        # 1. 句式偏好 — 句长分布
        sentences = re.split(r'[。！？\n]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
        if sentences:
            lengths = [len(s) for s in sentences]
            formula["features"]["avg_sentence_length"] = sum(lengths) / len(lengths)
            formula["features"]["min_sentence_length"] = min(lengths)
            formula["features"]["max_sentence_length"] = max(lengths)
            formula["features"]["sentence_count"] = len(sentences)

        # 2. 段落模式 — 每段句数
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        para_sentence_counts = []
        for para in paragraphs:
            para_sents = len(re.split(r'[。！？]', para))
            para_sentence_counts.append(para_sents)
        if para_sentence_counts:
            formula["features"]["avg_sentences_per_paragraph"] = sum(para_sentence_counts) / len(para_sentence_counts)

        # 3. 修辞手法 — 常见修辞词
        rhetoric_patterns = {
            "比喻": len(re.findall(r'(仿佛|好像|如同|像|似|犹如)', text)),
            "排比": len(re.findall(r'(.{2,30})\1{2,}', text)),
            "反问": len(re.findall(r'[难道|岂|怎么][^？]*[？]', text)),
            "拟人": len(re.findall(r'(呼啸|咆哮|低语|歌唱)(?=.*[风月星])', text)),
        }
        formula["features"]["rhetoric"] = {k: v for k, v in rhetoric_patterns.items() if v > 0}

        # 4. 对话占比
        dialogue_lines = len(re.findall(r'[「""][^「""」]+[」""]', text))
        total_chars = len(text)
        formula["features"]["dialogue_ratio"] = dialogue_lines / max(sentences.count(True), 1) if sentences else 0

        # 5. 高频词
        all_words = re.findall(r'[一-鿿]{2,4}', text)
        word_freq = {}
        for w in all_words:
            word_freq[w] = word_freq.get(w, 0) + 1
        top_words = sorted(word_freq.items(), key=lambda x: -x[1])[:20]
        formula["features"]["top_words"] = [w for w, c in top_words if c >= 3]

        # 保存
        from datetime import datetime
        formula["extracted_at"] = datetime.now().isoformat()
        self._formulas[name] = formula

        formula_path = self._formulas_dir / f"{name}.json"
        with open(formula_path, "w", encoding="utf-8") as f:
            json.dump(formula, f, ensure_ascii=False, indent=2)

        self.context.set_shared("writing_formulas", {
            "available": list(self._formulas.keys()),
            "active": name,
        })
        print(f"  [✓] 写法已提取: {name}")

        return formula

    def _format_formula_injection(self, formula: dict) -> str:
        """将写法格式化为 prompt 注入"""
        features = formula.get("features", {})
        lines = ["按以下写法特征写作:"]

        if "avg_sentence_length" in features:
            lines.append(f"- 平均句长约{features['avg_sentence_length']:.0f}字")
        if "avg_sentences_per_paragraph" in features:
            lines.append(f"- 平均每段{features['avg_sentences_per_paragraph']:.0f}句")
        if "rhetoric" in features and features["rhetoric"]:
            rhe = ", ".join(f"{k}×{v}" for k, v in features["rhetoric"].items())
            lines.append(f"- 修辞偏好: {rhe}")
        if "top_words" in features and features["top_words"]:
            lines.append(f"- 高频词汇: {', '.join(features['top_words'][:10])}")

        return "\n".join(lines)

    def set_active(self, name: str):
        """设置活跃写法"""
        if name in self._formulas:
            self.context.set_shared("writing_formulas", {
                "available": list(self._formulas.keys()),
                "active": name,
            })
            print(f"  [✓] 写法已激活: {name}")
        else:
            print(f"  [⚠️] 未知写法: {name}，可用: {list(self._formulas.keys())}")

    def list_formulas(self) -> List[str]:
        return list(self._formulas.keys())
