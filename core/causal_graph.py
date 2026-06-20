"""
因果图引擎 — 事件节点 + 因果边 + 伏笔追踪

基于:
- STAC: Li et al., ACL WNU 2025 (Situation/Task/Action/Consequence 四元分类)
- R²/CPC: Lin et al., ICLR 2025 (Causal Plot Graphs 贪婪破圈)
- E²RAG: 2025 (实体-事件双图)

用法:
    engine = CausalGraphEngine(project_dir)
    engine.add_event(EventNode(...))
    engine.save()
"""
from __future__ import annotations

import json, time, hashlib, re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Any

# ═══════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════

STAC_TYPES = ("situation", "task", "action", "consequence")
EVENT_TYPES = ("action", "dialogue", "revelation", "conflict", "resolution", "transition")


@dataclass
class EventNode:
    """因果图中的事件节点"""
    id: str                               # 唯一标识，如 "evt_042"
    chapter: int                          # 发生章节
    event_type: str                       # action/dialogue/revelation/conflict/resolution/transition
    stac_type: str                        # situation/task/action/consequence (STAC 四元)
    summary: str                          # 一句话概括
    participants: list[str] = field(default_factory=list)  # 参与角色
    location: str = ""                    # 发生地点
    emotional_valence: float = 0.0        # -1.0 到 +1.0

    # 因果边
    causes: list[str] = field(default_factory=list)   # 前置事件ID
    effects: list[str] = field(default_factory=list)   # 后置事件ID
    confidence: float = 1.0               # 因果确信度 0-1

    # 伏笔追踪
    foreshadow_plant: bool = False        # 是否埋下伏笔
    foreshadow_target: str | None = None  # 预计回收此伏笔的事件ID
    foreshadow_payoff: bool = False       # 是否回收了伏笔
    foreshadow_desc: str = ""             # 伏笔描述

    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v or k == "id"}

    @classmethod
    def from_dict(cls, d: dict) -> "EventNode":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Goal:
    """角色目标（GOAP 核心）"""
    id: str
    description: str                     # "复仇：找到杀害师父的凶手"
    priority: float = 0.5                # 优先级 0-1
    preconditions: list[str] = field(default_factory=list)
    desired_state: dict[str, Any] = field(default_factory=dict)
    deadline_chapter: int | None = None
    status: str = "active"               # active/achieved/abandoned


@dataclass
class Relationship:
    """角色关系"""
    target_id: str
    rel_type: str                        # ally/enemy/neutral/family/romance/rival
    intensity: float = 0.0               # -1.0(死敌) 到 +1.0(挚爱)
    history: list[str] = field(default_factory=list)  # 关键事件ID
    last_updated: int = 0


@dataclass
class CharacterNode:
    """角色节点（P2 完整实现，P0 先定义数据结构）"""
    id: str
    name: str
    role: str = ""                       # protagonist/antagonist/supporting/minor
    goals: list[Goal] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    personality: dict[str, float] = field(default_factory=lambda: {
        "ambition": 0.5, "loyalty": 0.5, "aggression": 0.5,
        "cunning": 0.5, "empathy": 0.5,
    })
    relationships: dict[str, Relationship] = field(default_factory=dict)
    first_appearance: int = 0
    last_appearance: int = 0


# ═══════════════════════════════════════════════════════════════════
# 因果图引擎
# ═══════════════════════════════════════════════════════════════════

