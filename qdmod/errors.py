"""User-facing error types. `str(err)` is always a message a player can understand."""


class ModError(Exception):
    exit_code = 1


class GameNotFoundError(ModError):
    exit_code = 3


class GameRunningError(ModError):
    exit_code = 4


class PatchError(ModError):
    """The game's files don't look the way the mod expects (e.g. after a game update)."""
    exit_code = 5


class VerifyError(ModError):
    exit_code = 6
