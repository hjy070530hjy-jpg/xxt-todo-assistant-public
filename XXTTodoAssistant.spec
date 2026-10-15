# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
tool_data = [('extras/geek/geek.exe', 'extras/geek')] if Path('extras/geek/geek.exe').is_file() else []
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('licenses', 'licenses'), ('assets/geek-tool.png', 'assets'), ('assets/memory-clean.svg', 'assets')] + tool_data,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Ignore unrelated ICU from external Poppler PATH; Qt uses Windows system ICU.
a.binaries = [entry for entry in a.binaries if '.cache' not in entry[1].lower()]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='XXTTodoAssistant',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='XXTTodoAssistant',
)
