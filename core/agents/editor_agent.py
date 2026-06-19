import json
import os
from utils.llm_client import _get_client

class EditorAgent:
    """
    负责对 s03 生成的初稿进行严厉审查和修改的复杂智能体。
    它具有多轮思考 (ReAct) 的能力。
    """
    def __init__(self, max_iterations=3):
        self.name = "ToxicEditorAgent"
        self.max_iterations = max_iterations
        
        default_prompt = """你是起点中文网的资深责任编辑。你审稿的标准就一条：这章能不能让读者点下一章。

审稿维度（按起点编辑真实标准）：
1. 前300字有没有抓住你 — 不能是设定介绍、不能是平淡日常、必须有事发生
2. 主角有没有主动性 — 主角在做事还是被事做？主角推动剧情还是被剧情推着走？
3. 爽点/钩子有没有到位 — 章末有没有让读者必须点下一章的东西
4. 有没有"人味" — 不是华丽的词藻，是真实的情绪颗粒度：尴尬、不甘、窃喜、后怕
5. 对话像不像活人说的 — 不说教、不哲学讨论、不解释剧情、有潜台词
6. 有没有过度解释 — 不总结道理、不让角色突然悟道、不让叙述者跳出来讲人生

你必须在思考后先后调用 submit_quality_review（评分）和 submit_final_revision（润色后的正文）。"""

        self.system_prompt = os.getenv("PROMPT_S03_EDITOR", default_prompt)
        self.last_review_result = None  # stores structured review after run()

    def get_tools(self):
        return [{
            "type": "function",
            "function": {
                "name": "submit_final_revision",
                "description": "当你完成了审稿、润色、修改（消除割裂感和视角跳跃）后，调用此工具提交符合字数要求的最终定稿小说正文。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "critique": {"type": "string", "description": "你对刚才这段草稿的评价和做出的修改说明"},
                        "final_text": {"type": "string", "description": "修改润色后可以直接发布的小说正文内容（不要包含任何评论）"}
                    },
                    "required": ["critique", "final_text"]
                }
            }
        }, {
            "type": "function",
            "function": {
                "name": "submit_quality_review",
                "description": "提交对章节的多维度质量评分。在润色前先调用此工具输出评分，然后再润色。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "overall_score": {"type": "integer", "description": "0-100 综合评分"},
                        "consistency_score": {"type": "integer", "description": "情节一致性 0-100"},
                        "pacing_score": {"type": "integer", "description": "节奏控制 0-100"},
                        "dialogue_score": {"type": "integer", "description": "对话质量 0-100"},
                        "prose_score": {"type": "integer", "description": "文笔质量 0-100"},
                        "over_explain_score": {"type": "integer", "description": "反过度解释 0-100 (StoryScope:77%AI vs 52%人类直接解释主题，越低代表越像AI)"},
                        "issues": {"type": "array", "items": {"type": "string"}, "description": "发现的主要问题列表"},
                        "strengths": {"type": "array", "items": {"type": "string"}, "description": "本章优点"}
                    },
                    "required": ["overall_score", "consistency_score", "pacing_score", "dialogue_score", "prose_score", "over_explain_score", "issues"]
                }
            }
        }]

    def run(self, raw_draft: str, beat_requirements: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"【大纲要求】：\\n{beat_requirements}\\n\\n【流水线初稿内容】：\\n{raw_draft}\\n\\n请严格审查，抹除 '***' 分界符，并调用 submit_final_revision 工具提交最终修改结果。"}
        ]

        print(f"\\n[{self.name}] 开始审阅并精修文稿...")

        for iteration in range(self.max_iterations):
            print(f"  -> 第 {iteration + 1} 轮推理...")

            from utils.llm_client import resolve_provider, resolve_model, _get_client
            client = _get_client()
            model = resolve_model(resolve_provider())
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=self.get_tools(),
                temperature=0.3
            )

            msg = response.choices[0].message

            # Record thought
            if msg.content:
                print(f"  [thought]: {msg.content.strip()[:120]}...")
                messages.append({"role": "assistant", "content": msg.content})

            # Execute tool calls
            if getattr(msg, 'tool_calls', None):
                for tool_call in msg.tool_calls:
                    args = json.loads(tool_call.function.arguments)

                    if tool_call.function.name == "submit_quality_review":
                        self.last_review_result = {
                            "score": args.get("overall_score", 75),
                            "issues": args.get("issues", []),
                            "sub_scores": [
                                {"name": "一致性", "score": args.get("consistency_score", 75), "issues": []},
                                {"name": "节奏", "score": args.get("pacing_score", 75), "issues": []},
                                {"name": "对话", "score": args.get("dialogue_score", 75), "issues": []},
                                {"name": "文笔", "score": args.get("prose_score", 75), "issues": []},
                                {"name": "反过度解释", "score": args.get("over_explain_score", 75),
                                 "issues": ["直接解释主题/角色顿悟讲道理/章末总结教训"] if args.get("over_explain_score", 75) < 60 else []},
                            ],
                        }
                        print(f"  [score] Editor评分: {self.last_review_result['score']}/100, {len(self.last_review_result['issues'])}个问题")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": "评分已记录。现在请调用 submit_final_revision 提交润色后的正文。"
                        })
                        continue

                    if tool_call.function.name == "submit_final_revision":
                        try:
                            from rich.console import Console
                            Console().print(f"[bold green]  [Editor Critique]:[/bold green] {args.get('critique', '')[:200]}")
                        except Exception:
                            print(f"  [Editor Critique]: {args.get('critique', '')[:200]}")

                        print(f"[{self.name}] 定稿完成。")
                        return args.get("final_text", raw_draft)

                # If we got tool calls but none were submit_final_revision
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls
                    ]
                })
                continue

            # No tool calls — prompt model to use tools
            if iteration < self.max_iterations - 1:
                messages.append({
                    "role": "user",
                    "content": "请先调用 submit_quality_review 评分，然后调用 submit_final_revision 提交润色后的正文。"
                })
            else:
                return msg.content if msg.content else raw_draft

        print(f"[{self.name}] 达到最大交互次数兜底返回。")
        return raw_draft

    def review_with_score(self, raw_draft: str, beat_requirements: str) -> dict:
        """
        Run review and return structured score + revised text.
        Returns: {score, issues, sub_scores, revised_text, critique}
        """
        revised_text = self.run(raw_draft, beat_requirements)
        review = self.last_review_result or {
            "score": 75,
            "issues": ["编辑未输出评分"],
            "sub_scores": [],
        }
        review["revised_text"] = revised_text
        return review
