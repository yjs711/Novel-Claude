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

    def find_character_by_name(self, name: str) -> CharacterNode | None:
        for c in self.characters.values():
            if c.name == name:
                return c
        return None

    def _update_character_appearances(self, event: EventNode):
        """记录角色出场信息"""
        for name in event.participants:
            for char in self.characters.values():
                if char.name == name:
                    if char.first_appearance == 0 or event.chapter < char.first_appearance:
                        char.first_appearance = event.chapter
                    if event.chapter > char.last_appearance:
                        char.last_appearance = event.chapter
                    break

    def _ensure_characters_from_events(self):
        """从已有事件中自动创建角色节点"""
        for event in self.events.values():
            for name in event.participants:
                if name and name not in ["未知", ""] and not self.find_character_by_name(name):
                    char = CharacterNode(id="", name=name)
                    self.add_character(char)

    # ── 反事实验证 ─────────────────────────────────────────

    def counterfactual_verify(self, cause_id: str, effect_id: str) -> bool:
        """P0 规则版，P1 接入 LLM"""
        cause = self.events.get(cause_id)
        effect = self.events.get(effect_id)
        if not cause or not effect:
            return False
        if (cause.chapter == effect.chapter
                and set(cause.participants) & set(effect.participants)
                and cause.stac_type == "action"
                and effect.stac_type == "consequence"):
            return True
        if (effect.chapter - cause.chapter > 3
                and not (set(cause.participants) & set(effect.participants))):
            return False
        if (set(cause.participants) & set(effect.participants)
                and cause.emotional_valence * effect.emotional_valence > 0):
            return True
        return False

    # ═════════════════════════════════════════════════════════════
    # P2: 角色行为引擎 (GOAP + Utility AI)
    # ═════════════════════════════════════════════════════════════

    def tick_characters(self, chapter: int, new_events: list[EventNode]):
        """章节写完后调用: 推演所有角色状态"""
        self._ensure_characters_from_events()
        for char in self.characters.values():
            for goal in char.goals:
                goal.priority = self._calc_goal_priority(char, goal, chapter)
            self._update_relationships(char, new_events)
            self._check_new_goals(char, new_events)
            for event in new_events:
                if char.name in event.participants:
                    if char.first_appearance == 0 or event.chapter < char.first_appearance:
                        char.first_appearance = event.chapter
                    char.last_appearance = event.chapter
        self.save()

    def _calc_goal_priority(self, char: CharacterNode, goal: Goal, current_chapter: int) -> float:
        """Utility AI: priority = 性格匹配 × 紧迫度"""
        p = char.personality
        desc = goal.description
        base = 0.5
        if any(w in desc for w in ["复仇","杀死","击败","摧毁","消灭"]):
            base = p["aggression"] * 1.0 + p["ambition"] * 0.5
        elif any(w in desc for w in ["保护","守护","拯救","帮助"]):
            base = p["empathy"] * 1.0 + p["loyalty"] * 0.5
        elif any(w in desc for w in ["力量","修炼","突破","变强","获得"]):
            base = p["ambition"] * 1.0 + p["cunning"] * 0.3
        elif any(w in desc for w in ["隐藏","秘密","调查","收集情报"]):
            base = p["cunning"] * 1.0
        urgency = 1.0
        if goal.deadline_chapter:
            remaining = goal.deadline_chapter - current_chapter
            if remaining <= 0: urgency = 1.5
            elif remaining < 5: urgency = 1.0 + (5 - remaining) * 0.1
            else: urgency = 0.5
        return max(0.0, min(1.5, base * urgency))

    def _update_relationships(self, char: CharacterNode, events: list[EventNode]):
        """基于事件更新角色关系"""
        for event in events:
            participants = set(event.participants)
            if char.name not in participants:
                continue
            for other_name in participants:
                if other_name == char.name:
                    continue
                other = self.find_character_by_name(other_name)
                if not other:
                    continue
                rel = char.relationships.get(other.id)
                if not rel:
                    rel = Relationship(target_id=other.id, rel_type="neutral")
                    char.relationships[other.id] = rel
                if event.emotional_valence > 0.5:
                    rel.intensity = min(1.0, rel.intensity + 0.1)
                    if rel.intensity > 0.5: rel.rel_type = "ally"
                elif event.emotional_valence < -0.5:
                    rel.intensity = max(-1.0, rel.intensity - 0.1)
                    if rel.intensity < -0.3: rel.rel_type = "enemy"
                elif event.event_type == "dialogue":
                    if event.emotional_valence > 0.3:
                        rel.intensity = min(1.0, rel.intensity + 0.05)
                    elif event.emotional_valence < -0.3:
                        rel.intensity = max(-1.0, rel.intensity - 0.05)
                rel.history.append(event.id)
                rel.last_updated = event.chapter

    def _check_new_goals(self, char: CharacterNode, events: list[EventNode]):
        """事件驱动的目标触发"""
        for event in events:
            text = event.summary
            if char.name not in event.participants:
                continue
            if any(w in text for w in ["发现","得知","听说","听闻","暴露"]):
                desc = f"调查: {text[:30]}"
                if not any(g.description == desc for g in char.goals):
                    char.goals.append(Goal(id=f"g_{len(char.goals)+1:03d}", description=desc, priority=0.6))
            if any(w in text for w in ["袭击","追杀","攻击","埋伏"]):
                desc = f"应对威胁: {text[:30]}"
                if not any(g.description == desc for g in char.goals):
                    char.goals.append(Goal(id=f"g_{len(char.goals)+1:03d}", description=desc, priority=0.8))

    def get_character_context(self, char_id: str) -> str:
        """生成角色上下文（注入写作 prompt）"""
        char = self.characters.get(char_id)
        if not char:
            return ""
        parts = [f"【{char.name}】"]
        active_goals = sorted([g for g in char.goals if g.status == "active"], key=lambda g: g.priority, reverse=True)
        if active_goals:
            parts.append("当前目标:")
            for g in active_goals[:3]:
                parts.append(f"  - {g.description} (优先级:{g.priority:.1f})")
        if char.relationships:
            parts.append("关键关系:")
            for rid, rel in sorted(char.relationships.items(), key=lambda x: abs(x[1].intensity), reverse=True)[:5]:
                other = self.characters.get(rid)
                name = other.name if other else rid
                tag = {-1:"🔴", 0:"⚪", 0.3:"🟢", 0.5:"💚"}.get(rel.intensity, "⚪")
                parts.append(f"  {tag} {name}: {rel.rel_type}({rel.intensity:+.1f})")
        p = char.personality
        traits = []
        if p["ambition"] > 0.65: traits.append("有野心")
        if p["loyalty"] > 0.65: traits.append("重情义")
        if p["aggression"] > 0.65: traits.append("好斗")
        if p["cunning"] > 0.65: traits.append("狡黠")
        if p["empathy"] > 0.65: traits.append("有同理心")
        if traits:
            parts.append(f"性格: {', '.join(traits)}")
        return "\n".join(parts)

    def get_active_characters_context(self, chapter: int) -> str:
        """获取当前章节活跃角色的上下文"""
        recent = [c for c in self.characters.values() if c.last_appearance >= chapter - 3 and c.last_appearance > 0]
        recent.sort(key=lambda c: c.last_appearance, reverse=True)
        contexts = [self.get_character_context(c.id) for c in recent[:5] if c.goals or c.relationships]
        return "\n\n".join(contexts) if contexts else ""

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
            if len(sent) < 8 or sent.startswith("#") or sent.startswith("*"):
                continue
            participants = []
            bracketed = re.findall(r'【(.+?)】|"([^"]+)"', sent)
            if not bracketed:
                words = re.findall(r'[一-鿿]{2,4}', sent)
                participants = words[:2] if len(words) >= 2 else ["未知"]
            event_type = "action" if any(w in sent for w in ["杀", "打", "攻击", "修炼", "突破"]) else "dialogue" if "说" in sent or "道" in sent else "transition"
            stac = self.classify_stac(sent, event_type)
            evt = EventNode(
                id="", chapter=chapter_num, event_type=event_type,
                stac_type=stac, summary=sent[:80], participants=participants,
                emotional_valence=0.0,
            )
            self.add_event(evt)
            count += 1
        self.save()
        return count

    def extract_events_llm(self, chapter_num: int, content: str, model: str | None = None) -> int:
        """
        使用 LLM 精确提取事件 + 因果链接（P1）

        基于 STAC 框架: Situation→Task→Action→Consequence
        返回提取到的事件数
        """
        from utils.llm_client import get_task_client, get_task_model, _llm_temperature

        client = get_task_client("planning")
        if model is None:
            model = get_task_model("planning")

        # 截取内容（避免超长）
        text = content[:6000]

        system = """你是小说结构分析师。从章节中提取关键事件，输出 JSON。

事件类型 (STAC):
- situation: 设定/环境建立
- task: 决定/计划/目标
- action: 具体行动/战斗/对话推进
- consequence: 结果/影响/变化

输出格式（只输出 JSON 数组，不要解释）:
[{"summary":"事件描述(20字内)","stac":"action","participants":["角色名"],"causes":["前置事件描述"],"emotional":0.5}]"""

        user = f"""分析以下小说章节，提取 8-15 个关键事件。每个事件包含: summary(20字内描述)、stac(situation/task/action/consequence)、participants(参与角色列表)、causes(前置事件描述——如果此事件是另一事件的直接结果) 、emotional(-1到1的情感值)。

章节正文:
{text}

请只输出 JSON 数组。"""

        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.3,
                max_tokens=2048,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            raw = response.choices[0].message.content
            # 提取 JSON 数组
            match = re.search(r'\[[\s\S]*\]', raw)
            if not match:
                print(f"  [⚠️] LLM 返回非 JSON 格式: {raw[:200]}")
                return 0

            events_data = json.loads(match.group())
            count = 0
            for ed in events_data:
                evt = EventNode(
                    id="",
                    chapter=chapter_num,
                    event_type="action",
                    stac_type=ed.get("stac", "action"),
                    summary=ed.get("summary", "")[:80],
                    participants=ed.get("participants", []),
                    emotional_valence=ed.get("emotional", 0.0),
                )
                eid = self.add_event(evt)

                # 处理因果链
                for cause_desc in ed.get("causes", []):
                    # 在已有事件中查找匹配的前置事件
                    for existing in list(self.events.values()):
                        if (existing.chapter == chapter_num
                                and cause_desc[:10] in existing.summary
                                and existing.id != eid):
                            self._link(existing.id, eid, confidence=0.7)
                            break

                count += 1

            self.save()
            return count

        except Exception as e:
            print(f"  [⚠️] LLM 提取失败: {e}")
            return 0
