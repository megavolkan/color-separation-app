# Ayrim'in Windows paketini üretir: dist\Ayrim\Ayrim.exe ve dist\Ayrim-windows-x64.zip
# Kullanım (proje klasöründe, PowerShell):  .\packaging\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv bulunamadı. Kurulum: winget install --id=astral-sh.uv -e"
}
$gs = Get-ChildItem "C:\Program Files\gs\gs*\bin\gswin64c.exe" -ErrorAction SilentlyContinue
if (-not $gs) {
    Write-Warning "Ghostscript yok. Uygulama çalışmak için ister: https://ghostscript.com/releases/gsdnld.html"
}

uv sync --group build

Write-Host "Simge hazırlanıyor..."
New-Item -ItemType Directory -Force -Path build | Out-Null
uv run python packaging/make_icon.py build/icon.png build/Ayrim.ico

Write-Host "Uygulama paketleniyor..."
uv run pyinstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller packaging/Ayrim.spec

$zip = "dist\Ayrim-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path dist\Ayrim -DestinationPath $zip
Write-Host "Hazır: dist\Ayrim\Ayrim.exe ve $zip"
