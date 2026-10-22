#!/bin/bash
# Ayrim.app paketini üretir ve Uygulamalar klasörüne kopyalar.
# Kullanım: ./packaging/build_mac.sh   (proje klasöründe, bir kez)
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null; then
    echo "uv bulunamadı. Kurulum: brew install uv"; exit 1
fi
if ! command -v gs >/dev/null && [ ! -x /opt/homebrew/bin/gs ]; then
    echo "Uyarı: Ghostscript yok. Uygulama çalışmak için ister: brew install ghostscript"
fi

uv sync --group build

echo "Simge hazırlanıyor…"
mkdir -p build/Ayrim.iconset
uv run python packaging/make_icon.py build/icon.png
for s in 16 32 128 256 512; do
    sips -z $s $s build/icon.png --out "build/Ayrim.iconset/icon_${s}x${s}.png" >/dev/null
    sips -z $((s * 2)) $((s * 2)) build/icon.png --out "build/Ayrim.iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns build/Ayrim.iconset -o build/Ayrim.icns

echo "Uygulama paketleniyor…"
uv run pyinstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller packaging/Ayrim.spec

# İmzasız yerel paket: Gatekeeper karantina işaretini kaldır, yerel imza at.
xattr -cr dist/Ayrim.app
codesign --force --deep --sign - dist/Ayrim.app

# CI'da (GitHub Actions) kurulum yapılmaz, yalnızca zip üretilir.
if [ -n "${CI:-}" ]; then
    ditto -c -k --keepParent dist/Ayrim.app dist/Ayrim-macos-arm64.zip
    echo "Hazır: dist/Ayrim-macos-arm64.zip"
    exit 0
fi

target="/Applications/Ayrim.app"
if [ -w /Applications ]; then
    rm -rf "$target"
    cp -R dist/Ayrim.app "$target"
    echo "Hazır: $target (Launchpad'de ve Spotlight'ta 'Ayrım' olarak görünür)"
else
    echo "Hazır: dist/Ayrim.app — Uygulamalar klasörüne sürükleyin."
fi
