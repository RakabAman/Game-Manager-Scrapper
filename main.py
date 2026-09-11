import os
import sys
import ctypes
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QCoreApplication
import config

# Choose the GUI module based on config (1=original, 2=claude, 3=deep)
if config.UI_VERSION == 2:
    from gui_main_2 import GameManager
elif config.UI_VERSION == 3:
    from gui_main_3 import GameManager
else:
    from gui_main_1 import GameManager

# Import config reader (avoid name conflict)
from config import CONFIG_FILE, _load_config

import ctypes

def set_app_user_model_id():
    if os.name == "nt":
        try:
            myappid = "yourcompany.gamemanager.gui.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"[DEBUG] Could not set AppUserModelID: {e}")
            
def get_base_dir():
    """Return the base directory for cache depending on run mode."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def setup_cache():
    """Ensure a cache folder exists next to the exe/script."""
    base_dir = get_base_dir()
    cache_dir = os.path.join(base_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def setup_logging_and_console():
    base_dir = get_base_dir()
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "game_manager.log")

    cfg = _load_config()
    show_console = cfg.getboolean("General", "show_console", fallback=False)

    class Tee:
        def __init__(self, *files):
            self.files = files
        def write(self, obj):
            for f in self.files:
                f.write(obj)
                f.flush()
        def flush(self):
            for f in self.files:
                f.flush()

    log_file = open(log_path, "w", encoding="utf-8")

    if show_console and getattr(sys, 'frozen', False):
        # No console exists yet in a console=False build — create one on demand
        ctypes.windll.kernel32.AllocConsole()
        sys.stdout = Tee(open("CONOUT$", "w"), log_file)
        sys.stderr = Tee(open("CONOUT$", "w"), log_file)
    else:
        sys.stdout = Tee(log_file)
        sys.stderr = Tee(log_file)

    print(f"Log file: {log_path}")
    return log_path

def get_icon_path():
    """Return the full path to the icon file, handling frozen mode."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
        print(f"[DEBUG] Frozen mode – sys._MEIPASS = {base}")
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        print(f"[DEBUG] Not frozen – base = {base}")
    
    # List contents of the base directory (only if frozen)
    if getattr(sys, 'frozen', False):
        try:
            files = os.listdir(base)
            print(f"[DEBUG] Files in _MEIPASS: {files}")
        except Exception as e:
            print(f"[DEBUG] Could not list _MEIPASS: {e}")
    
    path = os.path.join(base, 'icon.ico')
    exists = os.path.exists(path)
    print(f"[DEBUG] Icon path = {path}")
    print(f"[DEBUG] Icon exists? {exists}")
    if exists:
        size = os.path.getsize(path)
        print(f"[DEBUG] Icon file size = {size} bytes")
        # Optionally try to load it as QIcon to see if it's valid
        try:
            test_icon = QIcon(path)
            if not test_icon.isNull():
                print("[DEBUG] QIcon loaded successfully.")
                # Check available sizes
                available = test_icon.availableSizes()
                print(f"[DEBUG] Available icon sizes: {[s.width() for s in available]}")
            else:
                print("[DEBUG] QIcon is null – the file may be invalid.")
        except Exception as e:
            print(f"[DEBUG] QIcon loading failed: {e}")
    else:
        print("[DEBUG] Icon file not found!")
    return path

def main():
    set_app_user_model_id()   # before QApplication()

    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    log_path = setup_logging_and_console()
    cache_dir = setup_cache()
    print(f"Cache folder ready at: {cache_dir}")

    app = QApplication(sys.argv)   # <-- only this one

    icon_path = get_icon_path()
    if os.path.exists(icon_path):
        try:
            app.setWindowIcon(QIcon(icon_path))
            print("[DEBUG] setWindowIcon called successfully.")
        except Exception as e:
            print(f"[DEBUG] setWindowIcon failed: {e}")
    else:
        print(f"Warning: icon not found at {icon_path}")

    config.apply_application_palette(app)

    window = GameManager()
    window.setWindowIcon(app.windowIcon())
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()