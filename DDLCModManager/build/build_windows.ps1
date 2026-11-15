$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root "dist\windows"
$Work = Join-Path $env:TEMP "ddlc-mod-compiler-windows"
$Ico = Join-Path $Root "DDLC.ico"
$Png = Join-Path $Root "icon.png"

Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $Dist, $Work -Force | Out-Null

python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name DDLCModManager --icon $Ico --add-data "$Ico;." --add-data "$Png;." --add-data "$Root/icons;icons" `
    --distpath $Dist --workpath (Join-Path $Work "build") --specpath $Work `
    (Join-Path $Root "DDLCModManager.py")

Get-Item -LiteralPath (Join-Path $Dist "DDLCModManager.exe") |
    Select-Object FullName, Length, LastWriteTime
