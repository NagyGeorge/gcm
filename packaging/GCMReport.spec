# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

ROOT = Path.cwd()


def linux_tk_binaries():
    if not sys.platform.startswith("linux"):
        return []

    python_lib = Path(sys.base_prefix) / "lib"
    return [
        (str(path), ".")
        for library_name in ("libtcl8.6.so", "libtk8.6.so")
        if (path := python_lib / library_name).exists()
    ]


a = Analysis(
    [str(ROOT / "src" / "unit_awards_tracker" / "gui.py")],
    pathex=[str(ROOT / "src")],
    binaries=linux_tk_binaries(),
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["playwright"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GCMReport",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
