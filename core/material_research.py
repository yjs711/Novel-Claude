"""
真实素材研究模块 — 乌贼模式 v2: 联网搜索 + 本地模型整理

v1: LLM编造(不可靠)
v2: WebSearch获取真实数据 → 本地模型结构化整理(可追溯,可验证)

流程:
    用户指定时代/题材
    → 联网搜索真实历史数据(经济/饮食/居住/交通/服饰/社会)
    → 本地模型整理成结构化素材笔记
    → 注入写作prompt
"""
from __future__ import annotations
import json, time, re
from pathlib import Path
from typing import Optional

class MaterialResearcher:
    """素材研究员 — 联网搜索 + 本地模型整理"""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self._file = self.project_dir / "materials" / "素材笔记.md"
        self._source_file = self.project_dir / "materials" / "素材来源.txt"
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
        v2: 联网搜索真实数据 + 本地模型整理

        步骤:
        1. 根据题材确定搜索关键词 (genre → 真实历史对应)
        2. 逐维度搜索真实数据
        3. 本地模型整理+结构化
        """
        # 搜索维度
        dimensions = {
            "经济货币": f"{genre} 古代 货币 物价 工资 日常开销",
            "饮食起居": f"{genre} 古代 饮食 食物 三餐 烹饪",
            "居住建筑": f"{genre} 古代 房屋 建筑 家具 照明 取暖",
            "交通出行": f"{genre} 古代 交通 出行 马 船 马车",
            "服饰着装": f"{genre} 古代 服饰 衣服 材质 等级",
            "社会结构": f"{genre} 古代 家庭 婚姻 宗族 科举 官制",
        }

        all_search_results = []
        print(f"  [素材] 联网搜索 {genre} 的真实历史数据...")

        # 逐维度搜索 (使用内置 WebSearch)
        try:
            # 这里用 Python 的 requests 直接搜, 绕开 LLM 编造
            import urllib.request, urllib.parse
            for dim, query in dimensions.items():
                encoded = urllib.parse.quote(query)
                url = f"https://www.google.com/search?q={encoded}"
                # 简单提取搜索结果片段 (不使用LLM)
                try:
                    req = urllib.request.Request(url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    r = urllib.request.urlopen(req, timeout=10)
                    html = r.read().decode('utf-8', errors='ignore')
                    # 提取搜索结果摘要
                    snippets = re.findall(r'<span[^>]*>([^<]{20,200})</span>', html)
                    relevant = [s for s in snippets[:15] if not any(w in s.lower() for w in ['script','style','class','function'])]
                    all_search_results.append(f"\n## {dim}\n" + "\n".join(relevant[:5]))
                except Exception as e:
                    all_search_results.append(f"\n## {dim}\n(搜索暂时不可用: {e})")
                    # 降级: 用 genre 知识库中的模板数据
                    fallback = self._fallback_knowledge(genre, dim)
                    if fallback:
                        all_search_results.append(fallback)
        except Exception as e:
            print(f"  [素材] 搜索失败: {e}, 使用内置知识库")
            all_search_results.append(self._fallback_all(genre))

        raw_material = "\n".join(all_search_results)
        if not raw_material.strip():
            raw_material = f"# {genre} 基础设定\n(搜索不可用, 请手动补充素材)"

        # 保存搜索来源
        source_text = f"# 素材来源\n生成时间: {time.strftime('%Y-%m-%d %H:%M')}\n体裁: {genre}\n\n搜索维度:\n"
        for dim, query in dimensions.items():
            source_text += f"- {dim}: {query}\n"
        self._source_file.write_text(source_text, encoding="utf-8")

        # 本地模型整理
        structured = self._structure_with_local_model(raw_material, genre, style)

        self.notes["genre"] = genre
        self.notes["style"] = style
        self.notes["_raw"] = structured
        self.notes["_sources"] = source_text
        self.notes["_generated_at"] = time.time()
        self.save()
        return structured

    def _structure_with_local_model(self, raw_material: str, genre: str, style: str) -> str:
        """用本地模型结构化搜索结果 (不是编造, 是整理)"""
        from utils.llm_client import get_task_client, get_task_model, _llm_temperature

        client = get_task_client("planning")
        model = get_task_model("planning")

        system = """你是素材整理员。你的任务是把搜索到的真实历史数据整理成结构化的世界设定素材。

