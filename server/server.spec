# -*- mode: python ; coding: utf-8 -*-
"""
Custom PyInstaller spec for WeAgentChat backend.
Ensures project package `app` is collected (uvicorn imports via string),
and bundles tiktoken encoding assets.
"""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

block_cipher = None

spec_path = Path(sys.argv[0]).resolve()
server_dir = spec_path.parent
sys.path.insert(0, str(server_dir))

datas: list = []
binaries: list = []
datas += collect_data_files('tiktoken')
datas += collect_data_files('tiktoken_ext')
datas += collect_data_files('litellm')

# uvicorn loads `app.main:app` dynamically, so force-include the package.
hiddenimports = collect_submodules('app')
hiddenimports += collect_submodules('litellm')
# Ensure tiktoken extension encodings are bundled.
hiddenimports += ['tiktoken_ext', 'tiktoken_ext.openai_public']
# RecallService 在运行时按需导入该模块，打包时需显式包含。
hiddenimports += ['agents.extensions.models.litellm_model']

app_datas, app_binaries, app_hiddenimports = collect_all('app')
datas += app_datas
binaries += app_binaries
hiddenimports += app_hiddenimports

litellm_datas, litellm_binaries, litellm_hiddenimports = collect_all('litellm')
datas += litellm_datas
binaries += litellm_binaries
hiddenimports += litellm_hiddenimports

# Alembic migrations/config needed at runtime
datas += [(os.path.join(server_dir, 'alembic'), 'alembic')]
datas += [(os.path.join(server_dir, 'alembic.ini'), '.')]
# Static assets for preset avatars and other static files
datas += [(os.path.join(server_dir, 'static'), 'static')]
# Memobase migrations
datas += [
    (
        os.path.join(server_dir, 'app', 'vendor', 'memobase_server', 'migrations'),
        'app/vendor/memobase_server/migrations',
    )
]
# Memobase alembic.ini
datas += [
    (
        os.path.join(server_dir, 'app', 'vendor', 'memobase_server', 'alembic.ini'),
        'app/vendor/memobase_server',
    )
]
# sqlite-vec extension
sqlite_vec_dll = os.path.join(
    server_dir, 'venv', 'Lib', 'site-packages', 'sqlite_vec', 'vec0.dll'
)
if os.path.exists(sqlite_vec_dll):
    binaries += [(sqlite_vec_dll, 'sqlite_vec')]

a = Analysis(
    ['app/cli.py'],
    pathex=[server_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Pillow 的 AVIF 插件占用较大且未使用，打包时排除以减小体积。
    excludes=['PIL._avif', 'PIL.AvifImagePlugin'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='wechatagent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name='wechatagent',
)
