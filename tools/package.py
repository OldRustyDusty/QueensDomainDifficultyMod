"""Create the Nexus zips in release/ (run after PyInstaller has built dist/QueensDomainDifficultyMod.exe).

    python tools/package.py
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from qdmod.version import __version__  # noqa: E402

EXE = os.path.join(ROOT, "dist", "QueensDomainDifficultyMod.exe")
SOURCE_FILES = ["main.py", "build.ps1", "README.md", "README.txt", "NEXUS_DESCRIPTION.txt", "LICENSE",
                ".gitignore", "assets/icon.ico", "assets/version_info.txt"]
SOURCE_DIRS = ["qdmod", "tools"]


def write_zip(path, members):
    if os.path.exists(path):
        os.remove(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for arcname, src in members:
            z.write(src, arcname)  # arcname uses forward slashes on every extractor
    print(f"{path}  ({os.path.getsize(path):,} bytes)")


def main():
    if not os.path.isfile(EXE):
        sys.exit(f"missing {EXE} - build it first")
    out = os.path.join(ROOT, "release")
    os.makedirs(out, exist_ok=True)
    write_zip(os.path.join(out, f"QueensDomainDifficultyMod-{__version__}.zip"),
              [("QueensDomainDifficultyMod.exe", EXE), ("README.txt", os.path.join(ROOT, "README.txt")),
               ("LICENSE.txt", os.path.join(ROOT, "LICENSE"))])
    members = [(f, os.path.join(ROOT, *f.split("/"))) for f in SOURCE_FILES]
    for d in SOURCE_DIRS:
        for name in sorted(os.listdir(os.path.join(ROOT, d))):
            if name.endswith(".py"):
                members.append((f"{d}/{name}", os.path.join(ROOT, d, name)))
    write_zip(os.path.join(out, f"QueensDomainDifficultyMod-{__version__}-source.zip"), members)


if __name__ == "__main__":
    main()
