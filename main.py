import os
import sys
import ctypes
from PyQt5.QtWidgets import QApplication

# Import the new GUI module
from gui_main import GameManager

# Import config to read console visibility setting
from config import CONFIG_FILE, _load_config

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
    """
    Set up logging to file. If config allows, also show console and tee output.
    Returns the log file path.
    """
    base_dir = get_base_dir()
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "game_manager.log")

    # Read config to decide whether to show console
    config = _load_config()
    show_console = config.getboolean("General", "show_console", fallback=False)

    # Tee class to write to multiple outputs
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

    # Open log file for writing
    log_file = open(log_path, "w", encoding="utf-8")

    if show_console:
        # Show console window (if it was hidden by default)
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 1)
        except:
            pass
        # Tee to both original stdout/stderr and log file
        sys.stdout = Tee(sys.__stdout__, log_file)
        sys.stderr = Tee(sys.__stderr__, log_file)
    else:
        # Hide console window
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except:
            pass
        # Tee only to log file
        sys.stdout = Tee(log_file)
        sys.stderr = Tee(log_file)

    print(f"Log file: {log_path}")
    return log_path

def main():
    # Setup logging and console first
    log_path = setup_logging_and_console()

    # Prepare cache folder
    cache_dir = setup_cache()
    print(f"Cache folder ready at: {cache_dir}")

    # Launch PyQt5 GUI
    app = QApplication(sys.argv)
    window = GameManager()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()