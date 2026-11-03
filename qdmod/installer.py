"""High-level operations: read status, apply a preset, verify what's installed.

Files this tool manages in <game>\\QueensDomain\\Content\\Paks:
  * MOD_PAK_NAME            - the one combined mod pak (with an embedded manifest)
  * MOD_PAK_NAME + ".tmp"   - written first, verified, then atomically renamed
  * LEGACY_PAK_NAMES        - older dev-script paks, always removed on apply
The main game pak is only ever opened read-only.
"""
import datetime
import json
import logging
import os
import time
from dataclasses import dataclass, field

from . import gamedetect, procs
from .errors import GameNotFoundError, GameRunningError, ModError, PatchError, VerifyError
from .pak_reader import PakError, PakFile
from .pak_writer import MOUNT_POINT, write_pak
from .patcher import build_plan
from .presets import PRESETS, Preset, preset_from_manifest
from .verify import MANIFEST_NAME, read_manifest, verify_mod_pak
from .version import APP_NAME, __version__

log = logging.getLogger(__name__)

MOD_PAK_NAME = "QueensDomain-WindowsNoEditor_QDDifficultyMod_P.pak"
TEMP_SUFFIX = ".tmp"
LEGACY_PAK_NAMES = ("QueensDomain-WindowsNoEditor_EasyMode_P.pak",
                    "QueensDomain-WindowsNoEditor_CrateBuff_P.pak")


def _noop(fraction, message):
    pass


@dataclass
class Status:
    game_dir: str
    preset: str = None            # 'normal', 'easy', 'story', 'custom', or None if unknown
    manifest: dict = None
    installed: Preset = None      # the installed Preset (incl. Custom settings), if readable
    legacy_paks: list = field(default_factory=list)
    other_mods: list = field(default_factory=list)
    game_updated: bool = False    # main pak changed since the mod was applied
    problem: str = None           # mod pak present but unreadable, etc.

    def describe(self):
        if self.problem:
            return self.problem
        if self.preset is None and self.legacy_paks:
            return "Older Easy Mode / Crate Buff paks (from the earlier mod scripts)"
        if self.preset == "normal":
            text = "Normal (no difficulty mod installed)"
        elif self.installed is not None:
            text = self.installed.summary()
            applied = (self.manifest or {}).get("applied_at", "")
            if applied:
                text += f" (applied {applied[:16].replace('T', ' ')})"
        else:
            text = "Unknown"
        if self.legacy_paks:
            text += " + older Easy Mode/Crate Buff paks"
        return text


def _check_game_dir(game_dir):
    if not game_dir or not gamedetect.is_game_dir(game_dir):
        raise GameNotFoundError(
            "Queen's Domain wasn't found in that folder. Choose the game's install folder "
            "(the one containing QueensDomain.exe), e.g. ...\\steamapps\\common\\QueensDomain.")


def _check_not_running(game_dir):
    if procs.game_running(game_dir):
        raise GameRunningError("Queen's Domain is running. Please quit the game completely, "
                               "then try again. (The game locks its files while it runs.)")


def _main_fingerprint(main):
    return {"size": main.file_size, "index_sha1": main.index_hash.hex()}


def get_status(game_dir):
    _check_game_dir(game_dir)
    paks = gamedetect.paks_dir(game_dir)
    st = Status(game_dir)
    names = os.listdir(paks)
    st.legacy_paks = [n for n in LEGACY_PAK_NAMES if n in names]
    st.other_mods = sorted(n for n in names if n.lower().endswith(".pak")
                           and n != gamedetect.MAIN_PAK_NAME and n != MOD_PAK_NAME
                           and n not in LEGACY_PAK_NAMES)
    mod_path = os.path.join(paks, MOD_PAK_NAME)
    if not os.path.exists(mod_path):
        st.preset = None if st.legacy_paks else "normal"
        return st
    try:
        with PakFile(mod_path) as pak:
            st.manifest = read_manifest(pak)
        if not st.manifest:
            raise ValueError("no manifest")
        st.preset = st.manifest.get("preset")
        st.installed = preset_from_manifest(st.manifest)
        with PakFile(gamedetect.main_pak_path(game_dir)) as main:
            st.game_updated = st.manifest.get("main_pak") != _main_fingerprint(main)
    except (PakError, OSError, ValueError) as e:
        log.warning("Could not read installed mod pak: %s", e)
        st.problem = "Mod pak found but it can't be read - apply a preset again to repair it."
    return st


def _remove(path):
    if os.path.exists(path):
        try:
            os.remove(path)
        except PermissionError:
            raise GameRunningError(f"Windows wouldn't let the mod remove {os.path.basename(path)}. "
                                   "Make sure the game is fully closed and try again.")
        log.info("Removed %s", path)
        return True
    return False


