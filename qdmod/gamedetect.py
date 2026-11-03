"""Find the Queen's Domain install folder.

Order: a folder the EXE sits in (or below), the last folder the player chose,
then Steam (registry -> libraryfolders.vdf -> appmanifest_1799840.acf).
"""
import logging
import os
import re
import sys

log = logging.getLogger(__name__)

APP_ID = "1799840"
DEFAULT_INSTALLDIR = "QueensDomain"
MAIN_PAK_NAME = "QueensDomain-WindowsNoEditor.pak"
PAKS_REL = os.path.join("QueensDomain", "Content", "Paks")


def paks_dir(game_dir):
    return os.path.join(game_dir, PAKS_REL)


def main_pak_path(game_dir):
    return os.path.join(paks_dir(game_dir), MAIN_PAK_NAME)


def is_game_dir(path):
    return bool(path) and os.path.isfile(main_pak_path(path))


def normalize_game_dir(path, max_up=6):
    """Accept the game folder or anything inside it (Paks folder, an exe...). Return the root or None."""
    if not path:
        return None
    p = os.path.abspath(os.path.expandvars(os.path.expanduser(path.strip().strip('"'))))
    if os.path.isfile(p):
        p = os.path.dirname(p)
    for _ in range(max_up + 1):
        # Also accept a parent folder that directly contains the game, e.g. ...\steamapps\common
        for candidate in (p, os.path.join(p, DEFAULT_INSTALLDIR)):
            if is_game_dir(candidate):
                try:
                    return os.path.realpath(candidate)  # also restores the folder names' real casing
                except OSError:
                    return candidate
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return None


# --------------------------------------------------------------------- Steam
def _registry_steam_paths():
    paths = []
    try:
        import winreg
    except ImportError:
        return paths
    keys = ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"))
    for hive, sub, value in keys:
        try:
            with winreg.OpenKey(hive, sub) as k:
                v, _ = winreg.QueryValueEx(k, value)
                if v:
                    paths.append(os.path.normpath(v))
        except OSError:
            pass
    return paths


def _vdf_values(text, key):
    """All "key" "value" pairs from a Valve KeyValues text file (values unescaped)."""
    out = []
    for m in re.finditer(r'"%s"\s+"((?:[^"\\]|\\.)*)"' % re.escape(key), text, re.IGNORECASE):
        out.append(m.group(1).replace("\\\\", "\\").replace('\\"', '"'))
    return out


def _read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def steam_libraries():
    roots = _registry_steam_paths()
    pf86 = os.environ.get("ProgramFiles(x86)")
    if pf86:
        roots.append(os.path.join(pf86, "Steam"))
    libs, seen = [], set()
    for root in roots:
        for lib in [root] + _vdf_values(_read_text(os.path.join(root, "steamapps", "libraryfolders.vdf")) or "", "path"):
            lib = os.path.normpath(lib)
            key = os.path.normcase(lib)
            if key not in seen and os.path.isdir(lib):
                seen.add(key)
                libs.append(lib)
    return libs


def find_via_steam():
    for lib in steam_libraries():
        acf = _read_text(os.path.join(lib, "steamapps", f"appmanifest_{APP_ID}.acf"))
        if acf is None:
            continue
        names = _vdf_values(acf, "installdir") or [DEFAULT_INSTALLDIR]
        game = os.path.join(lib, "steamapps", "common", names[0])
        log.info("Steam manifest for app %s found in %s -> %s", APP_ID, lib, game)
        if is_game_dir(game):
            return normalize_game_dir(game)
    return None


def app_dir():
    """Folder containing the running EXE (or main.py when run from source)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(sys.argv[0] or __file__))


def find_near_exe():
    return normalize_game_dir(app_dir())


def auto_detect(remembered=None):
    """Return (game_dir, how_found) or (None, None)."""
    for how, finder in (("next to this program", find_near_exe),
                        ("last used folder", lambda: normalize_game_dir(remembered)),
                        ("Steam library", find_via_steam)):
        try:
            found = finder()
        except Exception:  # detection must never crash the tool
            log.exception("Game detection step '%s' failed", how)
            found = None
        if found:
            return found, how
    return None, None
