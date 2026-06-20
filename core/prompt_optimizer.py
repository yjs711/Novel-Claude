"""
DSPy 提示词优化器 — 连接本地 llama-router 自动优化写作 Prompt

用法:
    optimizer = PromptOptimizer()
    result = optimizer.optimize("writing", training_examples=[...])
    print(optimizer.get_best_prompt("writing"))
"""
from __future__ import annotations
import json, time, io
from pathlib import Path
from typing import Optional

import dspy


class PromptOptimizer:
    """使用 DSPy 自动优化 Novel-Claude 的模型提示词"""

    def __init__(self, router_url: str = "http://localhost:61183/v1",
                 model_name: str = "qwen3.6-27b-uncensored"):
        self.router_url = router_url
        self.model_name = model_name
        self._configured = False

    def _configure(self):
        """连接本地 llama-router（关闭思考模式，避免 token 被吃）"""
        if not self._configured:
            lm = dspy.LM(
                f"openai/{self.model_name}",
                api_base=self.router_url,
                api_key="not-needed",
                temperature=0.7,
                max_tokens=2000,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            dspy.configure(lm=lm)
            self._configured = True
            print(f"  [✓] DSPy 已连接 llama-router: {self.model_name}")

    def optimize_writer_prompt(self, examples: list[dict[str, str]], iterations: int = 5) -> dict:
        """
        优化写作 prompt

        examples: [{"input": "场景描述", "output": "期望的好文本"}, ...]
        iterations: 搜索迭代次数
        """
        self._configure()

        # 定义 DSPy Signature
        class WriterPrompt(dspy.Signature):
            """根据场景描述写出高质量网文段落。直接描写，不用比喻。对话有推进。感官丰富。"""
            scene = dspy.InputField(desc="输入的场景描述")
            output = dspy.OutputField(desc="生成的网文段落")

        # 构建训练集
        trainset = [
            dspy.Example(scene=ex["input"], output=ex["output"]).with_inputs("scene")
            for ex in examples
        ]

        # 定义评分指标
        def writing_metric(example, pred, trace=None):
            """区分文学比喻 vs AI模板比喻（基于2025多项中文AI写作研究文档化发现）"""
            score = 0.0
            text = pred.output

            # ── 比喻检测 ──
            # 基于 2025 Antislop + 知乎/豆瓣/CSDN 多源整理的 LLM 高频喻体
            # 特征: 通用感官名词→装饰性比喻（"说不清楚也要用"，不是"说不清楚才用"）
            AI_SLOP_NOUNS = [
                "砂纸","刀割","针刺","电流","涟漪","扁舟","风箱","重锤",
                "石子","藤蔓","小兽","潮水","漩涡","深渊","绳索","牢笼",
                "巨石","闪电","火焰","寒冰","利刃","铁钳","熔炉"
            ]

            simile_words = ["像", "仿佛", "如同", "犹如", "宛如"]
            for s in simile_words:
                if s in text:
                    idx = text.index(s)
                    context = text[max(0,idx-8):idx+30]
                    sentences = [x.strip() for x in text.split("。") if s in x]
                    ctx_len = len(sentences[0]) if sentences else 0

                    # 规则1: 喻体命中 AI 文档化高频列表 → AI模板, 重罚
                    if any(w in context for w in AI_SLOP_NOUNS):
                        score -= 0.8
                    # 规则2: 长句(>40字)中的比喻 → 更可能是解释性, 不罚
                    elif ctx_len > 40:
                        pass
                    # 规则3: 短句+比喻 → 可疑, 轻罚
                    elif ctx_len < 25:
                        score -= 0.4
                    else:
                        score -= 0.2

            # ── AI 词汇 ──
            # 基于 2025 研究: Lubrano 论文量化 + 中文社区标注
            # 硬禁词: LLM 显著过度使用 (≥3x 人类基准), 重罚
            HARD_AI = ["不禁","顿时","忽然","心头","嘴角","一股","前所未有","不可名状"]
            # 软禁词: 文学中也用, 但 AI 更频繁 (~1.5x), 轻罚
            SOFT_AI = ["缓缓","微微","轻轻","悄然","静静"]
            for w in HARD_AI:
                if w in text: score -= 0.5
            for w in SOFT_AI:
                if w in text: score -= 0.15

            # ── 奖励 ──
            if len(text) > 80: score += 1.0
            if len(text) > 150: score += 0.5
            sent = [x.strip() for x in text.replace("！","。").replace("？","。").split("。") if len(x.strip())>3]
            if len(sent) >= 3:
                avg = sum(len(x) for x in sent) / len(sent)
                if 8 < avg < 50: score += 1.0

            return max(0.0, score + 1.0)

        # 构建模块
        module = dspy.ChainOfThought(WriterPrompt)

        # 优化
        print(f"  训练数据: {len(trainset)} 条, 迭代: {iterations}")
        t0 = time.time()
        try:
            optimizer = dspy.BootstrapFewShot(
                metric=writing_metric,
                max_bootstrapped_demos=3,
                max_labeled_demos=3,
                max_rounds=iterations,
            )
            optimized = optimizer.compile(module, trainset=trainset)
            elapsed = time.time() - t0
            print(f"  优化完成: {elapsed:.0f}s")

            # 提取优化后的 prompt
            result = {
                "method": "DSPy BootstrapFewShot",
                "iterations": iterations,
                "elapsed_s": round(elapsed, 1),
                "train_examples": len(trainset),
                "signature": str(WriterPrompt),
                "demos": [
                    {"input": d.scene, "output": d.output}
                    for d in optimized.demos
                ] if hasattr(optimized, 'demos') else [],
            }
            return result

        except Exception as e:
            print(f"  [⚠️] 优化失败: {e}")
            return {"error": str(e)}

    def optimize_with_metric(self, task_name: str, trainset: list,
                              metric_fn, iterations: int = 5) -> dict:
        """
        通用优化接口: 自定义 Signature 和评分函数
        """
        self._configure()
        sig = dspy.Signature(
            {"input": dspy.InputField(), "output": dspy.OutputField()},
            f"优化 {task_name} 任务"
        )
        module = dspy.Predict(sig)

        t0 = time.time()
        optimizer = dspy.BootstrapFewShot(
            metric=metric_fn,
            max_bootstrapped_demos=3,
            max_labeled_demos=3,
            max_rounds=iterations,
        )
        optimized = optimizer.compile(module, trainset=trainset)
        elapsed = time.time() - t0

        return {
            "method": "DSPy BootstrapFewShot",
            "task": task_name,
            "iterations": iterations,
            "elapsed_s": round(elapsed, 1),
            "demos": [
                {"input": d.input, "output": d.output}
                for d in optimized.demos
            ] if hasattr(optimized, 'demos') else [],
        }


def quick_test():
    """快速验证 DSPy 连接本地模型"""
    opt = PromptOptimizer()
    opt._configure()

    # 简单生成测试
    result = dspy.Predict("input -> output")(
        input="写一句描写夜晚场景的话"
    )
    print(f"\n  测试输出: {result.output[:200]}")
    print("  ✅ DSPy 连接正常")
    return True


if __name__ == "__main__":
    quick_test()
