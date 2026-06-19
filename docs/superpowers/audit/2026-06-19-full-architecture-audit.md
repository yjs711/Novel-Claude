# Novel-Claude V3 全量架构审计报告

> 日期: 2026-06-19 | 审计范围: 全部 60+ 源文件, 17 个 Skill, 5 个子系统
> 方法: 本地全量代码阅读 + 联网竞品对比 (webnovel-writer v6.2, Novel-OS, InkOS, Autonovel)
> 审计标准: 2025-2026 AI 小说生成最佳实践

---

## 总览评分

| 子系统 | 得分 | 等级 |
|--------|------|------|
| 核心引擎 (WorldBuilder + VolumePlanner + SceneWriter) | 7.0/10 | B+ |
| 微内核 (EventBus + PluginManager + BaseSkill) | 8.0/10 | A- |
| 数据模型 (StoryState + ContinuityEngine) | 7.5/10 | B+ |
| 智能体 (EditorAgent + SkillBuilderAgent) | 5.0/10 | C |
| CLI + 项目管理 | 5.5/10 | C+ |
| LLM 客户端 | 8.0/10 | A- |
| Web UI | 6.5/10 | B |
| 插件生态 (17 Skills) | 7.0/10 | B+ |
| 记忆系统 (Working + Sedimentation + RAG) | 7.5/10 | B+ |
| **综合** | **7.0/10** | **B+** |

---

## 一、核心引擎

### 1.1 WorldBuilder (`world_builder.py`)

**优点：**
- Snowflake 方法四步展开（金手指→一句话→大纲→世界观→核心蓝图），流程清晰
- Pydantic schema 强类型校验每次 LLM 输出
- `render_to_markdown()` 生成人类可读手册是好设计

**缺点：**
- ❌ Prompt 硬编码在 `PROMPT_TEMPLATES` dict 中，不在外部 prompt 文件 — 调 prompt 必须改源码
- ❌ `CharacterCardSchema.born_scene` 拼写错误
- ❌ 无断点续传 — LLM 调用失败整个流程重来
- ❌ 缺少与竞品 `webnovel-writer` 种子初始化的对标：没有合同种子机制，核心设定不会被写为"不可违背的宪法"

**改进建议：**
1. Prompt 外置到 `prompts/` 目录，支持热加载
2. 新增 `MASTER_SETTING.json` 合同种子（对标 webnovel-writer）
3. 中间步骤自动保存 checkpoint，支持断点续传
4. 修复拼写错误

---

### 1.2 VolumePlanner (`volume_planner.py`)

**优点：**
- Pydantic schema 覆盖卷→阶段→章三级结构
- 章节字数归一化（~5000字/章）
- 六阶段结构（开篇→发展→转折→高潮→收束→过渡）符合网文节奏

**缺点：**
- ❌ 章节数估算 90-108 范围太宽（prompt 说 ~100 但实际偏差大）
- ❌ `get_world_context()` 读取的旧文件名（`world_rules.json`, `power_levels.json`）可能不存在
- ❌ `event_bus_emit_pipeline()` 使用 lazy import inside function — 循环依赖信号
- ❌ 不验证跨卷章节重叠

**改进建议：**
1. 分卷规划后回写 StoryState，标记每卷的章节范围——为后续一致性检查提供锚点
2. 统一 `get_world_context()` 到 `core/story_state.py`
3. 清理循环依赖

---

### 1.3 SceneWriter (`scene_writer.py`)

**优点：**
- `build_chapter_prompt()` 组装丰富上下文：章纲、人物卡、世界观、前章尾巴、历史章节、下章预告、伏笔、写作约束
- 五钩子生命周期完整：`before_scene_write → after_scene_write → post_chapter_continuity → chapter_render → after_chapter_complete`
- 状态机驱动（skip/existing/resume/drafting/generating/completed/failed）
- ProgressiveWriter 流式输出 + 进度回调

**缺点：**
- ❌ `_load_structured_outline_chapter()` 调用不存在的 `_load_config()` — **代码 bug**
- ❌ `deep_review_chapter()` 只取前 3000 字符 — 大量内容未审查
- ❌ Batch API 硬编码 `model: "glm-4"`
- ❌ 与 WebUI 的 `/api/write-stream` 是两条完全独立的代码路径 — 无共享状态
- ❌ EditorAgent 定义了但 `run_scene_writer` 从未调用 — 死代码

**改进建议：**
1. 🐛 **立即修复** `_load_config()` 缺失 bug
2. 统一 WebUI 和 CLI 的章节生成路径
3. 激活 EditorAgent 或删除
4. 深度审查改为分段审查而非截断

---

## 二、微内核