class CausalGraphEngine:
    """维护事件因果图，提供增删改查和持久化"""

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.events: dict[str, EventNode] = {}
        self.characters: dict[str, CharacterNode] = {}
        self._file = self.project_dir / "causal_graph.json"
        self._next_id = 1
        self.load()

    # ── 持久化 ───────────────────────────────────────────────────

    def load(self):
        """从 JSON 文件加载因果图"""
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
                for ed in data.get("events", []):
                    node = EventNode.from_dict(ed)
                    self.events[node.id] = node
                    num = int(node.id.split("_")[-1])
                    self._next_id = max(self._next_id, num + 1)
                for cd in data.get("characters", []):
                    char = CharacterNode(**cd)
                    self.characters[char.id] = char
            except Exception as e:
                print(f"  [⚠️] 加载因果图失败: {e}")

    def save(self):
        """保存因果图到 JSON"""
        data = {
            "events": [e.to_dict() for e in self.events.values()],
            "characters": [
                {
                    "id": c.id, "name": c.name, "role": c.role,
                    "goals": [asdict(g) for g in c.goals],
                    "state": c.state,
                    "personality": c.personality,
                    "relationships": {k: asdict(v) for k, v in c.relationships.items()},
                    "first_appearance": c.first_appearance,
                    "last_appearance": c.last_appearance,
                }
                for c in self.characters.values()
            ],
            "meta": {"version": "0.1", "updated": time.time()}
        }
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 事件管理 ────────────────────────────────────────────────

    def add_event(self, event: EventNode) -> str:
        """添加事件，自动分配ID，返回ID"""
        if not event.id or event.id in self.events:
            event.id = f"evt_{self._next_id:04d}"
            self._next_id += 1

        # 自动检测因果链
        self._auto_link(event)

        self.events[event.id] = event
        self._update_character_appearances(event)
        return event.id

    def _auto_link(self, event: EventNode):
        """自动检测因果链：在已有事件中查找候选前置原因"""
        # 1. 规则过滤：同章节或前章节的事件
        candidates = [
            e for e in self.events.values()
            if e.chapter <= event.chapter and e.id != event.id
        ]
        if not candidates:
            return

        # 2. 简单启发式：参与者重叠 → 可能相关
        event_chars = set(event.participants)
        for c in candidates:
            c_chars = set(c.participants)
            # 两个事件有共同角色，且情感方向一致 → 可能是因果
            if event_chars & c_chars:
                if event.stac_type == "consequence" and c.stac_type in ("action", "task"):
                    # 行动→结果 是最强的因果模式
                    self._link(c.id, event.id, confidence=0.8)
                elif event.chapter == c.chapter and c.stac_type == "action" and event.stac_type == "action":
                    # 同章节连续行动可能无关（只是时间顺序）
                    pass
                else:
                    # 默认轻声链接
                    score = 0.3
                    if event.location == c.location:
                        score += 0.2
                    if c.stac_type == "action" and event.stac_type == "consequence":
                        score += 0.3
                    if score >= 0.5:
                        self._link(c.id, event.id, confidence=score)

    def _link(self, cause_id: str, effect_id: str, confidence: float = 1.0):
        """建立因果边"""
        cause = self.events.get(cause_id)
        effect = self.events.get(effect_id)
        if not cause or not effect:
            return
        if effect_id not in cause.effects:
            cause.effects.append(effect_id)
        if cause_id not in effect.causes:
            effect.causes.append(cause_id)
        effect.confidence = min(1.0, max(effect.confidence, confidence))

    def get_event(self, event_id: str) -> EventNode | None:
        return self.events.get(event_id)

    def get_chapter_events(self, chapter: int) -> list[EventNode]:
        """按章节号获取事件"""
        return sorted(
            [e for e in self.events.values() if e.chapter == chapter],
            key=lambda e: e.id
        )

    def get_causal_chain(self, event_id: str, depth: int = 3) -> dict:
        """获取某个事件的前因后果链"""
        event = self.events.get(event_id)
        if not event:
            return {"error": f"事件 {event_id} 不存在"}

        def trace_up(eid, d):
            if d <= 0:
                return []
            e = self.events.get(eid)
            if not e:
                return []
            result = []
            for cid in e.causes:
                result.append({"id": cid, "summary": self.events[cid].summary if cid in self.events else "?"})
                result.extend(trace_up(cid, d - 1))
            return result

        def trace_down(eid, d):
            if d <= 0:
                return []
            e = self.events.get(eid)
            if not e:
                return []
            result = []
            for cid in e.effects:
                result.append({"id": cid, "summary": self.events[cid].summary if cid in self.events else "?"})
                result.extend(trace_down(cid, d - 1))
            return result

        return {
            "event": {"id": event.id, "summary": event.summary, "stac": event.stac_type,
                       "chapter": event.chapter, "participants": event.participants},
            "causes": trace_up(event_id, depth),
            "effects": trace_down(event_id, depth),
        }

    def get_active_threads(self) -> list[dict]:
        """获取当前所有未闭合的因果线（有因无果的事件）"""
        threads = []
        for e in self.events.values():
            if e.stac_type in ("action", "task") and not e.effects:
                threads.append({
                    "id": e.id,
                    "chapter": e.chapter,
                    "summary": e.summary,
                    "participants": e.participants,
                    "stac": e.stac_type,
                })

            # 伏笔未回收的
            if e.foreshadow_plant and not e.foreshadow_payoff:
                threads.append({
                    "id": e.id,
                    "chapter": e.chapter,
                    "summary": f"🔮 伏笔: {e.foreshadow_desc or e.summary}",
                    "participants": e.participants,
                    "stac": "foreshadow",
                })

        return sorted(threads, key=lambda t: t["chapter"])

    def get_summary(self) -> dict:
        """引擎状态摘要"""
        chs = set(e.chapter for e in self.events.values())
        chars_with_goals = [c for c in self.characters.values() if c.goals]
        return {
            "total_events": len(self.events),
            "chapters_covered": sorted(chs),
            "active_threads": len(self.get_active_threads()),
            "characters": len(self.characters),
            "characters_with_goals": len(chars_with_goals),
            "foreshadows_planted": sum(1 for e in self.events.values() if e.foreshadow_plant),
            "foreshadows_paid": sum(1 for e in self.events.values() if e.foreshadow_payoff),
        }

    # ── 角色管理 ────────────────────────────────────────────────

    def add_character(self, char: CharacterNode):
        if not char.id:
            char.id = f"char_{len(self.characters) + 1:03d}"
        self.characters[char.id] = char

    def get_character(self, char_id: str) -> CharacterNode | None:
        return self.characters.get(char_id)

    def _update_character_appearances(self, event: EventNode):
        """记录角色出场信息"""
        for name in event.participants:
            # 按名称匹配角色
            for char in self.characters.values():
                if char.name == name:
                    if char.first_appearance == 0 or event.chapter < char.first_appearance:
                        char.first_appearance = event.chapter
                    if event.chapter > char.last_appearance:
                        char.last_appearance = event.chapter
                    break

    # ── 反事实验证（P0 stub, P1 接入 LLM） ────────────────────────

    def counterfactual_verify(self, cause_id: str, effect_id: str) -> bool:
        """
        反事实验证（Beyond LLMs 论文方法）：
        "如果前提事件没发生，结果事件是否依然合理？"
        P0: 规则推断（同章节+同角色 → 高度相关）
        P1: 接入 LLM 判断
        """
        cause = self.events.get(cause_id)
        effect = self.events.get(effect_id)
        if not cause or not effect:
            return False

        # 规则1: 同章节 + 同角色 + 行动→结果 = 强因果
        if (cause.chapter == effect.chapter
                and set(cause.participants) & set(effect.participants)
                and cause.stac_type == "action"
                and effect.stac_type == "consequence"):
            return True

        # 规则2: 不同章节 + 无共同角色 = 弱相关
        if (effect.chapter - cause.chapter > 3
                and not (set(cause.participants) & set(effect.participants))):
            return False

        # 规则3: 有共同角色 + 情感方向一致 = 可能因果
        if (set(cause.participants) & set(effect.participants)
                and cause.emotional_valence * effect.emotional_valence > 0):
            return True

        return False

    # ── STAC 分类辅助 ───────────────────────────────────────────

    @staticmethod
    def classify_stac(summary: str, event_type: str) -> str:
        """
        简单启发式 STAC 分类（P0 版本，P1 接入 LLM 做精确分类）
        """
        # 行动类词汇 → action
        action_words = ["攻击", "杀死", "打败", "抢夺", "偷", "破坏", "创建", "建造",
                         "修炼", "突破", "斩杀", "夺", "刺杀", "击败", "灭", "战"]
        # 任务类词汇 → task
        task_words = ["决定", "计划", "安排", "寻找", "调查", "追踪", "追查", "前往",
                       "收到", "接到", "奉命", "出发", "准备"]
        # 结果类词汇 → consequence
        consequence_words = ["导致", "引发", "结果", "因此", "最终", "成功", "失败",
                              "暴露", "发现", "得知", "获得", "失去", "重伤", "陨落"]
        # 其余 → situation
        for w in action_words:
            if w in summary: return "action"
        for w in task_words:
            if w in summary: return "task"
        for w in consequence_words:
            if w in summary: return "consequence"
        return "situation"

    # ── 从现有章节批量导入 ────────────────────────────────────────

    def import_from_chapter(self, chapter_num: int, content: str):
        """
        从章节正文中提取事件（P0 简单分句版本，P1 接入 LLM 精确提取）
        返回提取到的事件数
        """
        # 按句号分句，每句作为一个候选事件
        sentences = [s.strip() for s in re.split(r'[。！？\n]', content) if len(s.strip()) > 5]
        count = 0
        for sent in sentences:
            # 跳过太短的句子和纯描述
            if len(sent) < 8 or sent.startswith("#") or sent.startswith("*"):
                continue

            # 简单命名实体检测：在【】或""中的内容优先
            participants = []
            bracketed = re.findall(r'【(.+?)】|"([^"]+)"', sent)
            if not bracketed:
                # 取前两个名词作为参与者
                words = re.findall(r'[一-鿿]{2,4}', sent)
                participants = words[:2] if len(words) >= 2 else ["未知"]

            event_type = "action" if any(w in sent for w in ["杀", "打", "攻击", "修炼", "突破"]) else "dialogue" if "说" in sent or "道" in sent else "transition"
            stac = self.classify_stac(sent, event_type)

            evt = EventNode(
                id="",
                chapter=chapter_num,
                event_type=event_type,
                stac_type=stac,
                summary=sent[:80],
                participants=participants,
                emotional_valence=0.0,
            )
            self.add_event(evt)
            count += 1

        self.save()
        return count
