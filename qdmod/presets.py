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
    settings: tuple = None      # Custom only: (player_damage %, enemy_damage %, crates key)

    @property
    def is_vanilla(self):
        return self.enemy_damage == self.enemy_hp == self.breakable_hp == 1.0

    def multipliers(self):
        return {"enemy_damage": self.enemy_damage, "enemy_hp": self.enemy_hp,
                "breakable_hp": self.breakable_hp}

    def custom_settings(self):
        """Custom settings as a JSON-friendly dict (None for the fixed presets)."""
        if self.settings is None:
            return None
        player, enemy, crates = self.settings
        return {"player_damage": player, "enemy_damage": enemy, "crates": crates}

    def summary(self):
        """One-line description of what's installed, e.g. for the status line."""
        if self.settings is None:
            return self.title
        player, enemy, crates = self.settings
        return (f"Custom (your damage {player}%, enemy damage {enemy}%, "
                f"crates: {CRATE_OPTIONS[crates][0].lower()})")


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

# ---- Custom ------------------------------------------------------------------
CUSTOM_KEY = "custom"
PERCENT_MIN, PERCENT_MAX = 1, 200
# key -> (label, breakable HP multiplier)
CRATE_OPTIONS = {
    "default": ("Default", 1.0),
    "half": ("Half", 0.5),
    "third": ("One-third", 1 / 3),
}
CUSTOM_TAGLINE = "Set your own damage, from 1% to 200%. Above 100% makes that side hit harder."


def custom_preset(player_damage=100, enemy_damage=100, crates="default"):
    """Build the Custom preset.

    player_damage: % of normal damage you deal. Applied as enemy HP x 100/player_damage,
                   which takes exactly the same number of hits as scaling your damage.
    enemy_damage:  % of normal damage enemies deal (enemy BaseDamage x enemy_damage/100).
    crates:        key of CRATE_OPTIONS (crate/barrel HP multiplier).
    """
    player_damage, enemy_damage = int(player_damage), int(enemy_damage)
    for name, value in (("player damage", player_damage), ("enemy damage", enemy_damage)):
        if not PERCENT_MIN <= value <= PERCENT_MAX:
            raise ValueError(f"{name} must be between {PERCENT_MIN}% and {PERCENT_MAX}% (got {value}%)")
    if crates not in CRATE_OPTIONS:
        raise ValueError(f"crates must be one of {', '.join(CRATE_OPTIONS)} (got {crates!r})")
    return Preset(
        key=CUSTOM_KEY,
        title="Custom",
        tagline=CUSTOM_TAGLINE,
        enemy_damage=enemy_damage / 100,
        enemy_hp=100 / player_damage,
        breakable_hp=CRATE_OPTIONS[crates][1],
        settings=(player_damage, enemy_damage, crates),
    )


def preset_from_manifest(manifest):
    """The Preset an installed mod pak was built with, or None if the manifest isn't usable."""
    key = (manifest or {}).get("preset")
    if key in PRESETS:
        return PRESETS[key]
    if key == CUSTOM_KEY:
        s = manifest.get("custom") or {}
        try:
            return custom_preset(s["player_damage"], s["enemy_damage"], s["crates"])
        except (KeyError, TypeError, ValueError):
            return None
    return None
