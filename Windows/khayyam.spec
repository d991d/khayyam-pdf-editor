# -*- mode: python ; coding: utf-8 -*-
#
# khayyam.spec — PyInstaller spec for Khayyam PDF Editor (Windows)
#
# Usage (from the Windows/ directory):
#   pyinstaller khayyam.spec
#
# Output: dist\Khayyam PDF Editor\Khayyam PDF Editor.exe  (one-folder bundle)

import sys
from pathlib import Path

block_cipher = None

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[
        # Bundle the src package
        ("src", "src"),
    ],
    hiddenimports=[
        # PyMuPDF internal modules
        "fitz",
        "fitz._fitz",
        # PyQt6 modules that get missed by the auto-analyser
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Strip heavy unused packages to keep the bundle lean
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "tkinter",
        "unittest",
        "pydoc",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── PYZ (Python bytecode archive) ─────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE ───────────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # one-folder mode (faster startup than onefile)
    name="Khayyam PDF Editor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                       # compress with UPX if available
    console=False,                  # no console window (windowed app)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",                # Windows taskbar / Explorer icon
    version_file=None,
)

# ── COLLECT (assemble the dist folder) ────────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Khayyam PDF Editor",     # → dist\Khayyam PDF Editor\
)