def apply_preset(game_dir, preset, progress=_noop):
    """Install `preset` (a Preset, or the key of a fixed preset). Returns a result dict (with timing).
    Raises ModError on failure. A Custom preset with every value at default acts like Normal."""
    t0 = time.perf_counter()
    if not isinstance(preset, Preset):
        preset = PRESETS[preset]
    _check_game_dir(game_dir)
    _check_not_running(game_dir)
    paks = gamedetect.paks_dir(game_dir)
    final = os.path.join(paks, MOD_PAK_NAME)
    tmp = final + TEMP_SUFFIX
    log.info("Applying preset %s to %s", preset.key, game_dir)
    _remove(tmp)  # leftover from an interrupted run

    result = {"preset": preset.key, "custom": preset.custom_settings(), "summary": preset.summary(),
              "vanilla": preset.is_vanilla, "game_dir": game_dir}
    if preset.is_vanilla:
        progress(0.5, "Removing mod files")
        removed = [n for n in (MOD_PAK_NAME,) + LEGACY_PAK_NAMES if _remove(os.path.join(paks, n))]
        result.update(removed=removed, seconds=time.perf_counter() - t0)
        progress(1.0, "Done")
        log.info("Normal restored; removed %s", removed or "nothing")
        return result

    try:
        main = PakFile(gamedetect.main_pak_path(game_dir))
    except (PakError, OSError) as e:
        raise PatchError(f"The game's main pak couldn't be read: {e}")
    try:
        plan = build_plan(main, preset, progress)
        manifest = {
            "tool": APP_NAME, "tool_version": __version__, "preset": preset.key,
            "multipliers": preset.multipliers(),
            "custom": preset.custom_settings(),
            "applied_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "main_pak": _main_fingerprint(main),
            "enemy_exports": plan.enemy_exports,
            "breakable_classes": plan.breakable_classes,
            "assets": len(plan.patches),
        }
        files = plan.pak_files(MOUNT_POINT)
        files.append((MANIFEST_NAME, json.dumps(manifest, indent=2).encode("utf-8")))
        progress(0.87, "Writing mod pak")
        try:
            size = write_pak(tmp, files)
        except OSError as e:
            _silent_remove(tmp)
            raise ModError(f"Couldn't write the mod file into the game folder: {e}")
        t_written = time.perf_counter()

        expected = {(p.uexp_path, e.offset) for p in plan.patches for e in p.edits}
        try:
            report = verify_mod_pak(tmp, main, expected,
                                    lambda f, m: progress(0.9 + 0.09 * f, m))
        except Exception:
            _silent_remove(tmp)
            raise
    finally:
        main.close()

    _check_not_running(game_dir)
    try:
        os.replace(tmp, final)
    except OSError as e:
        _silent_remove(tmp)
        raise GameRunningError(f"Couldn't put the mod file in place ({e.strerror}). "
                               "Make sure the game is fully closed and try again.")
    removed = [n for n in LEGACY_PAK_NAMES if _remove(os.path.join(paks, n))]
    t1 = time.perf_counter()
    progress(1.0, "Done")
    result.update(pak=final, size=size, removed=removed, warnings=plan.warnings,
                  enemy_floats=report["enemy_floats"], breakable_floats=report["breakable_floats"],
                  assets=report["assets"], breakable_classes=plan.breakable_classes,
                  seconds=t1 - t0, build_seconds=t_written - t0, verify_seconds=t1 - t_written)
    log.info("Applied %s: %d assets, %d enemy floats, %d breakable floats, %.2fs (verify %.2fs)",
             preset.key, report["assets"], report["enemy_floats"], report["breakable_floats"],
             result["seconds"], result["verify_seconds"])
    return result


def _silent_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def verify_installed(game_dir, progress=_noop):
    """Re-verify the installed mod pak against the game's current files."""
    _check_game_dir(game_dir)
    paks = gamedetect.paks_dir(game_dir)
    final = os.path.join(paks, MOD_PAK_NAME)
    legacy = [n for n in LEGACY_PAK_NAMES if os.path.exists(os.path.join(paks, n))]
    if not os.path.exists(final):
        return {"preset": "normal", "legacy_paks": legacy}
    with PakFile(gamedetect.main_pak_path(game_dir)) as main:
        try:
            with PakFile(final) as pak:
                manifest = read_manifest(pak)
        except (PakError, OSError, ValueError) as e:
            raise VerifyError(f"The installed mod pak can't be read: {e}")
        preset = preset_from_manifest(manifest)
        if preset is None or preset.is_vanilla:
            raise VerifyError("The installed mod pak has no valid manifest.")
        if manifest.get("main_pak") != _main_fingerprint(main):
            raise VerifyError("The game has been updated since the mod was applied. "
                              "Please apply your preset again.")
        plan = build_plan(main, preset, lambda f, m: progress(0.5 * f, m))
        expected = {(p.uexp_path, e.offset) for p in plan.patches for e in p.edits}
        report = verify_mod_pak(final, main, expected, lambda f, m: progress(0.5 + 0.5 * f, m))
    report["legacy_paks"] = legacy
    report["summary"] = preset.summary()
    return report
