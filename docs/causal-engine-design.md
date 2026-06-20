# 因果图 + 角色行为引擎 设计方案

> 基于 2025-2026 顶会论文、GOAP 游戏 AI、PlotPilot 开源项目
> 设计目标：让 Novel-Claude 从"响应式写作"升级为"世界推演引擎"

---

## 一、核心设计理念

### 分离关注点（GEST 论文，2026）
```
LLM 的职责：创意决策（"这个角色会做什么？"）
后端的职责：一致性约束（"这件事在这个时间点可能发生吗？"）
```

### 双图架构（E²RAG 论文，2025）
```
事件图（Event Graph）：节点=事件，边=因果关系+时间关系
角色图（Character Graph）：节点=角色，边=关系+目标+状态
```

### 两层决策（Kingdom Come II 架构，2025）
```
上层：Utility AI — 选目标（"我想复仇"）
下层：GOAP — 规划行动链（"复仇需要：收集情报→接近目标→制造冲突"）
```

---

## 二、数据结构

### 2.1 事件节点（Event Node）
```python
@dataclass
class EventNode:
    id: str                          # 唯一ID，如 "evt_042"
    chapter: int                     # 发生章节
    type: str                        # 'action' | 'dialogue' | 'revelation' | 'conflict' | 'resolution'
    
    # STAC 四元分类（Beyond LLMs 论文, ACL 2025）
    stac_type: str                   # 'situation' | 'task' | 'action' | 'consequence'
    
    summary: str                     # 一句话概括
    participants: list[str]          # 参与角色ID列表
    location: str                    # 发生地点
    emotional_valence: float         # -1.0 到 +1.0
    
    # 因果边
    causes: list[str]                # 前置事件ID（"因为A所以B"）
    effects: list[str]               # 后置事件ID（"A导致了C"）
    confidence: float                # 因果确信度 0-1
    
    # 伏笔追踪
    is_foreshadow_plant: bool        # 埋下伏笔？
    foreshadow_target: str|None      # 回收此伏笔的事件ID
    is_foreshadow_payoff: bool       # 回收伏笔？
```

### 2.2 角色节点（Character Node）
```python
@dataclass  
class CharacterNode:
    id: str                          # 如 "char_001"
    name: str
    
    # GOAP 核心三要素
    goals: list[Goal]                # 当前目标（可多个，按优先级排序）
    state: dict[str, Any]            # 当前状态 {"alive": True, "location": "京城", "reputation": 45}
    
    # 性格参数（驱动 Utility AI 目标选择）
    personality: {
        "ambition": float,           # 野心 0-1
        "loyalty": float,            # 忠诚 0-1  
        "aggression": float,         # 攻击性 0-1
        "cunning": float,            # 狡诈 0-1
        "empathy": float,            # 同理心 0-1
    }
    
    # 关系图
    relationships: dict[str, Relationship]  # 对其他角色的态度
```

### 2.3 目标（Goal）
```python
@dataclass
class Goal:
    id: str
    description: str                 # "复仇：杀死杀害师父的凶手"
    priority: float                  # 当前优先级（动态计算）
    preconditions: list[str]         # 达成前提，如 ["知道凶手身份", "修炼到金丹期"]
    desired_state: dict[str, Any]    # 目标状态
    deadline_chapter: int|None       # 预计需要在几章前达成（产生时间压力）
    status: str                      # 'active' | 'achieved' | 'abandoned'
```

### 2.4 关系（Relationship）
```python
@dataclass
class Relationship:
    target_id: str
    type: str                        # 'ally' | 'enemy' | 'neutral' | 'family' | 'romance'
    intensity: float                 # -1.0(死敌) 到 +1.0(挚爱)
    history: list[str]               # 关键关系转折事件ID列表
    last_updated_chapter: int
```

---

## 三、核心引擎

### 3.1 因果图引擎（CausalGraphEngine）

```python
class CausalGraphEngine:
    """维护事件因果图，提供查询和验证能力"""
    
    def __init__(self):
        self.events: dict[str, EventNode] = {}
        self.event_sequence: list[str] = []  # 章节顺序
    
    def add_event(self, event: EventNode):
        """添加新事件，自动检测因果链"""
        # 1. 查找潜在前置原因（LLM辅助 + 规则验证）
        candidates = self._find_candidates(event)
        # 2. 反事实验证（Beyond LLMs 论文方法）
        for c in candidates:
            if self._counterfactual_test(c, event):
                self._link_events(c.id, event.id)
        # 3. 伏笔自动追踪
        self._check_foreshadowing(event)
    
    def _counterfactual_test(self, cause: EventNode, effect: EventNode) -> bool:
        """如果前提事件没发生，结果事件是否依然合理？"""
        # 使用LLM快速判断 + 规则辅助
        # 论文报告的可靠度 >85%
        pass
    
    def get_causal_chain(self, event_id: str, depth: int = 3) -> list[EventNode]:
        """获取某个事件的因果链（前因+后果）"""
        pass
    
    def get_active_threads(self) -> list[list[EventNode]]:
        """获取当前所有未闭合的因果线程"""
        pass
```

### 3.2 角色行为引擎（CharacterEngine）

