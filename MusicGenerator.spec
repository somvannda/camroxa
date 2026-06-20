# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['build_entry.py'],
    pathex=[],
    binaries=[],
    datas=[('python_app\\assets', 'python_app\\assets'), ('C:\\Users\\Kong Somvannda\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\glfw\\glfw3.dll', 'glfw'), ('python_app\\.env', '.')],
    hiddenimports=['python_app', 'python_app.app', 'python_app.app.main_window'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'tensorflow', 'transformers'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MusicGenerator',
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
    icon='python_app\\assets\\icons\\app.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MusicGenerator',
)
