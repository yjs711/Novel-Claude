"""
Novel-Claude Fusion — Storyform (NCP-compatible structural constraints)

Implements Narrative Context Protocol v1.3.0 schema as Python dataclasses.
NCP is the open standard for transporting authorial intent across
multi-agent narrative systems (Dramatica Co. + USC, MIT license).

This gives Novel-Claude the "storyform-first" approach recommended by
Dramatica 2026: define the structural argument before generating prose.

Unlike full Dramatica/Narrova integration, this is a lightweight subset
that captures the critical constraints to prevent AI narrative homogenization.

Usage:
  storyform = Storyform.from_dict(cfg)         # load from .novel/storyform.json
  constraints = storyform.to_writing_context() # inject into chapter prompt
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any


# ── NCP v1.3.0 dataclasses ───────────────────────────────────────────────────

# Four Throughlines (the central narrative argument from 4 perspectives)
@dataclass
class Throughline:
    """NCP Throughline — one perspective on the central inequity."""
    domain: str = ""                 # Universe | Physics | Psychology | Mind
    concern: str = ""               # what the characters are focused on
    issue: str = ""                 # the thematic issue being explored
    problem: str = ""               # the source of inequity
    solution: str = ""              # the resolution direction
    catalyst: str = ""              # what accelerates the problem
    inhibitor: str = ""             # what restrains the problem
    benchmark: str = ""             # measure of progress
    description: str = ""           # human-readable summary
    perspective: str = ""           # "They" | "I" | "You" | "We"

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}

    @classmethod
    def from_dict(cls, data: dict) -> "Throughline":
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})


# NCP Dynamics
@dataclass
class StoryDynamics:
    """NCP Story Dynamics — how the narrative argument resolves."""
    resolve: str = "Change"          # Change | Steadfast
    outcome: str = "Success"         # Success | Failure
    judgement: str = "Good"          # Good | Bad
    driver: str = "Decision"         # Decision | Action
    limit: str = "Optionlock"       # Optionlock | Timelock

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}


# ── Storyform container ──────────────────────────────────────────────────────

@dataclass
class Storyform:
    """
    NCP-compatible storyform — the structural argument of a story.

    Defines what the story is arguing BEFORE prose generation begins.
    Prevents AI from defaulting to homogeneous narrative shapes.

    References:
      NCP v1.3.0: github.com/narrative-first/narrative-context-protocol
      Dramatica: "Put the narrative first" (May 2026)
    """
    title: str = ""
    version: str = "ncp-1.3.0"

    # Four Throughlines
    objective_story: Throughline = field(default_factory=lambda: Throughline(domain="Physics"))
    main_character: Throughline = field(default_factory=lambda: Throughline(domain="Universe"))
    influence_character: Throughline = field(default_factory=Throughline)
    relationship_story: Throughline = field(default_factory=Throughline)

    # Dynamics
    dynamics: StoryDynamics = field(default_factory=StoryDynamics)

    # Genre constraints
    genre: str = ""
    subgenre: str = ""

    # Key thematic question
    central_inequity: str = ""     # "What problem drives the entire story?"
    thematic_argument: str = ""    # "What is the story arguing?"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "version": self.version,
            "objective_story": self.objective_story.to_dict(),
            "main_character": self.main_character.to_dict(),
            "influence_character": self.influence_character.to_dict(),
            "relationship_story": self.relationship_story.to_dict(),
            "dynamics": self.dynamics.to_dict(),
            "genre": self.genre,
            "subgenre": self.subgenre,
            "central_inequity": self.central_inequity,
            "thematic_argument": self.thematic_argument,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Storyform":
        sf = cls(
            title=data.get("title", ""),
            version=data.get("version", "ncp-1.3.0"),
            genre=data.get("genre", ""),
            subgenre=data.get("subgenre", ""),
            central_inequity=data.get("central_inequity", ""),
            thematic_argument=data.get("thematic_argument", ""),
        )
        for key in ("objective_story", "main_character", "influence_character", "relationship_story"):
            if key in data:
                setattr(sf, key, Throughline.from_dict(data[key]))
        if "dynamics" in data:
            sf.dynamics = StoryDynamics(**{k: v for k, v in data["dynamics"].items()
                                           if k in StoryDynamics.__dataclass_fields__})
        return sf

    @classmethod
    def empty(cls, title: str = "", genre: str = "") -> "Storyform":
        """Create a minimal default storyform."""
        return cls(
            title=title,
            genre=genre,
            objective_story=Throughline(domain="Physics", perspective="They",
                                        description="The external conflict driving events"),
            main_character=Throughline(domain="Universe", perspective="I",
                                       description="The protagonist's personal struggle"),
            dynamics=StoryDynamics(),
        )

    def to_writing_context(self) -> str:
        """
        Build a structural constraint block for the chapter writing prompt.
        This tells the writer model what the story is ARGUING, not just what happens.
        """
        parts = [
            "\n[Storyform — Narrative Structural Constraints (NCP)]\n",
        ]

        if self.central_inequity:
            parts.append(f"Central Conflict: {self.central_inequity}")
        if self.thematic_argument:
            parts.append(f"Thematic Argument: {self.thematic_argument}")

        # Dynamics
        d = self.dynamics
        parts.append(f"Structure: {d.resolve}-type protagonist, {d.outcome}/{d.judgement} ending")

        # Throughlines summary
        for name, tl in [
            ("Objective Story", self.objective_story),
            ("Main Character", self.main_character),
            ("Influence Character", self.influence_character),
            ("Relationship Story", self.relationship_story),
        ]:
            if tl.domain:
                parts.append(f"{name} ({tl.perspective}): {tl.domain}")
                if tl.problem:
                    parts.append(f"  Problem: {tl.problem} -> Solution: {tl.solution}")
                if tl.description:
                    parts.append(f"  {tl.description[:120]}")

        # Writing instructions
        parts.append("")
        parts.append("Writing constraints from storyform:")
        parts.append(f"- Do NOT resolve the central conflict prematurely (this is a {d.resolve} story)")
        parts.append(f"- The main character's approach: {d.resolve} under pressure")
        if self.influence_character.domain:
            parts.append(f"- Include the Influence Character's alternative perspective ({self.influence_character.domain})")
        if self.relationship_story.domain:
            parts.append(f"- Advance the relationship arc ({self.relationship_story.domain})")
        parts.append("- Let the structure carry the meaning — don't explain the theme")
        parts.append("")

        return "\n".join(parts)

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ── Quick templates (working examples, not official Dramatica) ──────────────
# [待验证] These are our adaptations of NCP v1.3.0 schema principles applied to
# common web novel genres. Not sourced from official Dramatica storyforms.
# Verified: NCP schema structure (Throughline + StoryDynamics fields).
# Unverified: Specific problem/solution/concern assignments per genre.

STORYFORM_TEMPLATES = {
    "revenge": Storyform(
        title="Revenge Story",
        genre="action",
        central_inequity="An injustice has been done, and the protagonist must decide what justice means",
        thematic_argument="Revenge is a pursuit that changes the pursuer more than the target",
        objective_story=Throughline(domain="Physics", perspective="They",
                                    problem="Pursuit", solution="Avoid",
                                    concern="Obtaining", description="The external quest for revenge"),
        main_character=Throughline(domain="Universe", perspective="I",
                                   problem="Control", solution="Trust",
                                   description="The protagonist's struggle with their own need for control"),
        influence_character=Throughline(domain="Mind", perspective="You",
                                        problem="Avoid", solution="Pursuit",
                                        description="Someone who challenges the protagonist to let go, not chase"),
        dynamics=StoryDynamics(resolve="Change", outcome="Success", judgement="Bad",
                               driver="Decision", limit="Optionlock"),
    ),
    "rise_to_power": Storyform(
        title="Rise to Power",
        genre="xianxia",
        central_inequity="The protagonist starts from nothing in a world where power determines worth",
        thematic_argument="True power comes from mastery of self, not domination of others",
        objective_story=Throughline(domain="Physics", perspective="They",
                                    problem="Pursuit", solution="Avoid",
                                    concern="Obtaining", description="The path to power in a hierarchical world"),
        main_character=Throughline(domain="Universe", perspective="I",
                                   problem="Control", solution="Faith",
                                   description="Learning that external power cannot fill internal void"),
        dynamics=StoryDynamics(resolve="Steadfast", outcome="Success", judgement="Good",
                               driver="Action", limit="Timelock"),
    ),
    "mystery_uncover": Storyform(
        title="Mystery Uncovering",
        genre="mystery",
        central_inequity="A hidden truth distorts the present, and uncovering it changes everything",
        thematic_argument="The truth is never simple, and knowing it carries a cost",
        objective_story=Throughline(domain="Psychology", perspective="They",
                                    problem="Reconsider", solution="Accept",
                                    concern="Becoming", description="The investigation and its revelations"),
        main_character=Throughline(domain="Mind", perspective="I",
                                   problem="Certainty", solution="Doubt",
                                   description="The protagonist's worldview being dismantled"),
        dynamics=StoryDynamics(resolve="Change", outcome="Success", judgement="Bad",
                               driver="Decision", limit="Optionlock"),
    ),
}