```python
class CharacterEngine:
    """基于 GOAP + Utility AI 的角色自主行为推演"""
    
    def __init__(self):
        self.characters: dict[str, CharacterNode] = {}
    
    def tick(self, new_events: list[EventNode]):
        """每写完一章后调用，推演所有角色状态"""
        for char in self.characters.values():
            # 1. Utility AI: 重新评估目标优先级
            self._recalculate_priorities(char)
            # 2. 检测新事件是否触发目标变更
            self._react_to_events(char, new_events)
            # 3. 更新关系图
            self._update_relationships(char, new_events)
    
    def _recalculate_priorities(self, char: CharacterNode):
        """
        基于 Utility AI 原理：
        priority = Σ(性格权重 × 目标紧迫度 × 距离衰减)
        
        性格驱动的目标选择：
        - 野心高 → 追求地位/力量类目标
        - 忠诚高 → 优先保护盟友
        - 攻击性高 → 优先报复/消灭威胁
        - 狡诈高 → 优先隐藏目标，暗中推进
        """
        for goal in char.goals:
            urgency = self._calc_urgency(goal)
            personality_mod = self._personality_match(char, goal)
            goal.priority = urgency * personality_mod
    
    def suggest_next_actions(self, char_id: str, context: dict) -> list[str]:
        """
        GOAP 规划：给定角色+当前世界状态，建议下一步行动
        返回：行动描述列表（喂给写作prompt作为角色动机参考）
        """
        pass
    
    def _react_to_events(self, char: CharacterNode, events: list[EventNode]):
        """事件驱动：角色对世界变化的反应"""
        for event in events:
            if char.id in event.participants:
                # 角色参与的事件：记录
                pass
            else:
                # 角色未参与但受影响：可能产生新目标
                self._check_trigger_new_goal(char, event)
```

### 3.3 世界状态快照（WorldSnapshot）

```python
@dataclass
class WorldSnapshot:
    """章节开始/结束时的世界状态快照"""
    chapter: int
    timestamp: float
    
    # 所有角色当前状态
    character_states: dict[str, dict]
    # 活跃的因果线
    active_causal_threads: list[str]
    # 未回收的伏笔
    open_foreshadows: list[str]
    # 当前冲突
    active_conflicts: list[str]
    
    @classmethod
    def take_snapshot(cls, engine_state) -> 'WorldSnapshot':
        """拍照当前世界状态"""
        pass
    
    def diff(self, previous: 'WorldSnapshot') -> dict:
        """对比两个快照，发现变化"""
        pass
```

---

## 四、与现有系统集成

### 4.1 数据文件结构
```
.novel_{project}/
  ├── story_state.json          # 已有：StoryState
  ├── causal_graph.json         # 新增：事件因果图
  ├── character_engine.json     # 新增：角色行为状态
  └── snapshots/                # 新增：章节快照
      ├── ch001_before.json
      ├── ch001_after.json
      └── ...
```

### 4.2 写作流程集成

```
写前阶段（before chapter write）:
  1. 加载因果图 → 提取当前活跃线索
  2. 加载角色引擎 → 获取每个角色的当前目标和优先行动
  3. 生成 "前情提要+角色动机" 上下文 → 注入 system prompt

写后阶段（after chapter write）:
  1. STAC 分类新事件
  2. 构建因果边 + 反事实验证
  3. 角色引擎 tick（重新计算目标、更新关系）
  4. 世界状态快照 → 保存
  5. 伏笔自动登记
```

### 4.3 第一次运行时
- 从现有 `story_state.json` + manuscript 自动逆向抽取初始事件图
- LLM 扫描前 N 章，构建初始因果链和角色状态

---

## 五、实现优先级

| 阶段 | 内容 | 依赖 | 工作量 |
|------|------|------|--------|
| P0: MVP | EventNode + 基础因果图 + 手动添加事件 | 无 | 2-3天 |
| P1: 自动抽取 | LLM 扫描章节自动提取事件+因果 | P0 | +2天 |
| P2: 角色引擎 | CharacterNode + GOAP 目标系统 | P0 | +3天 |
| P3: 写作集成 | 写前上下文注入 + 写后自动更新 | P1+P2 | +1天 |
| P4: 可视化 | 因果图/角色关系图 WebUI 展示 | P3 | +2天 |

## 六、参考文献

1. STAC: Li et al., "Beyond LLMs: A Linguistic Approach to Causal Graph Generation", ACL WNU 2025
2. R²/CPC: Lin et al., "Novel-to-Screenplay Generation with Causal Plot Graphs", ICLR 2025
3. E²RAG: "Respecting Temporal-Causal Consistency: Entity-Event Knowledge Graphs", arXiv 2025
4. EventRAG: Yang et al., "Enhancing LLM Generation with Event Knowledge Graphs", ACL 2025
5. GEST: "Agentic Video Generation: From Text to Executable Event Graphs", arXiv 2026
6. PLOTTER: "Planning Beyond Text: Graph-based Reasoning for Narrative Generation", ACL 2026
7. GOAP: Orkin, "Goal-Oriented Action Planning", MIT Media Lab 2006 + GDC 2025 Kingdom Come II
8. Utility AI: Roberts (ed.), "Game AI Uncovered Vol.2", CRC Press 2024
9. PlotPilot: shenminglinyi/PlotPilot, GitHub 2024
10. CreAgentive: Sichuan Univ., "Multi-Category Creative Generation Engine", 2025