规则:
1. 只使用下面提供给你的搜索结果, 不要编造任何数据
2. 如果搜索结果缺乏某个领域的信息, 标注「该领域待补充」, 不要猜测填补
3. 按维度分类整理: 经济/饮食/居住/交通/服饰/社会/教育/医疗/信仰/权力
4. 保留具体数字(价格/尺寸/时长), 这些是写作时的真实细节
5. 输出 Markdown 格式, 简洁清晰"""

        try:
            response = client.chat.completions.create(
                model=model, temperature=0.3, max_tokens=2000,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"以下是关于{genre}的真实搜索数据, 请整理成素材笔记:\n\n{raw_material[:4000]}"}
                ],
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"素材整理失败: {e}\n\n原始数据:\n{raw_material[:2000]}"

    def _fallback_knowledge(self, genre: str, dimension: str) -> str:
        """内置知识库 — 搜索不可用时的降级方案"""
        knowledge = {
            "修仙": {
                "经济货币": "参考中国古代: 1两黄金=10两白银=10000文铜钱。普通工人月入1-2两银。1两银可买100斤大米。灵石作为修仙界硬通货, 下品灵石约等于100两白银。",
                "饮食起居": "参考唐宋: 主食为粟/麦/稻。平民一日两餐(朝食/晡食)。调味品: 盐/酱/醋/豉。肉食以羊/鸡/鱼为主, 牛肉因耕牛保护极少食用。",
                "居住建筑": "平民住夯土或木结构平房, 一明两暗三开间。窗户用纸糊。照明靠油灯或蜡烛。取暖靠炭盆或火炕。",
                "交通出行": "平民步行或骑驴。士人乘马车/牛车。长途靠驿道或水路。修仙者御剑/飞行法宝。",
                "服饰着装": "等级森严: 官员着丝绸, 平民穿麻布/棉布。颜色有禁忌(明黄禁庶人)。道袍代表修仙者身份。",
                "社会结构": "士农工商四民。家族宗法制。科举取士。修仙门派类似于官僚系统。",
            },
            "都市": {
                "经济货币": "现代社会, 人民币元。2020年代平均月薪5000-15000元。一线城市房租3000-8000元/月。",
                "饮食起居": "外卖/快餐/家常菜。一日三餐。奶茶/咖啡文化。",
                "居住建筑": "公寓/小区。北上广深房价3-10万/平。租房是年轻人常态。",
                "交通出行": "地铁/公交/网约车/共享单车。一线城市通勤30-90分钟。",
                "服饰着装": "T恤/牛仔裤/运动鞋为日常。职场正装。品牌消费。",
                "社会结构": "996工作制。互联网大厂。创业潮。内卷。",
            },
        }
        genre_kb = knowledge.get(genre, {})
        return genre_kb.get(dimension, "")

    def _fallback_all(self, genre: str) -> str:
        """全维度降级数据"""
        parts = []
        for dim in ["经济货币","饮食起居","居住建筑","交通出行","服饰着装","社会结构"]:
            fb = self._fallback_knowledge(genre, dim)
            if fb:
                parts.append(f"## {dim}\n{fb}")
        return "\n\n".join(parts) if parts else f"# {genre} 基础设定\n(无可用数据)"

    def get_notes(self, max_chars: int = 1500) -> str:
        text = self.notes.get("_raw", "")
        if not text: return ""
        return text[:max_chars] + (f"\n\n...(共{len(text)}字, 已截断)" if len(text) > max_chars else "")

    def _format_notes(self) -> str:
        text = self.notes.get("_raw", "")
        header = f"# 素材笔记\n> 体裁: {self.notes.get('genre','')} | 风格: {self.notes.get('style','')} | 生成: {time.strftime('%Y-%m-%d')}"
        source = f"\n\n---\n## 搜索来源\n{self.notes.get('_sources','(无)')[:500]}"
        return header + "\n\n" + text + source

    def inject_to_prompt(self, base_prompt: str, max_chars: int = 1200) -> str:
        notes = self.get_notes(max_chars)
        if notes:
            return base_prompt + f"\n\n---\n**世界素材笔记（真实搜索数据整理）**:\n{notes}"
        return base_prompt


# 保留伏笔模块
class LooseForeshadowScanner:
    """伏笔随手扔 — 乌贼模式"""

    @staticmethod
    def scan_chapter(chapter_num: int, content: str) -> list[dict]:
        hooks = []
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
                hooks.append({"chapter": chapter_num, "type": hook_type, "text": m.group(0)[:60], "context": context[:100], "position": m.start()})
        return hooks

    @staticmethod
    def find_reusable_hooks(project_dir: Path, current_chapter: int, recent_content: str) -> list[dict]:
        hook_file = project_dir / "materials" / "loose_hooks.json"
        if not hook_file.exists(): return []
        data = json.loads(hook_file.read_text(encoding="utf-8"))
        all_hooks = data.get("hooks", [])
        usable = [h for h in all_hooks if h["chapter"] < current_chapter - 20]
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
        hooks = LooseForeshadowScanner.scan_chapter(chapter_num, content)
        hook_file = project_dir / "materials" / "loose_hooks.json"
        hook_file.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if hook_file.exists(): existing = json.loads(hook_file.read_text(encoding="utf-8")).get("hooks", [])
        existing.extend(hooks)
        hook_file.write_text(json.dumps({"hooks": existing, "updated": time.time()}, ensure_ascii=False, indent=2), encoding="utf-8")
