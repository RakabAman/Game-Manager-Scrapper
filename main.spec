# game_manager.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# --- Force collect reportlab (even if hooks fail) ---
reportlab_hidden = [
    'reportlab',
    'reportlab.pdfgen',
    'reportlab.platypus',
    'reportlab.lib',
    'reportlab.lib.pagesizes',
    'reportlab.lib.styles',
    'reportlab.lib.utils',
    'reportlab.lib.colors',
    'reportlab.pdfbase',
    'reportlab.pdfbase.pdfmetrics',
    'reportlab.graphics',
    'reportlab.graphics.shapes',
    'reportlab.graphics.renderPDF',
]
# Try to collect submodules automatically as fallback
try:
    reportlab_hidden += collect_submodules('reportlab')
except:
    pass

# Collect data files (fonts, etc.)
reportlab_datas = collect_data_files('reportlab')

# --- Collect Pillow (required by reportlab) ---
pillow_hidden = ['PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont']
try:
    pillow_hidden += collect_submodules('PIL')
except:
    pass
pillow_datas = collect_data_files('PIL')

# Excluded large/unused modules
excluded_modules = [
    'tkinter',
    'matplotlib',
    'numpy',
    'scipy',
    'pandas.tests',
    'openpyxl.tests',
    'PyQt5.QtWebEngine',
    'PyQt5.QtWebEngineWidgets',
    'PyQt5.QtQuick',
    'PyQt5.QtQml',
    'PyQt5.QtPositioning',
    'PyQt5.QtSensors',
    'PyQt5.QtSerialPort',
    'PyQt5.QtSql',
    'PyQt5.QtXml',
    'PyQt5.QtXmlPatterns',
    'PyQt5.QtBluetooth',
    'PyQt5.QtNfc',
    'PyQt5.QtDBus',
]

a = Analysis(
    ['gui_main.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.')] + reportlab_datas + pillow_datas,
    hiddenimports=[
        'PyQt5.sip',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        'requests',
        'configparser',
        'hashlib',
        'json',
        'csv',
        'sqlite3',
        'webbrowser',
        'tempfile',
        'html',
        're',
        'time',
        'os',
        'sys',
        'pathlib',
        'typing',
        'urllib',
        'base64',
        'colorsys',
        'pandas',
        'openpyxl',
        'fpdf',
    ] + reportlab_hidden + pillow_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
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
    name='GameManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,               # Disable stripping to avoid Windows errors
    upx=True,
    upx_exclude=['vcruntime140.dll'],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    onefile=True,
)