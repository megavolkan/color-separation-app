# PyInstaller tanımı: `uv run --group build pyinstaller packaging/Ayrim.spec`
import os
import sys

from ayrim import __version__

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON = os.path.join(ROOT, "build", "Ayrim.icns")

# Kullanılmayan büyük Qt modülleri paketten çıkarılır.
EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtPdf", "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtTest", "tkinter",
]

a = Analysis(
    [os.path.join(SPECPATH, "run_ayrim.py")],
    pathex=[os.path.join(ROOT, "src")],
    excludes=EXCLUDES,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Ayrim",
    console=False,
    target_arch="arm64" if sys.platform == "darwin" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Ayrim")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Ayrim.app",
        icon=ICON if os.path.exists(ICON) else None,
        bundle_identifier="local.ayrim",
        version=__version__,
        info_plist={
            "CFBundleDisplayName": "Ayrım",
            "CFBundleName": "Ayrım",
            "CFBundleShortVersionString": __version__,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "PDF",
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "Alternate",
                    "LSItemContentTypes": ["com.adobe.pdf"],
                }
            ],
        },
    )
