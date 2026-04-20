# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['buttonbox/gui/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('buttonbox/gui/ui', 'buttonbox/gui/ui'),
    ],
    hiddenimports=[
        'PyQt6.sip',
        'serial.tools.list_ports',
        'serial.tools.list_ports_common',
        'serial.tools.list_ports_windows',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['evdev'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ButtonBox',
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # sin ventana de consola negra
    icon=None,          # podés poner 'assets/icon.ico' si tenés un ícono
)
