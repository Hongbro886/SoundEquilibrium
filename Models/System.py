from pathlib import Path
import sys
import win32com.client

def get_app_dir() -> Path:
    """Get application directory, works both in development and when frozen by PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent

def create_startup_shortcut():
    startup_dir = Path.home() / r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"
    shortcut_path = startup_dir / "统一音量控制器.lnk"

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(str(shortcut_path))

    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()

        shortcut.TargetPath = str(exe_path)
        shortcut.WorkingDirectory = str(exe_path.parent)
        shortcut.IconLocation = str(exe_path)
        shortcut.Arguments = ""
    else:
        python_exe = Path(sys.executable).resolve()
        main_py = Path(__file__).resolve()

        shortcut.TargetPath = str(python_exe)
        shortcut.Arguments = f'"{main_py}"'
        shortcut.WorkingDirectory = str(main_py.parent)
        shortcut.IconLocation = str(python_exe)

    shortcut.save()

def remove_startup_shortcut():
    shortcut_path = Path.home() / r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\统一音量控制器.lnk"

    if shortcut_path.exists():
        shortcut_path.unlink()