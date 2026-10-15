# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
if not Path('extras/geek/geek.exe').is_file():
    raise RuntimeError('单文件发行版需要先将 Geek 放到 extras/geek/geek.exe')
tool_data = [('extras/geek/geek.exe', 'extras/geek')]
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
    a.binaries,
    a.datas,
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
