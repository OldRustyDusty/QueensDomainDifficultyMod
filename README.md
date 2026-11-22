# Queen's Domain Difficulty Mod

A small Windows tool that adds difficulty settings to **Queen's Domain**: easier presets, or Custom sliders that can make the game easier or harder. Pick one, click **Apply**, and play. Switch back to the normal game at any time.

**[⬇ Download the latest release](https://github.com/OldRustyDusty/QueensDomainDifficultyMod/releases/latest)**: get `QueensDomainDifficultyMod-<version>.zip`, or the standalone `.exe`.

## Presets

| Preset | Enemy damage to you | Enemy health | Crates & barrels |
|---|---|---|---|
| **Normal** | Original | Original | Original (this uninstalls the mod) |
| **Easy** | −30% | ÷1.3 (as if you dealt 30% more damage) | Half the hits to break |
| **Story** | −50% | −50% | A quarter of the hits to break |
| **Custom** | 1%–200% (slider) | set by the *Your damage* slider, 1%–200% | Default, Half or One-third health |

**Custom** has two sliders, *Your damage* and *Enemy damage*, each from 1% to 200% of normal, with a box beside each for exact values. Above 100% makes that side hit harder, so Custom can also make the game harder. *Your damage* is applied as enemy health × 100 / your-damage-%, which takes exactly the same number of hits. The tool remembers your last Custom settings.

The presets cover every enemy that uses the game's enemy stat files, bosses included, and every breakable crate, barrel and sci-fi crate type.

## Requirements

- Windows 10 or 11
- **Queen's Domain** (the full game) on Steam. If the tool can't find your install, point it at the game folder with **Browse...**.

## How to use

1. **Close Queen's Domain completely.** The game locks its files while it runs.
2. Download the [latest release](https://github.com/OldRustyDusty/QueensDomainDifficultyMod/releases/latest), then unzip it anywhere, such as your Desktop. No installer is needed.
3. Run `QueensDomainDifficultyMod.exe`. It finds your Steam install automatically. If it doesn't, click **Browse...** and choose the game folder (in Steam: right-click Queen's Domain → *Manage* → *Browse local files*).
4. Choose **Easy**, **Story** or **Custom**, then click **Apply**. It takes a second or two.
5. Start the game and play. *Currently installed* in the tool always shows what's active.

**To change difficulty**, close the game, pick another option and click **Apply** again.

**To uninstall**, choose **Normal** and click **Restore Normal**. This removes the mod's file and the game is back to the original. You can then delete the exe. Settings and a log are kept in `%APPDATA%\QueensDomainDifficultyMod` if you want to delete those too.

**Upgrading the tool:** just run the new exe. It detects what you have installed.

## After a game update

**Re-apply after every Queen's Domain patch:** close the game, run the tool and click **Apply** again.

The mod is built from your game files *as they were when you clicked Apply*. After a game update, the old mod file still contains pre-update copies of the enemy and crate files. Those copies override the patched versions, so the old mod quietly **undoes parts of the update**, such as rebalanced boss attacks. Re-applying rebuilds the mod from the updated files, so you get the patch's changes with your difficulty settings on top.

The tool detects this for you: when the game has changed since your last apply, it shows a warning (*"The game was updated since this was applied. Click Apply again to refresh the mod."*). Steam's *Verify integrity of game files* doesn't remove the mod, so re-applying (or choosing Normal) is the way to refresh it.

If an update ever changes the game's files so much that the tool can't recognise them, it refuses to apply and changes nothing. Check here for a new version of the tool.

## Compatibility

| Tool | Last tested with |
|---|---|
| 1.1.0 | Queen's Domain version 13571 (Steam build 26663759, the November 14, 2026 update) |

The November 14 update changed attack patterns for 27 bosses and minibosses but not the HP and damage values this mod scales, and the tool needed no changes. If you applied the mod before that update, re-apply it.

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
QueensDomainDifficultyMod.exe --preset custom [--player-damage 1-200] [--enemy-damage 1-200] [--crates default|half|third]
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
