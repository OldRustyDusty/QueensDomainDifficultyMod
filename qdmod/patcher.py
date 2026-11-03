"""Work out the patched asset bytes for a preset, from the player's own main pak.

One pass over every .uasset under /QueensDomain/Content/ collects:
  * packages that mention EnemyData_C (enemy stat assets: HP, BaseDamage), and
  * every Blueprint class and its parent, so the crate/barrel family can be found
    by inheritance from Permabreakable_base_C (HP on each class default object).

All edits are same-size float overwrites in the .uexp; the .uasset is unchanged.
"""
import logging
import struct
from dataclasses import dataclass, field

from .binio import f32
from .errors import PatchError
from .uasset import AssetError, Package

log = logging.getLogger(__name__)

CONTENT_DIR = "/QueensDomain/Content/"
ENEMY_CLASS = "EnemyData_C"
ENEMY_PROPS = (("HP", "enemy_hp"), ("BaseDamage", "enemy_damage"))
BREAKABLE_BASE = "Permabreakable_base_C"
BREAKABLE_PROP = "HP"
BGC = "BlueprintGeneratedClass"


@dataclass
class FloatEdit:
    export: str
    prop: str
    offset: int
    old: float
    new: float
    multiplier: float
    category: str  # 'enemy' or 'breakable'


@dataclass
class AssetPatch:
    uasset_path: str  # full pak path including mount point
    uasset: bytes
    uexp: bytearray
    edits: list = field(default_factory=list)

    @property
    def uexp_path(self):
        return self.uasset_path[:-len(".uasset")] + ".uexp"

    def set_float(self, export, prop, offset, multiplier, category):
        if any(e.offset == offset for e in self.edits):
            raise PatchError(f"internal error: {self.uasset_path} {export}.{prop} would be scaled twice")
        old = struct.unpack_from("<f", self.uexp, offset)[0]
        self.uexp[offset:offset + 4] = f32(old * multiplier)
        new = struct.unpack_from("<f", self.uexp, offset)[0]
        self.edits.append(FloatEdit(export, prop, offset, old, new, multiplier, category))


@dataclass
class PatchPlan:
    patches: list
    enemy_exports: int
    breakable_classes: list
    warnings: list

    def edits(self, category=None):
        return [e for p in self.patches for e in p.edits if category in (None, e.category)]

    def pak_files(self, mount):
        """[(path relative to mount, bytes)] for the pak writer, in a stable order."""
        out = []
        for p in sorted(self.patches, key=lambda p: p.uasset_path):
            out.append((p.uasset_path[len(mount):], bytes(p.uasset)))
            out.append((p.uexp_path[len(mount):], bytes(p.uexp)))
        return out


def _noop(fraction, message):
    pass


def build_plan(pak, preset, progress=_noop):
    """Return a PatchPlan for `preset` using the opened main PakFile `pak`."""
    mult = preset.multipliers()
    candidates = sorted((e for path, e in pak.entries.items()
                         if path.endswith(".uasset") and CONTENT_DIR in path),
                        key=lambda e: e.offset)  # read in file order: much faster on HDDs
    if not candidates:
        raise PatchError("No game assets were found in the main pak. Is this really Queen's Domain?")

    warnings = []
    enemy_files = {}   # path -> uasset bytes
    parent, where = {}, {}  # BP class -> parent class name / defining package path
    total = len(candidates)
    for i, entry in enumerate(candidates):
        if i % 500 == 0:
            progress(0.8 * i / total, f"Scanning game files ({i:,} of {total:,})")
        ua = pak.read(entry)
        is_enemy = ENEMY_CLASS.encode() in ua
        is_bp = BGC.encode() in ua
        if not (is_enemy or is_bp):
            continue
        if is_enemy:
            enemy_files[entry.path] = ua
        if is_bp:
            try:
                pkg = Package(ua)
            except (AssetError, ValueError, IndexError) as e:
                warnings.append(f"Skipped unreadable asset {entry.path}: {e}")
                continue
            for x in pkg.exports:
                if pkg.class_name(x) == BGC:
                    parent[x.name] = pkg.ref_name(x.super_index)[1]
                    where[x.name] = entry.path
    progress(0.8, "Preparing changes")

    patches = {}

    def patch_for(path, ua):
        if path not in patches:
            uexp_path = path[:-len(".uasset")] + ".uexp"
            if uexp_path not in pak.entries:
                raise KeyError(uexp_path)
            patches[path] = AssetPatch(path, ua, bytearray(pak.read(uexp_path)))
        return patches[path]

    # --- enemies -----------------------------------------------------------
    enemy_exports = 0
    for path in sorted(enemy_files):
        ua = enemy_files[path]
        try:
            pkg = Package(ua)
            targets = [x for x in pkg.exports
                       if pkg.ref_name(x.class_index) == ("import", ENEMY_CLASS)
                       or x.name == "Default__" + ENEMY_CLASS]
            if not targets:
                continue
            patch = patch_for(path, ua)
            pkg.uexp = patch.uexp
            for x in targets:
                floats = pkg.top_floats(x)
                touched = False
                for prop, key in ENEMY_PROPS:
                    if prop in floats and mult[key] != 1.0:
                        patch.set_float(x.name, prop, floats[prop], mult[key], "enemy")
                        touched = True
                enemy_exports += touched
            if not patch.edits:
                del patches[path]
        except (AssetError, ValueError, IndexError, KeyError, struct.error) as e:
            patches.pop(path, None)
            warnings.append(f"Skipped enemy asset {path}: {e}")
    if enemy_exports == 0 and (mult["enemy_hp"] != 1.0 or mult["enemy_damage"] != 1.0):
        raise PatchError("No enemy stat assets (EnemyData) were found in the game files. "
                         "The game may have been updated in a way this version of the mod "
                         "doesn't understand yet - please check the mod page for an update.")

    # --- breakables --------------------------------------------------------
    breakable_classes = []
    if mult["breakable_hp"] != 1.0:
        if BREAKABLE_BASE not in where:
            raise PatchError("The crate/barrel base class (Permabreakable_base) was not found in the "
                             "game files. The game may have been updated - please check the mod page "
                             "for an update.")

        def is_breakable(cls):
            seen = set()
            while cls != BREAKABLE_BASE and cls in parent and cls not in seen:
                seen.add(cls)
                cls = parent[cls]
            return cls == BREAKABLE_BASE

        for cls in sorted(c for c in where if is_breakable(c)):
            path = where[cls]
            try:
                ua = pak.read(path)
                patch = patch_for(path, ua)
                pkg = Package(ua, patch.uexp)
                off = pkg.top_floats("Default__" + cls).get(BREAKABLE_PROP)
                if off is None:
                    # No own HP value: it inherits from its parent, which is scaled itself.
                    if not patch.edits:
                        del patches[path]
                    continue
                patch.set_float("Default__" + cls, BREAKABLE_PROP, off, mult["breakable_hp"], "breakable")
                breakable_classes.append(cls)
            except (AssetError, ValueError, IndexError, KeyError, struct.error) as e:
                warnings.append(f"Skipped breakable class {cls} ({path}): {e}")
        if not breakable_classes:
            raise PatchError("No crates or barrels could be adjusted. The game may have been updated - "
                             "please check the mod page for an update.")

    for w in warnings:
        log.warning(w)
    progress(0.85, "Changes prepared")
    return PatchPlan([p for p in patches.values() if p.edits], enemy_exports, breakable_classes, warnings)