### 2.1 EventBus (`core/event_bus.py`)

**优点：**
- 三种分发模式涵盖所有场景：`emit`（广播）、`emit_pipeline`（串行管道）、`collect`（收集）
- 单插件崩溃隔离 — 这是微内核架构的核心价值
- 单例模式确保全局唯一

**缺点：**
- ❌ 所有订阅者收到所有事件 — 无事件过滤
- ❌ 同步执行 — 长时间运行的提取/审查钩子阻塞主流程
- ❌ print() 错误日志 — 无结构化日志

**改进建议：**
1. 新增 `event_types` 注册，订阅者声明关注的事件类型
2. 异步 emit 可选 — 非关键钩子（沉淀/统计）异步执行
3. 结构化 logging 替代 print

---

### 2.2 PluginManager (`core/plugin_manager.py`)

**优点：**
- 动态扫描 + importlib 热加载 — 放入即生效
- `.disabled` 标记文件开关 — 简洁实用
- 热重载保留上下文

**缺点：**
- ❌ 无插件依赖排序 — 加载顺序依赖文件系统
- ❌ 生成的代码（SkillBuilderAgent）无沙箱直接热加载
- ❌ `_load_skill()` 静默吞掉所有异常

**改进建议：**
1. 插件声明 `depends_on` 字段，PluginManager 做拓扑排序加载
2. 生成的代码先 syntax check + 基础静态分析再加载
3. 加载失败时输出完整 traceback（当前只有一行 print）

---

### 2.3 BaseSkill (`core/base_skill.py`)

**优点：**
- 七大生命周期钩子覆盖完整写作流程
- Tool Calling 接口预留扩展点
- 设计简洁，上手门槛低

**缺点：**
- ❌ `get_llm_tools()` / `execute_tool()` 定义但没有任何 Agent 框架实际调用 — **功能空洞**
- ❌ `on_volume_planning()` 签名与 `emit_pipeline` 的串行管道语义不一致

**改进建议：**
1. 在 SceneWriter 或新建 Orchestrator 中实现 tool-calling loop
2. 统一 pipeline 钩子签名

---

## 三、数据模型

### 3.1 StoryState (`core/story_state.py`)

**优点：**
- 5 个核心数据类覆盖角色/剧情/章节/风格/时间线
- 原子写入 + `.bak` 回滚
- 分片存储（70章/卷）支撑 500万字 → 对标竞品的持久化方案
- `from_dict()` 防御性忽略未知字段

**缺点：**
- ❌ 无版本迁移 — `Character` 字段变更后旧 JSON 静默丢数据
- ❌ `Character.last_appearance_chapter = 0` 语义模糊（0 表示"未登场"还是"第0章"？）
- ❌ `CHAPTERS_PER_VOLUME = 70` 硬编码

**改进建议：**
1. 新增 `version` 字段 + 迁移函数
2. 显式 `None` 表示"未登场"替代 0 的歧义
3. 分片大小可配置

---

### 3.2 ContinuityEngine (`core/continuity_engine.py`)

**优点：**
- 7项零 token 确定性检查 — 对标 Novel-OS 的设计
- 严重/警告/提示三级分类
- 中文本地化输出

**缺点：**
- ❌ `_file_cache` 全局永不过期 — 内存泄漏风险
- ❌ `check_dead_characters_reappearing()` 关键词匹配太粗糙（检查 `emotional_state` + `notes` 中的"死"字）
- ❌ 调谐常量硬编码（`DORMANT_THREAD_GAP_CHAPTERS = 3`）

**改进建议：**
1. 缓存加 TTL 或手动失效
2. 死亡检测改为显式 `Character.status` 字段（`alive`/`dead`/`unknown`）
3. 调谐常量移到 config.json

---

## 四、智能体

### 4.1 EditorAgent (`core/agents/editor_agent.py`)

**优点：**
- ReAct 多轮审稿设计正确
- `submit_final_revision` 工具 + critique 输出

**缺点：**
- 🔴 **未被任何生产路径调用** — `run_scene_writer` 不调它，WebUI 也不调
- system_prompt 默认值写在代码中

**改进建议：**
1. 激活集成到 SceneWriter 或删除
2. 对标 InkOS Auditor — 扩展审查维度到 10+

---

### 4.2 SkillBuilderAgent (`core/agents/skill_builder_agent.py`)

**优点：**
- 元生成概念极有创新性 — 竞品均无此功能

**缺点：**
- 🔴 **无沙箱** — 生成的 Python 代码直接 `importlib` 加载，安全风险
- 引用的 `reference/Skill与Agent开发模板规范.md` 不存在
- 生成代码无验证

