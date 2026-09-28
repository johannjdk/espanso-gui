# Build a portable Windows release on a Windows x64 machine.
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "This script must be run on Windows."
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$packageName = "espanso-gui"
$version = ([regex]::Match(
    (Get-Content (Join-Path $projectRoot "pyproject.toml") -Raw),
    '(?m)^version = "([^"]+)"\r?$'
)).Groups[1].Value

if (-not $version) {
    throw "Could not read the project version from pyproject.toml."
}

$pythonCommand = if (Get-Command python -ErrorAction SilentlyContinue) {
    "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    "py"
} else {
    throw "Python 3.10 or newer is required."
}
$pythonPrefix = if ($pythonCommand -eq "py") { @("-3") } else { @() }

$buildDir = Join-Path $projectRoot "build\windows"
$distDir = Join-Path $projectRoot "dist"
$workDir = Join-Path $buildDir "work"
$specDir = Join-Path $buildDir "spec"
$pyInstallerDist = Join-Path $buildDir "dist"
$iconFile = Join-Path $buildDir "espanso-gui.ico"
$appDir = Join-Path $pyInstallerDist "Espanso GUI"
$archive = Join-Path $distDir "$packageName-$version-windows-x64.zip"

Remove-Item -Recurse -Force $buildDir -ErrorAction SilentlyContinue
Remove-Item -Force $archive -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $workDir, $specDir, $pyInstallerDist, $distDir | Out-Null

# PyInstaller expects an .ico file for a Windows executable. Pillow creates one
# from the project PNG, including the common shell and taskbar sizes.
$iconConverter = @'
from pathlib import Path
from PIL import Image

source, destination = map(Path, __import__("sys").argv[1:])
image = Image.open(source).convert("RGBA")
image.save(destination, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
'@

Write-Host "==> Installing build dependencies" -ForegroundColor Cyan
& $pythonCommand @pythonPrefix -m pip install --upgrade pip
& $pythonCommand @pythonPrefix -m pip install $projectRoot pyinstaller Pillow
& $pythonCommand @pythonPrefix -c $iconConverter `
    (Join-Path $projectRoot "assets\espanso-gui.png") $iconFile

Write-Host "==> Building Espanso GUI for Windows" -ForegroundColor Cyan
& $pythonCommand @pythonPrefix -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "Espanso GUI" `
    --icon $iconFile `
    --add-data "$(Join-Path $projectRoot 'assets');assets" `
    --distpath $pyInstallerDist `
    --workpath $workDir `
    --specpath $specDir `
    (Join-Path $projectRoot "run_editor.py")

if (-not (Test-Path (Join-Path $appDir "Espanso GUI.exe"))) {
    throw "PyInstaller did not produce Espanso GUI.exe."
}

Compress-Archive -Path $appDir -DestinationPath $archive -Force
Write-Host "==> Built $archive" -ForegroundColor Green
