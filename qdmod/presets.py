"""Difficulty presets: the exact multipliers and how they're described to players."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Preset:
    key: str
    title: str
    tagline: str
    details: tuple = field(default_factory=tuple)
    enemy_damage: float = 1.0   # x BaseDamage on every EnemyData asset
    enemy_hp: float = 1.0       # x HP on every EnemyData asset
    breakable_hp: float = 1.0   # x HP on every Permabreakable (crate/barrel) class

    @property
    def is_vanilla(self):
        return self.enemy_damage == self.enemy_hp == self.breakable_hp == 1.0

    def multipliers(self):
        return {"enemy_damage": self.enemy_damage, "enemy_hp": self.enemy_hp,
                "breakable_hp": self.breakable_hp}


NORMAL = Preset(
    key="normal",
    title="Normal",
    tagline="The game exactly as the developers made it.",
    details=("Removes this mod completely (this is also how you uninstall).",),
)

EASY = Preset(
    key="easy",
    title="Easy",
    tagline="A gentler fight that still asks something of you.",
    details=(
        "Enemies deal 30% less damage to you.",
        "Enemies have less health, as if you dealt 30% more damage.",
        "Crates and barrels break in about half the hits.",
    ),
    enemy_damage=0.7,
    enemy_hp=1 / 1.3,
    breakable_hp=0.5,
)

STORY = Preset(
    key="story",
    title="Story",
    tagline="For enjoying the world and story with little resistance.",
    details=(
        "Enemies deal half damage to you.",
        "Enemies have half health, so they go down in half the hits.",
        "Crates and barrels break in about a quarter of the hits.",
    ),
    enemy_damage=0.5,
    enemy_hp=0.5,
    breakable_hp=0.25,
)

PRESETS = {p.key: p for p in (NORMAL, EASY, STORY)}
