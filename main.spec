# game_manager.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# --- ReportLab data and hidden imports (from original) ---
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
try:
    reportlab_hidden += collect_submodules('reportlab')
except:
    pass
reportlab_datas = collect_data_files('reportlab')

# --- Pillow (required by reportlab, also used for icons) ---
pillow_hidden = ['PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont']
try:
    pillow_hidden += collect_submodules('PIL')
except:
    pass
pillow_datas = collect_data_files('PIL')

# --- Excluded modules (large/unused) ---
# IMPORTANT: Do NOT exclude QtWebEngine or QtWebEngineWidgets – they are needed for the trailer player.
excluded_modules = [
    'tkinter',
    'matplotlib',
    'numpy',
    'scipy',
    'pandas.tests',
    'openpyxl.tests',
    # QtWebEngine is required – keep it
    # 'PyQt5.QtWebEngine',
    # 'PyQt5.QtWebEngineWidgets',
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
    ['main.py'],  # <-- Entry point is main.py (not gui_main.py)
    pathex=[],
    binaries=[],
    # Icon and data files from reportlab and Pillow
    datas=[('icon.ico', '.')] + reportlab_datas + pillow_datas,
    hiddenimports=[
        # Core PyQt5
        'PyQt5.sip',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtWebEngineWidgets',   # explicitly required for trailer player
        # Third-party
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
        # ---- Custom UI modules (all three versions and helpers) ----
        'gui_main_1',
        'gui_main_2',
        'gui_main_3',
        'ui_header',
        'ui_sidebar',
        'ui_details_panel',
        'widgets',
        'image_display',
        'trailer_player',
        'settings_dialog',
        'config',
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
    strip=False,               # Prevent FileNotFoundError on Windows (strip.exe missing)
    upx=True,                  # Use UPX if installed; set False if you don't have it
    upx_exclude=['vcruntime140.dll'],
    runtime_tmpdir=None,
    console=False,              # Console window (show/hide controlled by config)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    onefile=True,              # Single executable
)