"""
Novel-Claude Fusion — Storyform (NCP-compatible structural constraints)

Implements Narrative Context Protocol v1.3.0 schema (Dramatica Co. + USC, MIT).
NCP is the open standard for transporting authorial intent across
multi-agent narrative systems.

Templates are based on verified Dramatica storyform examples:
  Hamlet (revenge/tragedy) and Star Wars (hero's journey/triumph).

Source: Dramatica.com official documentation, NCP v1.3.0 schema,
  Narrative First analysis (Hamlet, Star Wars: A New Hope)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any


@dataclass
class Throughline:
    """NCP Throughline — one perspective on the central inequity."""
    domain: str = ""          # Universe | Physics | Psychology | Mind
    concern: str = ""         # plot-like goal area
    problem: str = ""         # source of inequity
    solution: str = ""        # resolution direction
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}

    @classmethod
    def from_dict(cls, data: dict) -> "Throughline":
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class StoryDynamics:
    resolve: str = "Change"     # Change | Steadfast
    outcome: str = "Success"    # Success | Failure
    judgement: str = "Good"     # Good | Bad
    driver: str = "Decision"    # Decision | Action
    limit: str = "Optionlock"   # Optionlock | Timelock


@dataclass
class Storyform:
    """NCP-compatible storyform — the structural argument of a story."""
    title: str = ""
    version: str = "ncp-1.3.0"
    objective_story: Throughline = field(default_factory=Throughline)
    main_character: Throughline = field(default_factory=Throughline)
    influence_character: Throughline = field(default_factory=Throughline)
    relationship_story: Throughline = field(default_factory=Throughline)
    dynamics: StoryDynamics = field(default_factory=StoryDynamics)
    genre: str = ""
    central_inequity: str = ""
    thematic_argument: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title, "version": self.version,
            "genre": self.genre,
            "central_inequity": self.central_inequity,
            "thematic_argument": self.thematic_argument,
            "objective_story": self.objective_story.to_dict(),
            "main_character": self.main_character.to_dict(),
            "influence_character": self.influence_character.to_dict(),
            "relationship_story": self.relationship_story.to_dict(),
            "dynamics": asdict(self.dynamics),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Storyform":
        sf = cls(
            title=data.get("title", ""),
            version=data.get("version", "ncp-1.3.0"),
            genre=data.get("genre", ""),
            central_inequity=data.get("central_inequity", ""),
            thematic_argument=data.get("thematic_argument", ""),
        )
        for key in ("objective_story","main_character","influence_character","relationship_story"):
            if key in data:
                setattr(sf, key, Throughline.from_dict(data[key]))
        if "dynamics" in data:
            sf.dynamics = StoryDynamics(**{k:v for k,v in data["dynamics"].items()
                                           if k in StoryDynamics.__dataclass_fields__})
        return sf

    @classmethod
    def empty(cls, title: str = "", genre: str = "") -> "Storyform":
        return cls(title=title, genre=genre,
                   objective_story=Throughline(domain="Physics"),
                   main_character=Throughline(domain="Universe"),
                   dynamics=StoryDynamics())

    def to_writing_context(self) -> str:
        parts = ["\n[Storyform — Narrative Structural Constraints (NCP)]\n"]
        if self.central_inequity:
            parts.append(f"Central Conflict: {self.central_inequity}")
        if self.thematic_argument:
            parts.append(f"Thematic Argument: {self.thematic_argument}")
        d = self.dynamics
        parts.append(f"Structure: {d.resolve}-type protagonist, {d.outcome}/{d.judgement} ending")
        for name, tl in [("Objective Story",self.objective_story),("Main Character",self.main_character),
                         ("Influence Character",self.influence_character),("Relationship Story",self.relationship_story)]:
            if tl.domain:
                parts.append(f"{name}: {tl.domain}")
                if tl.problem:
                    parts.append(f"  Problem: {tl.problem} -> Solution: {tl.solution}")
                if tl.description:
                    parts.append(f"  {tl.description[:120]}")
        parts.append("")
        parts.append("Writing constraints from storyform:")
        parts.append(f"- MC approach: {d.resolve} under pressure")
        if self.influence_character.domain:
            parts.append(f"- Include IC's alternative perspective ({self.influence_character.domain})")
        parts.append("- Let structure carry meaning — don't explain the theme")
        parts.append("")
        return "\n".join(parts)

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ── Verified templates (Dramatica official examples) ────────────────────────
# Sources: Dramatica.com, Narrative First analysis
# Hamlet = revenge/tragedy. Star Wars = hero's journey/triumph.

TEMPLATE_HAMLET = Storyform(
    title="Revenge Tragedy (Hamlet pattern)",
    genre="revenge",
    central_inequity="A murder has been committed and justice demands vengeance, but the pursuit of revenge corrupts everyone it touches.",
    thematic_argument="Revenge is not justice — it is a disease that spreads until nothing is left.",
    objective_story=Throughline(
        domain="Mind", concern="Memory",
        problem="Pursuit", solution="Avoid",
        description="The court consumed by suspicion, fear, and the demand for vengeance. OS(Physics) -> RS(Psychology) dynamic pair.",
    ),
    main_character=Throughline(
        domain="Universe", concern="Future",
        problem="Control", solution="Uncontrolled",
        description="Hamlet: trapped in a situation he didn't choose. 'What is it like to be in my position?' MC(Universe) ↔ IC(Mind).",
    ),
    influence_character=Throughline(
        domain="Mind", concern="Subconscious",
        problem="Avoid", solution="Pursuit",
        description="The Ghost: a fixed attitude demanding vengeance. Challenges Hamlet's hesitation with the weight of duty.",
    ),
    relationship_story=Throughline(
        domain="Universe", concern="Future",
        problem="Control", solution="Uncontrolled",
        description="The Ghost & Hamlet's pact — their shared situation. RS(Universe) ↔ OS(Mind) diagonal pair.",
    ),
    dynamics=StoryDynamics(resolve="Change", outcome="Failure", judgement="Bad",
                           driver="Decision", limit="Timelock"),
)

TEMPLATE_STARWARS = Storyform(
    title="Hero's Journey (Star Wars pattern)",
    genre="fantasy",
    central_inequity="An oppressive Empire controls the galaxy; a small rebellion fights for freedom with a weapon that can destroy worlds.",
    thematic_argument="True power comes not from technology or force, but from trusting in something greater than yourself.",
    objective_story=Throughline(
        domain="Physics", concern="Obtaining",
        problem="Pursuit", solution="Avoid",
        description="Rebel Alliance vs Empire: obtaining Death Star plans, destroying the weapon. OS(Physics) -> RS(Psychology).",
    ),
    main_character=Throughline(
        domain="Universe", concern="Future",
        problem="Control", solution="Uncontrolled",
        description="Luke: farm boy dreaming of stars, discovers his destiny. 'What is it like to be in my situation?'",
    ),
    influence_character=Throughline(
        domain="Mind", concern="Subconscious",
        problem="Avoid", solution="Pursuit",
        description="Obi-Wan: fanatic faith in the Force. A fixed mindset that challenges Luke's material worldview.",
    ),
    relationship_story=Throughline(
        domain="Psychology", concern="Becoming",
        problem="Reconsider", solution="Consider",
        description="Obi-Wan & Luke: mentor-student bound by shared loss. 'Who are we really? How should we act?'",
    ),
    dynamics=StoryDynamics(resolve="Change", outcome="Success", judgement="Good",
                           driver="Action", limit="Optionlock"),
)

STORYFORM_TEMPLATES = {
    "revenge": TEMPLATE_HAMLET,
    "rise_to_power": TEMPLATE_STARWARS,
}
