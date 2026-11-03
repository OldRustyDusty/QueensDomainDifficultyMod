# Queen's Domain Difficulty Mod

A small Windows tool that adds difficulty presets to **Queen's Domain**. Pick a preset, click **Apply**, and play. Switch back to the normal game at any time.

**[⬇ Download the latest release](https://github.com/OldRustyDusty/QueensDomainDifficultyMod/releases/latest)**: get `QueensDomainDifficultyMod-<version>.zip`, or the standalone `.exe`.

## Presets

| Preset | Enemy damage to you | Enemy health | Crates & barrels |
|---|---|---|---|
| **Normal** | Original | Original | Original (this uninstalls the mod) |
| **Easy** | −30% | ÷1.3 (as if you dealt 30% more damage) | Half the hits to break |
| **Story** | −50% | −50% | A quarter of the hits to break |

The presets cover every enemy that uses the game's enemy stat files, bosses included, and every breakable crate, barrel and sci-fi crate type.

## How to use

1. **Close Queen's Domain.** The game locks its files while it runs.
2. Run `QueensDomainDifficultyMod.exe` from anywhere. It finds your Steam install automatically. If it doesn't, use **Browse...**.
3. Choose a preset and click **Apply**. The tool shows which preset is currently installed.

To uninstall, choose **Normal**. After a game update, run the tool and click **Apply** again. It warns you when the game has changed since your last apply.

## How it works

- The mod is **built from your own game files** when you click Apply. No game assets are included in this repository or in the releases.
- The game's original pak is only read, never modified. The tool adds one file to `<game>\QueensDomain\Content\Paks`: `QueensDomain-WindowsNoEditor_QDDifficultyMod_P.pak`. Unreal Engine loads `_P` paks with higher priority than the main game pak.
- The tool scales the `HP` and `BaseDamage` values in every `EnemyData` asset, and the `HP` of every class derived from `Permabreakable_base` (the crates and barrels). Each edit replaces a single float in place without changing its size.
- Every pak it writes is read back and verified: pak structure, SHA1 checksums, every changed value equal to original × multiplier, and nothing else changed. If any check fails, nothing is installed.
- It refuses to apply while the game is running.

Settings and a log live in `%APPDATA%\QueensDomainDifficultyMod`.

## Command line

```
QueensDomainDifficultyMod.exe --preset normal|easy|story [--game-dir PATH]
QueensDomainDifficultyMod.exe --status [--json] [--game-dir PATH]
QueensDomainDifficultyMod.exe --verify [--game-dir PATH]
```

Exit codes: 0 OK, 2 bad arguments, 3 game not found, 4 game running or files locked, 5 game files not as expected, 6 verification failed, 1 other error. The exe is a windowed program, so use `start /wait` (cmd) or `Start-Process -Wait` (PowerShell) to get the exit code.

## Building from source

Requires Python 3.12 or newer. The tool itself uses only the standard library.

```powershell
python main.py                      # run the GUI from source
python -m venv .venv
.venv\Scripts\pip install pyinstaller
powershell -ExecutionPolicy Bypass -File build.ps1   # builds dist\ and release\ zips
```

## Antivirus / SmartScreen

The exe isn't code-signed and is packaged with PyInstaller, which sometimes triggers false positives. On SmartScreen, click *More info → Run anyway*. You can also run it from source as shown above.

## License

[GPL-3.0](LICENSE). This is a fan-made mod and is not affiliated with the developers of Queen's Domain.
