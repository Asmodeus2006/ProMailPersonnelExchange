# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Promed Messagerie
import sys
from pathlib import Path

# Locate qt_material so its XML themes are bundled
try:
    import qt_material as _qm
    _qt_material_datas = [(str(Path(_qm.__file__).parent), "qt_material")]
except ImportError:
    _qt_material_datas = []

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[
        *_qt_material_datas,
        ("ressources", "ressources"),
    ],
    hiddenimports=[
        # exchangelib and its deps
        "exchangelib",
        "lxml",
        "lxml.etree",
        "requests",
        "cached_property",
        "isodate",
        "pytz",
        "tzlocal",
        "defusedxml",
        # pywin32 COM (used for AD user lookup)
        "win32com",
        "win32com.client",
        "win32com.client.gencache",
        "win32com.shell",
        "pywintypes",
        "pythoncom",
        "win32api",
        "win32con",
        # pkg_resources (used internally by qt_material)
        "pkg_resources",
        "pkg_resources.py2_warn",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy unused packages to keep the build lean
    excludes=["tkinter", "matplotlib", "numpy", "scipy", "pandas", "IPython"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_icon = "ressources\\logo_promed.ico" if Path("ressources\\logo_promed.ico").exists() else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PromedMessagerie",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PromedMessagerie",
)
