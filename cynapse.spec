# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['cynapse_entry.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('cynapse/data', 'cynapse/data'),
        ('cynapse/neurons', 'cynapse/neurons'),
        # ('cynapse/models', 'cynapse/models'), # Large models, excluded by default?
    ],
    hiddenimports=[
        'cynapse.core.hivemind',
        'cynapse.tui.main',
        'cynapse.utils.security',
        # Dynamic imports in hivemind
        'llama_cpp', 
        'ollama',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'unittest', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Cynapse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
