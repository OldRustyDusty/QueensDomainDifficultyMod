QUEEN'S DOMAIN DIFFICULTY MOD  -  version 1.1.0
================================================

Adds difficulty settings to Queen's Domain: easier presets, or Custom
sliders that can make it easier or harder. Pick one in a simple window and
click Apply. You can switch back to the normal game at any time.

The mod builds its file from YOUR OWN copy of the game when you click Apply,
so it never ships any game files and never changes the original game files.


PRESETS
-------
  Normal  The game exactly as the developers made it. Choosing this
          uninstalls the mod.

  Easy    Enemies deal 30% less damage to you.
          Enemies have less health, as if you dealt 30% more damage.
          Crates and barrels break in about half the hits.

  Story   Enemies deal half damage to you.
          Enemies have half health, so they go down in half the hits.
          Crates and barrels break in about a quarter of the hits.

  Custom  Set it yourself with two sliders (or type an exact number):
            Your damage    1% to 200% of normal
            Enemy damage   1% to 200% of normal
          plus crates and barrels: Default, Half or One-third of their health.
          Going above 100% makes that side hit harder, so Custom can also
          make the game HARDER - e.g. your damage 70% and enemy damage 150%.
          The tool remembers your last Custom settings.
          (Your damage works by changing enemy health: 150% damage gives
          enemies 1/1.5 of their health, which takes exactly the same number
          of hits.)

The changes cover every enemy that uses the game's enemy stat files,
including bosses, and every breakable crate, barrel and sci-fi crate type.


INSTALL AND USE
---------------
1. Close Queen's Domain completely. The game locks its files while it runs,
   so the mod can't change anything until the game is closed.
2. Unzip QueensDomainDifficultyMod.exe anywhere you like, such as your
   Desktop. No installer is needed.
3. Double-click QueensDomainDifficultyMod.exe.
4. Check that the "Game folder" shows your Queen's Domain install. The mod
   finds Steam installs automatically. If it doesn't, click Browse... and
   pick the game folder. To find it in Steam, right-click Queen's Domain,
   then Manage > Browse local files.
5. Choose Easy, Story or Custom and click Apply. It takes a second or two.
6. Start the game and play.

"Currently installed" always shows which preset is active.


UNINSTALL
---------
Open the tool, choose Normal and click "Restore Normal". The mod's file is
removed and the game is back to the original. You can then delete the exe.

The tool keeps its settings and a log in %APPDATA%\QueensDomainDifficultyMod.
You can delete that folder too if you want to remove every trace.


AFTER A GAME UPDATE
-------------------
When Queen's Domain gets a patch, open the tool and click Apply again so the
mod is rebuilt from the updated game files. If the game was updated since
you applied, the tool shows a warning telling you to do this.

If a big update changes the game's files too much, the tool refuses to
apply and asks you to check the mod page for a new version. Nothing is
changed in that case.


TROUBLESHOOTING
---------------
* "Windows protected your PC" (SmartScreen): this tool is a small free
  program without a paid code-signing certificate. Click "More info", then
  "Run anyway". The source code is available on the mod page.
* An antivirus flags the exe: this is a known false positive for programs
  packaged with PyInstaller (a common Python packaging tool). You can check
  the source code, or add an exception for the file.
* "Queen's Domain is running": quit the game fully, including the launcher,
  and try again.
* The game folder isn't found: use Browse... and pick the folder that
  contains QueensDomain.exe.
* Something else went wrong: click "Open log folder" in the tool and include
  QueensDomainDifficultyMod.log when you report the problem.
* Steam's "Verify integrity of game files" does not remove this mod. Use
  Normal to remove it.


WHAT IT CHANGES ON DISK
-----------------------
Only one file is added, in <game folder>\QueensDomain\Content\Paks:

    QueensDomain-WindowsNoEditor_QDDifficultyMod_P.pak

The game's own QueensDomain-WindowsNoEditor.pak is only read, never
modified. Every time the mod file is written, the tool reads it back and
checks it: file structure, checksums, and that every changed value equals
the original value times the preset's multiplier, with nothing else
changed. If any check fails, the file is deleted and you get an error.

Applying any preset (including Normal) also removes the older
"..._EasyMode_P.pak" and "..._CrateBuff_P.pak" files from earlier
script versions of this mod, if you have them. Any other mods in the Paks
folder are left alone. If another mod changes the same enemy stats,
whichever mod loads last wins.


COMMAND LINE (OPTIONAL)
-----------------------
    QueensDomainDifficultyMod.exe --preset normal|easy|story [--game-dir PATH]
    QueensDomainDifficultyMod.exe --preset custom --player-damage 150
                                  --enemy-damage 80 --crates half|third|default
    QueensDomainDifficultyMod.exe --status [--json] [--game-dir PATH]
    QueensDomainDifficultyMod.exe --verify [--game-dir PATH]

The exe is a windowed program, so use "start /wait" in cmd, or
"Start-Process -Wait" in PowerShell, to wait for it and get its exit code:
0 = OK, 2 = bad arguments, 3 = game not found, 4 = game running or files
locked, 5 = game files not as expected, 6 = verification failed,
1 = other error. Everything is also written to the log file.


BUILDING FROM SOURCE
--------------------
The source zip contains the Python code, which uses only the standard
library. To run it: python main.py. To build the exe with PyInstaller, run
build.ps1, which expects a .venv with PyInstaller installed.


This is a fan-made mod and is not affiliated with the developers of
Queen's Domain.
