# Novel-Claude Fusion — AI 小说写作系统

底盘: Novel-Claude V3 (微内核+插件架构)
缝合来源: Novel-OS / StoryForge / WenShape / Mo-Shen / AI-Novel-Assistant

## 🔴 核心设计法则 — 对所有改动生效

**法则 1：最少规则 > 详细指令**
27B 级别本地模型对过长的写作指令会过拟合。不要在 system prompt 里教模型怎么写 ——
它会机械地执行每一条到最后。正确的做法：文风参照锚定 + 最少规则(<=5条) + 禁用词表。
四轮 A/B 实测验证：最少规则的 V4 在句长变化、禁用词避碰、感官细节三项指标上全部最优。

**法则 2：风格靠参照，不靠指令**
POLARIS 2026 论文验证：人类文本锚定是提升 AI 小说质量的最有效技术。
告诉模型 "不要怎么写" 远不如给它看 "好文章长什么样"。`style_reference.py` 中的真人段落
是项目最核心的资产之一，所有新增题材必须配套文风参照段落。

**法则 3：改动前必须联网查真实来源**
网文写作技巧必须来自：万订作者访谈、起点编辑公开言论、读者社区（龙空/NGA/知乎）共识。
不允许凭感觉编造写作规则。每次修改 prompt 文件前，先搜索对应主题的真实讨论。

**法则 4：改动后必须实测**
任何 prompt/system prompt 的修改必须用本地模型跑至少一次完整生成，记录句长变化、
禁用词命中、感官细节密度三项指标。不通过实测的改动不准提交。

**法则 5：死代码 = 直接删除**
git 历史就是存档。不归档、不标记 deprecated、不保留 "以备后用"。
每个保留的文件必须在代码中有明确的引用链。

## 快速开始

```bash
cd C:\Users\abee\ai-novel-frameworks\Novel-Claude
python cli.py --interactive
```

## 架构

```
core/                  ← 微内核
  ├── novel_context.py ← 运行时状态 + shared_state
  ├── event_bus.py     ← 单例事件总线（emit/emit_pipeline/collect）
  ├── plugin_manager.py← 扫描/加载/热重载 skills/
  ├── base_skill.py    ← Skill 基类（6个生命周期钩子）
  ├── story_state.py   ← [NEW] StoryState 统一数据模型
  └── continuity_engine.py ← [NEW] 9项零token确定性检查

skills/                ← 13个插件（1个已有 + 12个新增）
  ├── det_continuity_engine/  ← 9项连续性检查（零token）
  ├── det_story_state_crud/   ← StoryState 持久化
  ├── gen_genre_tags/         ← 29种流派标签
  ├── gen_writing_style/      ← 20种写作风格
  ├── gen_deai_engine/        ← 去AI味检测
  ├── mem_fact_summary/       ← BM25+距离衰减事实摘要
  ├── mem_working_memory/     ← 三层记忆（L1/L2/L3）
  ├── mem_card_system/        ← 人物/世界观/文风卡片
  ├── wf_mo_shen_workflow/    ← 三档工作流（quick/standard/deep）
  ├── wf_auto_director/       ← AI自动导演全链路
  └── wf_writing_formula/     ← 写法提取与复用

utils/
  └── llm_client.py           ← [REWRITTEN] 多provider LLM客户端
```

## 配置 (config.json)

```json
{
  "llm": {
    "provider": "lmstudio",
    "model": "qwen3-coder-30b-a3b-instruct",
    "base_url": "http://localhost:1234/v1",
    "api_key": "lm-studio-no-auth-needed"
  },
  "workflow": {"mode": "quick"},
  "genre": "玄幻"
}
```

## 常用命令

```bash
# 交互模式
python cli.py --interactive

# 连续性检查
python cli.py continuity --chapter 5

# 热重载插件
python cli.py skills reload det_continuity_engine

# 切换工作流模式（修改 config.json workflow.mode）
```
