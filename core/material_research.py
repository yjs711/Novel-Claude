"""
素材研究模块 — 乌贼模式: 先素材, 后大纲

灵感: 乌贼写《诡秘之主》花半年读《伦敦传》+《维多利亚时期英国中产阶级婚姻家庭生活研究》
     先搞清楚"一条街几家店, 工人每天工作几小时, 花销占工资多少"再动笔

用法:
    researcher = MaterialResearcher(project_dir)
    researcher.research_materials(genre="修仙", style="古龙风格")  # 生成素材笔记
    notes = researcher.get_notes()  # 注入大纲/写作 prompt
"""
from __future__ import annotations
import json, time, re
from pathlib import Path
from typing import Optional

class MaterialResearcher:
    """素材研究员 — 生成世界设定细节素材"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self._file = self.project_dir / "materials" / "素材笔记.md"
        self.notes: dict = {}
        self.load()

    def load(self):
        if self._file.exists():
            self.notes["_raw"] = self._file.read_text(encoding="utf-8")

    def save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file, "w", encoding="utf-8") as f:
            f.write(self._format_notes())

    def research_materials(self, genre: str, style: str, extra_context: str = "") -> str:
        """
        调用 LLM 生成素材笔记。
        基于乌贼的工作流: 先收集真实世界的细节数据, 再构建架空世界。
        """
        from utils.llm_client import get_task_client, get_task_model, _llm_temperature

        client = get_task_client("planning")
        model = get_task_model("planning")
        temp = _llm_temperature("planning")

        system = f"""你是架空世界设定研究员。你的任务是生成一个{genre}世界的生活细节素材。
不要写大纲、不要写剧情、不要写人物。只写"这个世界的普通生活是什么样"。
参考乌贼写《诡秘之主》的方法: 先搞清楚一条街几家店, 工人每天工作几小时, 花销占工资多少。

请覆盖以下维度:
1. 经济: 货币体系, 普通人月收入, 日常开销(食物/住房/衣物)
2. 饮食: 普通人三餐吃什么, 富人吃什么, 特殊场合吃什么
3. 居住: 不同阶层住什么样的房子, 用什么家具, 照明取暖方式
4. 交通: 普通人如何出行, 富人如何出行, 长途运输方式
5. 服饰: 不同阶层/职业的着装差异, 材质, 颜色禁忌
6. 社会: 家庭结构, 婚姻习俗, 节日庆典, 丧葬礼仪
7. 教育: 谁能读书, 教什么, 怎么教
8. 医疗: 常见疾病, 治疗方法, 医生地位
9. 信仰: 主流信仰, 民间迷信, 禁忌, 祭祀方式
10. 权力: 统治结构, 法律, 税收, 刑罚

写作风格: {style}
体裁: {genre}
{extra_context}

输出 Markdown 格式, 每个维度1-2段, 包含具体数字和细节。不要空洞的概括。"""

        try:
            response = client.chat.completions.create(
                model=model, temperature=temp, max_tokens=2500,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"为{genre}小说(风格:{style})生成世界设定素材笔记。"}
                ],
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            text = response.choices[0].message.content
            self.notes["genre"] = genre
            self.notes["style"] = style
            self.notes["_raw"] = text
            self.notes["_generated_at"] = time.time()
            self.save()
            return text
        except Exception as e:
            return f"素材研究失败: {e}"

    def get_notes(self, max_chars: int = 1500) -> str:
        """获取素材笔记（截断注入 prompt）"""
        text = self.notes.get("_raw", "")
        if not text:
            return ""
        if len(text) > max_chars:
            return text[:max_chars] + f"\n\n...(共{len(text)}字, 已截断)"
        return text

    def _format_notes(self) -> str:
        """格式化素材笔记"""
        text = self.notes.get("_raw", "")
        header = f"# 素材笔记\n> 体裁: {self.notes.get('genre','')} | 风格: {self.notes.get('style','')} | 生成时间: {time.strftime('%Y-%m-%d')}\n\n"
        return header + text

    def inject_to_prompt(self, base_prompt: str, max_chars: int = 1200) -> str:
        """将素材笔记注入写作 prompt"""
        notes = self.get_notes(max_chars)
        if notes:
            return base_prompt + f"\n\n---\n**世界素材笔记（真实细节参考）**:\n{notes}"
        return base_prompt


class LooseForeshadowScanner:
    """伏笔随手扔 — 乌贼模式: 写完扫描, 不预设"""

    @staticmethod
    def scan_chapter(chapter_num: int, content: str) -> list[dict]:
        """
        扫描章节中可作为伏笔的"钩子点"。
        不预设什么应该是什么伏笔, 只是标记出来供以后使用。
        """
        hooks = []

        # 模式1: 未解释的异常现象
        patterns = [
            (r'不知为何.{0,20}(?:出现|发生|感觉|看到)', "异常现象"),
            (r'(?:似乎|仿佛|隐约|莫名).{0,15}(?:不对|奇怪|诡异|异常)', "异常感觉"),
            (r'暗中.{0,20}(?:注视|观察|跟踪|监视)', "暗中观察"),
            (r'(?:留下|藏着|存放).{0,20}(?:日后|将来|以后|某天)', "物品线索"),
            (r'(?:说到|提到).{0,30}(?:秘密|真相|往事|来历)', "信息线索"),
            (r'(?:从未|不曾|没有).{0,20}(?:提起|说过|解释)', "信息空缺"),
        ]

        for pat, hook_type in patterns:
            for m in re.finditer(pat, content):
                context = content[max(0, m.start()-30):m.end()+30]
                hooks.append({
                    "chapter": chapter_num,
                    "type": hook_type,
                    "text": m.group(0)[:60],
                    "context": context[:100],
                    "position": m.start(),
                })

        return hooks

    @staticmethod
    def find_reusable_hooks(project_dir: Path, current_chapter: int, recent_content: str) -> list[dict]:
        """
        检索之前扫描的所有钩子, 找出当前章节中可能可以"回收"的。
        乌贼原话: "很多时候前面是随便埋的...在后面写的时候可能就直接拿来用了"
        """
        hook_file = project_dir / "materials" / "loose_hooks.json"
        if not hook_file.exists():
            return []

        data = json.loads(hook_file.read_text(encoding="utf-8"))
        all_hooks = data.get("hooks", [])

        # 过滤: 太近的不需要回收 (留20章以上距离)
        usable = [h for h in all_hooks if h["chapter"] < current_chapter - 20]

        # 匹配: 当前内容中的关键词是否能对上之前钩子的上下文中关键词
        matched = []
        for h in usable:
            ctx_words = set(re.findall(r'[一-鿿]{2,4}', h["context"]))
            recent_words = set(re.findall(r'[一-鿿]{2,4}', recent_content[:2000]))
            overlap = ctx_words & recent_words
            if len(overlap) >= 2:
                h["match_score"] = len(overlap)
                matched.append(h)

        return sorted(matched, key=lambda x: -x["match_score"])[:5]

    @staticmethod
    def save_hooks(project_dir: Path, chapter_num: int, content: str):
        """保存扫描到的钩子"""
        hooks = LooseForeshadowScanner.scan_chapter(chapter_num, content)
        hook_file = project_dir / "materials" / "loose_hooks.json"
        hook_file.parent.mkdir(parents=True, exist_ok=True)

        existing = []
        if hook_file.exists():
            existing = json.loads(hook_file.read_text(encoding="utf-8")).get("hooks", [])

        existing.extend(hooks)
        hook_file.write_text(json.dumps({"hooks": existing, "updated": time.time()}, ensure_ascii=False, indent=2), encoding="utf-8")
