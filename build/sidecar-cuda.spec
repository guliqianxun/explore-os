# -*- mode: python -*-
"""ft-023: PyInstaller spec for the CUDA-flavored sidecar bundle (self-use).

Run from the project root:

    uv run pyinstaller build/sidecar-cuda.spec --noconfirm --distpath dist

Output: ``dist/explore-os-sidecar/explore-os-sidecar.exe`` (one-folder).
The folder is referenced by ``electron-builder.yml`` as ``extraResources``
so it lands at ``<app>/resources/sidecar/`` in the packaged Electron app.

Notes
-----
* ``collect_all`` is used for torch/docling/matplotlib/transformers — these
  modules dynamic-import submodules and bundle non-py data (CUDA DLLs,
  shaders, fonts, JSON manifests). PyInstaller's static analysis misses them.
* ``hookspath=["build/hooks"]`` provides ``hook-torch.py`` as a belt-and-
  suspenders fallback for torch CUDA hidden imports.
* ``console=True``: keep a console window so stdout (the "listening on"
  line) is reachable. Electron parent reads the pipe regardless.
* CPU-flavored bundle is left for ft-025; this spec is CUDA-only.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
ROOT = Path.cwd()

# Heavyweight deps with non-trivial dynamic imports / data.
torch_data, torch_binaries, torch_hidden = collect_all("torch")
docling_data, docling_binaries, docling_hidden = collect_all("docling")
docling_core_data, docling_core_binaries, docling_core_hidden = collect_all("docling_core")
mpl_data, mpl_binaries, mpl_hidden = collect_all("matplotlib")
trans_data, trans_binaries, trans_hidden = collect_all("transformers")

a = Analysis(
    ["sidecar_entry.py"],
    pathex=[str(ROOT)],
    binaries=(
        torch_binaries
        + docling_binaries
        + docling_core_binaries
        + mpl_binaries
        + trans_binaries
    ),
    datas=[
        ("config", "config"),
        ("apps", "apps"),
        ("interpret", "interpret"),
        ("delivery", "delivery"),
        ("sources", "sources"),
        ("subscriptions", "subscriptions"),
        *torch_data,
        *docling_data,
        *docling_core_data,
        *mpl_data,
        *trans_data,
    ],
    hiddenimports=[
        # Django plumbing PyInstaller often misses
        "django.template.loaders.app_directories",
        "django.template.loaders.filesystem",
        "django.contrib.admin.apps",
        "django.contrib.auth.apps",
        "django.contrib.contenttypes.apps",
        "django.contrib.sessions.apps",
        "django.contrib.messages.apps",
        "django.contrib.staticfiles.apps",
        "rest_framework",
        "rest_framework.apps",
        # Local apps (each AppConfig is loaded by string path)
        "apps.core.apps",
        "apps.api.apps",
        "apps.extract.apps",
        "apps.interpret.apps",
        "apps.render.apps",
        "subscriptions.apps",
        "sources.apps",
        "interpret.apps",
        "delivery.apps",
        # Server
        "waitress",
        # Heavyweight deps' hidden imports
        *torch_hidden,
        *docling_hidden,
        *docling_core_hidden,
        *mpl_hidden,
        *trans_hidden,
    ],
    hookspath=["build/hooks"],
    runtime_hooks=[],
    excludes=[
        "pytest",
        "pytest_django",
        "ruff",
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="explore-os-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="explore-os-sidecar",
)
