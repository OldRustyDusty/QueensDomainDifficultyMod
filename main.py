"""Entry point: no arguments -> GUI window; any arguments -> command-line mode."""
import os
import sys


def _attach_console():
    """A windowed EXE has no console. Borrow the parent's (if any) so CLI output is visible."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    stream = None
    try:
        import ctypes
        if ctypes.windll.kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
            stream = open("CONOUT$", "w", encoding="utf-8", buffering=1)
    except Exception:
        stream = None
    if stream is None:
        stream = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = sys.stdout or stream
    sys.stderr = sys.stderr or stream


def main():
    from qdmod import appdata
    if len(sys.argv) > 1:
        _attach_console()
        appdata.setup_logging()
        from qdmod import cli
        return cli.run(sys.argv[1:])
    appdata.setup_logging()
    from qdmod import gui
    return gui.run()


if __name__ == "__main__":
    sys.exit(main())
