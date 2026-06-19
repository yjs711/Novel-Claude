---
name: Novel-Claude
description: 本地 AI 小说写作工作站 — 全息霓虹科幻创作终端
colors:
  void-deep: "#080a10"
  void-surface: "#0d1117"
  void-elevated: "#141a24"
  void-border: "#1c2541"
  ink-primary: "#e8edf5"
  ink-secondary: "#8090b0"
  ink-tertiary: "#4a5578"
  neon-cyan: "#00c8ff"
  neon-cyan-glow: "#00c8ff66"
  neon-violet: "#a855f7"
  neon-violet-glow: "#a855f766"
  neon-mint: "#00e5a0"
  neon-amber: "#f59e0b"
  neon-rose: "#f43f5e"
typography:
  display:
    fontFamily: "'Space Grotesk', 'Inter', system-ui, sans-serif"
    fontSize: "clamp(1.5rem, 5vw, 2.5rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "'Space Grotesk', 'Inter', system-ui, sans-serif"
    fontSize: "clamp(1.125rem, 3vw, 1.5rem)"
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  title:
    fontFamily: "'Inter', 'SF Pro Display', system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  body:
    fontFamily: "'Inter', 'SF Pro Display', system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "0.005em"
  label:
    fontFamily: "'Inter', 'SF Pro Display', system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.06em"
  mono:
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
rounded:
  none: "0"
  sm: "2px"
  md: "4px"
  lg: "8px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  "2xl": "48px"
components:
  button-primary:
    backgroundColor: "{colors.neon-cyan}"
    textColor: "{colors.void-deep}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "8px 20px"
  button-primary-hover:
    backgroundColor: "{colors.neon-cyan-glow}"
  button-secondary:
    backgroundColor: "{colors.void-elevated}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-tertiary}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  input:
    backgroundColor: "{colors.void-surface}"
    textColor: "{colors.ink-primary}"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  panel:
    backgroundColor: "{colors.void-surface}"
    rounded: "{rounded.md}"
---

# Design System: Novel-Claude

## 1. Overview

**Creative North Star: "The Holographic Terminal"**

Novel-Claude 的界面是一个悬浮在虚空中全息投影创作终端。暗色基底几乎消失，霓虹元素像全息光纹一样漂浮在表面之上。它不是"深色模式"——它是"虚空模式"：界面退到背景中，文字和操作元素像被投射到空间中一样浮现。

这个系统明确拒绝 Google Material Design 的圆角大卡片、Bento 网格、蓝白配色，拒绝苹果极简白的眩光，拒绝传统网文写作软件的界面堆砌。它是一件为长时间深度写作设计的光学仪器，每束霓虹光都有其功能含义。

**Key Characteristics:**
- 虚空基底：极深蓝黑（`#080a10`）作为背景，几乎感知不到"界面"的存在
- 霓虹功能指示：青=主要操作，紫=强调/选中，绿=成功/通过，琥珀=警告，玫红=危险
- 全息层次：面板通过微妙边框光晕和表面抬升区分，而非厚重阴影
- 全无衬线：抛弃文学衬线体，拥抱科技感几何无衬线，作者感觉在使用精密仪器
- 玻璃质面板：半透明深色面板带 1px 冷色边框，悬浮感而非卡片感

## 2. Colors: The Neon Void Palette

暗色基底从近纯黑到深蓝灰，形成三级抬升。霓虹色系全谱覆盖功能指示，每种霓虹色都有对应的发光变体用于 hover/focus/glow。

### Primary
- **霓虹青 Neon Cyan** (`#00c8ff`): 主操作色。按钮、链接、焦点环、选中态指示器。唯一有权大面使用的霓虹色。hover 时转为发光态 (`#00c8ff66`)。

### Secondary
- **霓虹紫 Neon Violet** (`#a855f7`): 强调/高亮。用于大纲节点高亮、伏笔标记、灵感工坊模块标题、对话气泡 AI 侧。

### Tertiary
- **霓虹薄荷 Neon Mint** (`#00e5a0`): 成功/完成。门控通过、伏笔回收、章节完成状态。
- **霓虹琥珀 Neon Amber** (`#f59e0b`): 警告/注意。门控警告、未回收伏笔、冲突级别偏低。
- **霓虹玫红 Neon Rose** (`#f43f5e`): 危险/错误。门控失败、巧合场景过多、爽点密度过低。

