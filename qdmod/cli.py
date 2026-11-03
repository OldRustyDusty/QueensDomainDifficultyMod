"""Command-line mode (for testing/automation). Runs when any arguments are given.

    QueensDomainDifficultyMod.exe --preset easy [--game-dir PATH]
    QueensDomainDifficultyMod.exe --preset custom --player-damage 150 --enemy-damage 80 --crates half
    QueensDomainDifficultyMod.exe --status [--game-dir PATH]
    QueensDomainDifficultyMod.exe --verify [--game-dir PATH]

Exit codes: 0 ok, 1 unexpected error, 2 bad arguments, 3 game not found,
4 game running / files locked, 5 game files not as expected, 6 verification failed.
"""
import argparse
import json
import logging
import sys

from . import appdata, gamedetect, installer
from .errors import GameNotFoundError, ModError
from .presets import CRATE_OPTIONS, CUSTOM_KEY, PERCENT_MAX, PERCENT_MIN, PRESETS, custom_preset
from .version import APP_NAME, __version__

log = logging.getLogger(__name__)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"error: {message}", file=sys.stderr)
        log.error("Bad arguments: %s", message)
        raise SystemExit(2)


def _parser():
    p = _Parser(prog="QueensDomainDifficultyMod", description=f"{APP_NAME} {__version__}",
                epilog="Without arguments the graphical window opens. "
                       f"A log is written to {appdata.log_path()}")
    p.add_argument("--game-dir", metavar="PATH", help="Queen's Domain install folder (auto-detected if omitted)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--preset", choices=sorted(PRESETS) + [CUSTOM_KEY], help="apply a preset (normal = uninstall)")
    g.add_argument("--status", action="store_true", help="show what is currently installed")
    g.add_argument("--verify", action="store_true", help="re-check the installed mod pak")
    c = p.add_argument_group("custom preset options (only with --preset custom)")
    c.add_argument("--player-damage", type=int, metavar="PCT",
                   help=f"damage you deal, {PERCENT_MIN}-{PERCENT_MAX} (default 100)")
    c.add_argument("--enemy-damage", type=int, metavar="PCT",
                   help=f"damage enemies deal, {PERCENT_MIN}-{PERCENT_MAX} (default 100)")
    c.add_argument("--crates", choices=list(CRATE_OPTIONS),
                   help="crate/barrel HP: default, half or third (default: default)")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.add_argument("--version", action="version", version=__version__)
    return p


def _out(text):
    log.info("%s", text)
    print(text, flush=True)


def _preset_from_args(parser, args):
    custom_opts = (args.player_damage, args.enemy_damage, args.crates)
    if args.preset != CUSTOM_KEY:
        if any(v is not None for v in custom_opts):
            parser.error("--player-damage, --enemy-damage and --crates need --preset custom")
        return PRESETS[args.preset]
    try:
        return custom_preset(100 if args.player_damage is None else args.player_damage,
                             100 if args.enemy_damage is None else args.enemy_damage,
                             args.crates or "default")
    except ValueError as e:
        parser.error(str(e))


def run(argv):
    parser = _parser()
    args = parser.parse_args(argv)
    preset = _preset_from_args(parser, args) if args.preset else None
    try:
        if args.game_dir:
            game_dir = gamedetect.normalize_game_dir(args.game_dir)
            if not game_dir:
                raise GameNotFoundError(f"Queen's Domain was not found at {args.game_dir}")
            how = "--game-dir"
        else:
            game_dir, how = gamedetect.auto_detect(appdata.load_settings().get("game_dir"))
            if not game_dir:
                raise GameNotFoundError("Queen's Domain could not be found automatically; pass --game-dir PATH")
        log.info("Game folder: %s (%s)", game_dir, how)

        if args.status:
            st = installer.get_status(game_dir)
            data = {"game_dir": game_dir, "found_by": how, "preset": st.preset, "status": st.describe(),
                    "legacy_paks": st.legacy_paks, "other_mods": st.other_mods,
                    "game_updated_since_apply": st.game_updated, "manifest": st.manifest}
            if args.json:
                _out(json.dumps(data, indent=2))
            else:
                _out(f"Game folder: {game_dir} ({how})\nInstalled:   {st.describe()}")
                if st.game_updated:
                    _out("Note: the game was updated since this was applied - apply it again.")
                if st.other_mods:
                    _out("Other mod paks (left alone): " + ", ".join(st.other_mods))
            return 0

        if args.verify:
            rep = installer.verify_installed(game_dir)
            if args.json:
                rep.pop("samples", None)
                _out(json.dumps(rep, indent=2))
            elif rep["preset"] == "normal":
                _out("No difficulty mod installed (Normal)."
                     + (f" Legacy paks present: {', '.join(rep['legacy_paks'])}" if rep["legacy_paks"] else ""))
            else:
                _out(f"OK: {rep['summary']} verified - {rep['assets']} assets, "
                     f"{rep['enemy_floats']} enemy values, {rep['breakable_floats']} crate/barrel values.")
            return 0

        res = installer.apply_preset(game_dir, preset)
        if args.json:
            _out(json.dumps(res, indent=2))
        elif preset.is_vanilla:
            _out(f"Normal restored in {res['seconds']:.1f}s. Removed: {', '.join(res['removed']) or 'nothing'}")
        else:
            _out(f"{preset.summary()} applied and verified in {res['seconds']:.1f}s: "
                 f"{res['assets']} assets, {res['enemy_floats']} enemy values, "
                 f"{res['breakable_floats']} crate/barrel values -> {res['pak']}")
            if res["removed"]:
                _out("Removed old paks: " + ", ".join(res["removed"]))
        return 0
    except ModError as e:
        log.error("%s", e)
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        return e.exit_code
    except Exception:
        log.exception("Unexpected error")
        print(f"ERROR: unexpected problem - see {appdata.log_path()}", file=sys.stderr, flush=True)
        return 1
