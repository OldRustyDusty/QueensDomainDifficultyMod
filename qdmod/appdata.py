"""Per-user settings and the log file, both under %APPDATA%\\QueensDomainDifficultyMod."""
import json
import logging
import logging.handlers
import os

from .version import APP_NAME, __version__

APP_FOLDER = "QueensDomainDifficultyMod"


def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_FOLDER)
    os.makedirs(path, exist_ok=True)
    return path


def log_path():
    return os.path.join(data_dir(), "QueensDomainDifficultyMod.log")


def _settings_path():
    return os.path.join(data_dir(), "settings.json")


def load_settings():
    try:
        with open(_settings_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(**changes):
    data = load_settings()
    data.update(changes)
    tmp = _settings_path() + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, _settings_path())
    except OSError:
        logging.getLogger(__name__).warning("Could not save settings", exc_info=True)


def setup_logging(verbose_console=False):
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    try:
        fh = logging.handlers.RotatingFileHandler(log_path(), maxBytes=512 * 1024, backupCount=2,
                                                  encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        root.addHandler(fh)
    except OSError:
        pass  # a missing log file must never stop the tool
    if verbose_console:
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(message)s"))
        sh.setLevel(logging.WARNING)
        root.addHandler(sh)
    logging.getLogger(__name__).info("---- %s %s started", APP_NAME, __version__)