### Neutral
- **虚空深 Void Deep** (`#080a10`): 页面背景。最暗层，几乎纯黑带微蓝底调。
- **虚空面板 Void Surface** (`#0d1117`): 面板/卡片/输入框背景。第一级抬升。
- **虚空抬升 Void Elevated** (`#141a24`): 悬浮元素/模态/dropdown。第二级抬升。
- **虚空边框 Void Border** (`#1c2541`): 1px 分割线和边框。带蓝调，避免死黑边框。
- **墨水主 Ink Primary** (`#e8edf5`): 正文。冷白，在虚空深底上 ≥11:1 对比度。
- **墨水次 Ink Secondary** (`#8090b0`): 辅助文字/标签。WCAG AA 正文 ≥4.5:1。
- **墨水弱 Ink Tertiary** (`#4a5578`): 占位符/禁用态/装饰。不用于功能性文字。

### Named Rules
**The One-Neon Rule.** 任何给定屏幕上，霓虹色总面积 ≤10%。霓虹青作为主操作色占比最高，紫色次之，其他霓虹色仅出现在状态指示中。稀有即力量。

**The No-Gray Rule.** 不使用中性灰（`#808080` 系）。所有"灰色"必须是蓝调的虚空色（`void-*`），与霓虹色产生冷暖对比。

**The Glow Reserve Rule.** 发光态（`*-glow`）仅用于 hover/focus/active 交互反馈。静态元素不使用 box-shadow glow。界面在静止时保持冷静，交互时才展现霓虹生命力。

## 3. Typography: The Precision Instrument

**Display/Heading Font:** Space Grotesk → Inter → system-ui sans-serif
**Body Font:** Inter → SF Pro Display → system-ui sans-serif
**Mono Font:** JetBrains Mono → Fira Code → monospace

**Character:** 全无衬线栈。Space Grotesk 的几何骨架为标题带来精密仪器感，Inter 为正文提供最佳可读性。抛弃了旧主题的衬线文学感，拥抱"创作终端"的科技气质。编辑区正文使用 Inter（非等宽），保持长文阅读舒适；代码/数据显示使用 JetBrains Mono。

### Hierarchy
- **Display** (600, `clamp(1.5rem, 5vw, 2.5rem)`, 1.15): 向导标题、故事蓝图主标题。仅出现于模态和向导。
- **Headline** (500, `clamp(1.125rem, 3vw, 1.5rem)`, 1.25): 面板标题、章节标题。
- **Title** (600, `1rem`, 1.3): 卡片标题、模块标题、对话角色名。
- **Body** (400, `0.875rem`, 1.6): 正文、编辑器内容、对话内容。最大行宽 75ch。
- **Label** (600, `0.6875rem`, 1.2, `0.06em`): 按钮、标签、面板标题（大写）、徽章、数据标注。
- **Mono** (400, `0.8125rem`, 1.6): 代码块、字数统计、门控分数、JSON 预览、终端输出。

### Named Rules
**The Caps Reserve Rule.** 全大写字母间距（`letter-spacing: 0.06em`）仅用于 Label 层级。正文、标题禁止全大写。

**The Line-Length Rule.** 正文最大行宽 75ch。编辑器内部最大 820px 已在此范围内。对话气泡不受此限。

## 4. Elevation: Holographic Depth

此系统不使用传统 Material 阴影。深度通过**亮度抬升 + 边框发光**表达：在虚空基底上，抬升的表面变得更亮（通过半透明白色叠加），而非更暗。这模拟了全息投影的物理特性——离投影源越近的表面越亮。

边框不纯黑，而是带蓝调的 `void-border`（`#1c2541`），在暗底上产生微妙的分离感，像玻璃边缘的光折射。

### Surface Layering
- **Level 0 (Page BG):** `void-deep` (`#080a10`) — 无边框，无圆角
- **Level 1 (Panel/Card):** `void-surface` (`#0d1117`) — 1px `void-border`，圆角 `md` (4px)
- **Level 2 (Modal/Dropdown):** `void-elevated` (`#141a24`) — 1px `void-border` + 霓虹青微光晕 (`0 0 0 1px #00c8ff22`)，圆角 `lg` (8px)
- **Level 3 (Toast/Notification):** `void-elevated` — 霓虹边框着色（按状态：青/绿/琥珀/玫红）

### Named Rules
**The No-Shadow Rule.** 不使用 `box-shadow` 表达深度。面板间通过 1px 冷色边框 + 亮度差异区分。唯一的例外是：模态层（Level 2）有一个极微弱的霓虹青外发光（`0 0 0 1px #00c8ff22`）表示其悬浮态。

**The Flat-By-Default Rule.** 所有表面在静止时是平的。hover 和 focus 是唯一的抬升触发器，且仅通过颜色/边框变化表达，不改变阴影。

## 5. Components

