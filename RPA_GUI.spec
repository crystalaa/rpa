# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('config/*.json', 'config'), ('docs/*.html', 'docs'), ('data/*.xlsx', 'data'), ('rpa_framework/robots/*.py', 'rpa_framework/robots'), ('rpa_framework/ui/resources/*', 'rpa_framework/ui/resources'), ('.venv/Lib/site-packages/playwright', 'playwright'), ('.venv/Lib/site-packages/pyee', 'pyee'), ('.venv/Lib/site-packages/greenlet', 'greenlet')],
    hiddenimports=['playwright', 'playwright.sync_api', 'playwright.async_api', 'playwright._impl._api_types', 'playwright._impl._connection', 'playwright._impl._driver', 'playwright._impl._transport', 'playwright._impl._browser_type', 'playwright._impl._browser', 'playwright._impl._page', 'playwright._impl._frame', 'playwright._impl._element_handle', 'playwright._impl._locator', 'playwright._impl._network', 'playwright._impl._video', 'playwright._impl._accessibility', 'playwright._impl._assertions', 'playwright._impl._fetch', 'playwright._impl._waiter', 'playwright._impl._greenlets', 'playwright._impl._event_context_manager', 'pyee', 'pyee.base', 'greenlet', 'openpyxl', 'PySide6', 'sqlite3', 'requests', 'pandas', 'json', 'logging', 'pathlib', 'os', 'sys', 'traceback', 'rpa_framework.utils.db_util', 'rpa_framework.utils.email_util', 'rpa_framework.utils.base64_decoder', 'rpa_framework.robots.ah_related_party_trans'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=['matplotlib,scipy,PIL,tkinter,test,unittest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RPA_GUI',
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
    icon=['rpa_framework\\ui\\resources\\favicon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['*.dll,*.so,*.dylib'],
    name='RPA_GUI',
)