**改进建议：**
1. 生成代码先 `py_compile` + AST 扫描再加载
2. 限制生成代码的 import（白名单）
3. 写模板规范文档

---

## 五、CLI + 项目管理

**优点：**
- 20+ 命令覆盖全局
- prompt_toolkit REPL + tab 补全
- 多项目管理（project_manager）

**缺点：**
- ❌ 每个 REPL 命令创建新的 NovelContext/PluginManager — 无会话共享状态
- ❌ Subprocess dispatch 脆弱（REPL 内执行 Click 命令 spawn 新 Python 进程）
- ❌ `settings set` 写入 `env` 文件而非 `config.json` — 两套配置系统

**改进建议：**
1. REPL session 共享单一 NovelContext 实例
2. 命令内联执行而非 subprocess
3. 统一配置到 config.json，废弃 env 文件

---

## 六、LLM 客户端 (`utils/llm_client.py`)

**优点：**
- 10 个 provider 抽象层 — 对标竞品最佳实践 ✅
- 多模型池（default + flash + alt_models）+ 任务路由
- ProgressiveWriter 流式输出 + Rich Live 渲染
- 上下文截断策略（中间截断保留首尾）
- 采样参数按任务类型分离

**缺点：**
- ❌ `generate_json()` 重试时 prompt 无限增长（追加前次错误）
- ❌ `ProgressiveWriter` 依赖 Rich Live → 非 TTY 环境崩溃
- ❌ `extract_entities()` JSON 解析失败后的逗号分割 fallback 极其脆弱

**改进建议：**
1. 重试时固定 prompt 大小
2. ProgressiveWriter 检测 TTY 降级到纯文本
3. 移除脆弱的 fallback 解析

---

## 七、Web UI (`webui/app.py`)

**优点：**
- FastAPI + SSE 流式生成
- 25+ REST 端点覆盖全部功能
- 多 Agent 路径（quick/standard/deep）

**缺点：**
- ❌ 无认证/速率限制
- ❌ 同步引擎代码在 async 端点中阻塞
- ❌ 两条独立创作路径（直接流式 vs Agent 管线）无共享状态

**改进建议：**
1. 全局状态单例替代 per-request 重建
2. 同步调用用 `run_in_executor` 包装
3. 添加基本认证

---

## 八、插件生态（17 Skills）

### 8.1 审计总览

| Skill | 质量 | 状态 |
|-------|------|------|
| `mem_working_memory` | A- | ✅ 完整 |
| `mem_sedimentation` | A- | ✅ 新建 |
| `mem_fact_summary` | B+ | ✅ 完整 |
| `det_continuity_engine` | B+ | ✅ 完整 |
| `gen_deai_engine` | B | ✅ 完整 |
| `wf_mo_shen_workflow` | B | ⚠️ 5 Agent 串行开销大 |
| `gen_genre_tags` | B+ | ✅ 29 流派完整 |
| `gen_writing_style` | B+ | ✅ 20 风格完整 |
| `core_memory_rag` | B- | ⚠️ ChromaDB 依赖+性能问题 |
| `mem_card_system` | B | ✅ 完整 |
| `det_story_state_crud` | B- | ⚠️ 密钥不匹配 bug |
| `wf_auto_director` | B | ✅ 完整 |
| `wf_writing_formula` | B- | ✅ 基础功能 |
| `ext_gold_finger` | C+ | ✅ 演示级 |
| `ext_handsome_protagonist` | D | 📌 演示 Skill |
| `ext_world_highlight` | C+ | ✅ 演示级 |
| `mem_card_system` | B | ✅ 完整 |

### 8.2 关键问题

**🔴 P0 — Tool Calling 空洞**
`get_llm_tools()` / `execute_tool()` 在多个 Skill 中实现（gold_finger, handsome_protagonist, world_highlight），但没有一个 Agent 框架来驱动 tool-calling loop。LLM 返回的 tool_call 不会路由到 Skill 执行。

**🔴 P0 — det_story_state_crud 密钥不匹配**
`_sync_from_settings()` 读 `blueprint.get("characters", [])`，实际 key 是 `character_cards`。

**🔴 P1 — core_memory_rag 性能**
- ZhipuEmbeddingFunction 逐个文本调 API（无批处理）
- sentence-transformers 420MB CPU 模型
- `_condense_state()` 每个 entity 调一次完整 LLM

**🔴 P1 — 代码生成无沙箱**
SkillBuilderAgent 生成的代码直接热加载。

### 8.3 竞品差距