### Buttons
- **Shape:** 利落矩形，圆角 `sm`（2px）。不圆润——这是一个精密仪器，不是消费 App。
- **Primary:** `neon-cyan` 背景 + `void-deep` 文字（青底黑字）。全息终端的主要交互信号。
- **Hover:** 背景切换为 `neon-cyan-glow`（半透明青），文字保持 `void-deep`。
- **Focus:** `0 0 0 2px void-deep, 0 0 0 3px neon-cyan` 双环焦点，确保在暗底可见。
- **Secondary:** `void-elevated` 背景 + `ink-secondary` 文字 + 1px `void-border`。
- **Ghost:** 透明背景 + `ink-tertiary` 文字。hover 时文字变 `ink-primary`。
- **Danger:** `neon-rose` 背景 + `void-deep` 文字。仅用于不可逆操作。

### Inputs & Fields
- **Style:** 1px `void-border` + `void-surface` 背景 + `ink-primary` 文字。
- **Focus:** 边框变 `neon-cyan`，外发光 `0 0 0 2px #00c8ff33`。
- **Placeholder:** `ink-tertiary`，对比度 ≥4.5:1。
- **Error:** 边框变 `neon-rose` + `0 0 0 2px #f43f5e33`。

### Panels & Cards
- **Corner Style:** 圆角 `md`（4px）。利落，不像 Material 的 `12-16px` 圆角。
- **Background:** `void-surface`（`#0d1117`）。
- **Border:** 1px `void-border`。不可省略——无边框的暗色面板会与背景融为一体。
- **Internal Padding:** `md`（16px）标准，`lg`（24px）用于编辑器区域。
- **Nested panels:** 禁止。面板内不放面板。

### Navigation & Tabs
- **Tab Bar:** 底部分割线 1px `void-border`。
- **Active Tab:** 底部 2px `neon-cyan` 下划线 + `ink-primary` 文字。
- **Inactive Tab:** `ink-secondary` 文字，无下划线。
- **Hover:** `ink-primary` 文字。

### Chips / Badges
- **Style:** 圆角 `full`（胶囊），`void-elevated` 背景 + 1px `void-border`。
- **Status variants:** 通过=薄荷边框+文字，警告=琥珀边框+文字，错误=玫红边框+文字。
- **Size:** 内边距 `2px 8px`，字号 Label（`0.6875rem`）。

### Scrollbar
- **Track:** 透明。
- **Thumb:** `ink-tertiary`（`#4a5578`），宽 4px，圆角 2px。
- **Hover:** `ink-secondary`（`#8090b0`）。

### Editor Textarea
- **Background:** `void-surface`。
- **Text:** `ink-primary`，字号 `1rem`（编辑器）或 `0.875rem`（细纲）。
- **Font:** Inter（全无衬线，精密仪器感）。
- **Border:** 1px `void-border`，focus 时变 `neon-cyan` + 青发光。
- **Line-height:** 2.0 保持舒适的写作行距。
- **Max-width:** 820px，居中。

### Focus Ring (Global)
所有可聚焦元素的 `:focus-visible` 样式：
- `outline: none`（移除浏览器默认）
- `box-shadow: 0 0 0 2px var(--void-deep), 0 0 0 3px var(--neon-cyan)`
- 双环确保在暗底和亮元素上都可见

## 6. Do's and Don'ts

### Do:
- **Do** 用 `void-border`（`#1c2541`）做所有分割线和边框——带蓝调的深色，拒绝死黑
- **Do** 只用霓虹青做主要操作色——其他霓虹色仅用于状态指示
- **Do** 保持面板 1px 边框——暗色基底上无边框等于消失
- **Do** 用 `ink-tertiary`（`#4a5578`）做占位符和装饰文字，对比度仍 ≥4.5:1
- **Do** 所有交互元素有 `:focus-visible` 双环，确保键盘导航可达
- **Do** 动效尊重 `prefers-reduced-motion`，降级为即时过渡或淡入淡出
- **Do** 正文行宽 ≤75ch，编辑器最大 820px
- **Do** 色彩对比度在提交前自检：正文≥4.5:1，大文本≥3:1

### Don't:
- **Don't** 使用 Google Material Design 3 的任何特征：蓝白配色、12-16px 圆角、Bento 网格、大卡片嵌套
- **Don't** 使用纯黑（`#000000`）或纯白（`#FFFFFF`）——虚空色系和冷白墨水才是规范
- **Don't** 使用中性灰（`#808080`、`#999999` 系）——所有灰色替换为蓝调虚空色
- **Don't** 使用 `box-shadow` 表达深度——用亮度抬升 + 1px 边框 + 微光晕
- **Don't** 在面板内嵌套面板——用分割线或间距区分内容
- **Don't** 同时使用超过 2 种霓虹色——青+紫是上限
- **Don't** 在静态元素上使用发光态（`*-glow`）——glow 仅用于 hover/focus/active
- **Don't** 使用 serif 衬线字体——全系统无衬线
- **Don't** 圆角超过 8px——`rounded` 最大是 `lg`（8px），利落矩形优于圆润
- **Don't** 使用 Apple HIG 极简白（纯白背景、大留白）——白色眩光导致眼疲劳
