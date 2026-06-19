# Novel-Claude Fusion — AI 小说写作系统

底盘: Novel-Claude V3 (微内核+插件架构)
缝合来源: Novel-OS / StoryForge / WenShape / Mo-Shen / AI-Novel-Assistant

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