| 能力 | Novel-Claude | webnovel-writer | InkOS |
|------|-------------|-----------------|-------|
| Token 审计（零成本检查） | ✅ 7项 | ❌ 无独立模块 | ✅ 33项 |
| 多 Agent 审查管线 | ⚠️ 5 Agent 串行 | ✅ Blocking Review | ✅ 11 Agent 审查 |
| 长期记忆闭环 | ✅ (刚补全) | ✅ 5路投影 | ✅ 7 files |
| 追读力系统 | ❌ | ✅ | ⚠️ 基础 |
| 合同/Story System | ❌ | ✅ v6.0 | ❌ |
| Tool Calling | ❌ 空洞 | ✅ 集成 | ✅ 集成 |
| 质量门控 | ❌ | ✅ 阻断 | ✅ 多级 |
| **去AI味** | ✅ 8维 | ⚠️ 基础 | ✅ 4维 |
| **Skill Builder** | ✅ 独有 | ❌ | ❌ |
| **Web UI** | ✅ FastAPI | ⚠️ 只读Dash | ✅ Studio 2.0 |

---

## 九、优先改进路线图

### 🔴 P0 — 立即修复

1. **SceneWriter `_load_config()` bug** — 文件级崩溃风险
2. **det_story_state_crud 密钥不匹配** — 数据静默丢失
3. **Tool Calling 空洞** — 多个 Skill 的交互功能不可用
4. **SkillBuilder 沙箱** — 安全风险

### 🟡 P1 — 本月内

5. **统一双生成路径**（CLI vs WebUI）
6. **两套配置统一**（config.json vs env）
7. **RAG 性能优化**（批处理 + 去 LLM 冷凝）
8. **追读力系统** — 对标 webnovel-writer v5.3
9. **合同种子机制** — 对标 webnovel-writer v6.0 Story System

### 🟢 P2 — 下季度

10. **质量门控** — 对标 InkOS 阻断机制
11. **插件依赖排序**
12. **CLI REPL 会话状态共享**
13. **config.json 版本迁移**
14. **Web UI 认证**

---

## 十、竞品定位总结

```
                    社区规模 →
            小                    大
架构  高  ┌ Novel-Claude ─── ─── webnovel-writer
先进   │  │ (6★, 微内核+插件)   (4.9k★, 合同系统)
度     │  │
      │  ┌ Novel-OS ─── ─── ─── InkOS
      │  │ (学术级, 5 Agent)    (生产级, 11 Agent)
     低  └ ─── ─── ─── ─── ─── Sudowrite (闭源)
```

**Novel-Claude 的独特优势（别人抄不走的）：**
1. **Skill Builder 元生成** — 全网唯一 AI 写插件的系统
2. **微内核 + 事件总线** — 扩展性天花板最高
3. **Web UI + CLI 双界面** — 用户体验最好
4. **本地模型优化** — 128G 统一内存架构的独特硬件优势

**核心短板（需要追的）：**
1. Story System / 合同机制（webnovel-writer 已领跑）
2. 质量门控 + 阻断（InkOS 已实现）
3. 追读力/读者留存分析（webnovel-writer v5.3）
4. 社区建设（6 stars vs 4900）

---

## Sources

- [webnovel-writer GitHub](https://github.com/lingfengQAQ/webnovel-writer)
- [Novel-OS GitHub](https://github.com/mrigankad/Novel-OS)
- [InkOS GitHub](https://github.com/visense/inkos)
- [Autonovel GitHub](https://github.com/NousResearch/autonovel)
- [Novel-Claude GitHub](https://github.com/wzxsph/Novel-Claude)
- [Novel Creator Skill](https://github.com/leenbj/novel-creator-skill)
- [SCORE: Story Coherence and Retrieval Enhancement](https://ar5iv.labs.arxiv.org/html/2503.23512v1)
- [Dev.to Best AI Tools for Fiction 2026](https://dev.to/nitinfab/the-best-ai-tools-for-writing-fiction-in-2026-2l72)
- [Duple 2026 AI Writing Tools](https://dupple.com/learn/best-ai-for-writing-books)
- [HackerNoon Claude Book](https://hackernoon.com/claude-book-a-multi-agent-framework-for-writing-novels-with-claude-code)
- [FictionRAG (Algorithms 2026)](https://www.mdpi.com)
- [E²RAG (ACL 2026)](https://aclanthology.org)
- [Neo4j Graph-Powered Storyworlds (NODES AI 2026)](https://neo4j.com/videos/nodes-ai-2026-graph-powered-storyworlds-using-neo4j-to-keep-1m-word-litrpg-epics-coherent-w-ai/)
- [Dramatica Blog: A Pipeline Is Not a Storyform](https://dramatica.com/blog/a-pipeline-is-not-a-storyform)
- [Dev.to ReAct Pattern Review](https://dev.to/seahjs/react-pattern-review-3cki)
