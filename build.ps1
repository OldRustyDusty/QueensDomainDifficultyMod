# Build QueensDomainDifficultyMod.exe and the Nexus zips.
#   powershell -ExecutionPolicy Bypass -File build.ps1
# Needs the project venv with PyInstaller:  python -m venv .venv ; .venv\Scripts\pip install pyinstaller
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$py = '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw 'Create the venv first: python -m venv .venv; .venv\Scripts\pip install pyinstaller' }
if (-not (Test-Path 'assets\icon.ico')) { & $py tools\make_icon.py }

& $py -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name QueensDomainDifficultyMod `
    --icon "$PSScriptRoot\assets\icon.ico" `
    --add-data "$PSScriptRoot\assets\icon.ico;assets" `
    --version-file "$PSScriptRoot\assets\version_info.txt" `
    --distpath dist --workpath build\pyinstaller --specpath build\pyinstaller `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }


# Nexus packages (zipped with Python so paths use forward slashes for every extractor)
& $py tools\package.py
if ($LASTEXITCODE -ne 0) { throw "Packaging failed ($LASTEXITCODE)" }
Get-FileHash dist\QueensDomainDifficultyMod.exe -Algorithm SHA256 | Select-Object Hash
