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
            """评分: 避免比喻+AI词汇，奖励长度和多样性"""
            score = 0.0
            text = pred.output
            # 惩罚比喻
            similes = ["像", "仿佛", "如同", "犹如", "宛如"]
            for s in similes:
                if s in text:
                    score -= 0.5
            # 惩罚AI词
            ai_words = ["不禁", "缓缓", "微微", "顿时", "忽然", "心头", "嘴角"]
            for w in ai_words:
                if w in text:
                    score -= 0.3
            # 奖励长度
            if len(text) > 100:
                score += 1.0
            if len(text) > 200:
                score += 0.5
            # 奖励句子多样性
            sentences = [s.strip() for s in text.replace("！", "。").replace("？", "。").split("。") if s.strip()]
            if len(sentences) > 5:
                avg_len = sum(len(s) for s in sentences) / len(sentences)
                if 5 < avg_len < 40:
                    score += 1.0
            return max(0.0, score + 3.0)  # 基线 3 分

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
