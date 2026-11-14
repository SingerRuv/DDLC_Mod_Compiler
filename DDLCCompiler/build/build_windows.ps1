$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root "dist\windows"
$Work = Join-Path $env:TEMP "ddlc-compiler-windows"
$Ico = Join-Path $Root "DDLC.ico"

Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $Dist, $Work -Force | Out-Null

python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name DDLCCompiler --icon $Ico --add-data "$Ico;." `
    --distpath $Dist --workpath (Join-Path $Work "build") --specpath $Work `
    (Join-Path $Root "DDLCCompiler.py")

Get-Item -LiteralPath (Join-Path $Dist "DDLCCompiler.exe") |
    Select-Object FullName, Length, LastWriteTime
