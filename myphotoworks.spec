# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

src_dir = Path("src")
icon_file = str(src_dir / "myphotoworks" / "resources" / "myphotoworks.ico")

a = Analysis(
    [str(src_dir / "myphotoworks" / "main.py")],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        (str(src_dir / "myphotoworks" / "resources"), "myphotoworks/resources"),
    ],
    hiddenimports=[
        "myphotoworks",
        "myphotoworks.ui",
        "myphotoworks.ui.main_window",
        "myphotoworks.ui.preview_window",
        "myphotoworks.ui.settings_panel",
        "myphotoworks.ui.thumbnail_panel",
        "myphotoworks.ui.exif_panel",
        "myphotoworks.processing",
        "myphotoworks.processing.effects",
        "myphotoworks.processing.resize",
        "myphotoworks.processing.processor",
        "myphotoworks.models",
        "myphotoworks.models.photo_item",
        "myphotoworks.models.settings",
        "myphotoworks.workers",
        "myphotoworks.workers.batch_worker",
        "myphotoworks.utils",
        "myphotoworks.utils.config",
        "myphotoworks.utils.exif_reader",
        "piexif",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "pytest_qt",
        "ruff",
        "tkinter",
        "_tkinter",
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="myPhotoWorks",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=icon_file,
    runtime_tmpdir=None,
)
