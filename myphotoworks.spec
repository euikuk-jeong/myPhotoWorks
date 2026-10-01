# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

from PyInstaller.utils.hooks import collect_all

src_dir = Path("src")
# MediaPipe (face analysis, stage 2): its native library is loaded at runtime by path, so
# collect the package's binaries / data explicitly
mp_datas, mp_binaries, mp_hiddenimports = collect_all("mediapipe")
icon_file = str(src_dir / "myphotoworks" / "resources" / "myphotoworks.ico")

a = Analysis(
    [str(src_dir / "myphotoworks" / "main.py")],
    pathex=[str(src_dir)],
    binaries=mp_binaries,
    datas=[
        (str(src_dir / "myphotoworks" / "resources"), "myphotoworks/resources"),
        (str(src_dir / "myphotoworks" / "ui" / "styles"), "myphotoworks/ui/styles"),
        (str(src_dir / "myphotoworks" / "recipes" / "fuji_fp1"), "myphotoworks/recipes/fuji_fp1"),
        # face models (BlazeFace detector, Face Landmarker): read at runtime from the package
        (str(src_dir / "myphotoworks" / "models_ml"), "myphotoworks/models_ml"),
    ] + mp_datas,
    hiddenimports=[
        "PyQt6.QtSvg",  # qsvg image plugin for the theme's SVG icons (QSS url())
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
        "myphotoworks.core",
        "myphotoworks.core.analysis_image",
        "myphotoworks.core.faces",
        "myphotoworks.core.composition",
        "myphotoworks.core.afpoint",
        "myphotoworks.utils.selection_log",
        "myphotoworks.core.grouping",
        "myphotoworks.core.pipeline",
        "myphotoworks.core.scoring",
        "myphotoworks.core.similarity",
        "myphotoworks.models.group_session",
        "myphotoworks.processing.export",
        "myphotoworks.processing.group_runner",
        "myphotoworks.workers.group_worker",
        "myphotoworks.ui.group_tab",
        "myphotoworks.ui.group_review_window",
        "myphotoworks.ui.guide",
        "myphotoworks.ui.zoom_view",
        "piexif",
        "numpy",
    ] + mp_hiddenimports,
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
