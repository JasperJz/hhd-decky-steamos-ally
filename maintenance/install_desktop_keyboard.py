"""Install the optional, tested HHD 4.1.12 X11 desktop keyboard workaround."""
from pathlib import Path
import importlib.util
import os
import shutil

OLD = '''def open_steam_kbd(open: bool = True):
    return run_steam_command(f"steam://{'open' if open else 'close'}/keyboard")'''
NEW = '''def open_steam_kbd(open: bool = True):
    # Local X11 desktop keyboard workaround; gamepad mode retains upstream behavior.
    if open and not is_steam_gamepad_running():
        from pathlib import Path
        import sys
        helper = Path('/home/deck/.local/share/hhd/maintenance/desktop_keyboard.py')
        if helper.is_file():
            subprocess.Popen([sys.executable, str(helper)])
            return True
    return run_steam_command(f"steam://{'open' if open else 'close'}/keyboard")'''


def install():
    if os.geteuid() != 0:
        raise RuntimeError('Run this script with sudo and the HHD venv Python')
    source = Path(importlib.util.find_spec('hhd.plugins.plugin').origin)
    text = source.read_text()
    marker = '# Local X11 desktop keyboard workaround;'
    if marker not in text and OLD not in text:
        raise RuntimeError('Unsupported HHD source layout; source was not changed')
    destination = Path('/home/deck/.local/share/hhd/maintenance/desktop_keyboard.py')
    helper = Path(__file__).with_name('desktop_keyboard.py')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if helper.resolve() != destination.resolve():
        shutil.copy2(helper,destination)
    destination.chmod(0o644)
    if marker not in text:
        backup = Path('/var/lib/hhd-trial/desktop-keyboard-plugin-original.py')
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():
            shutil.copy2(source,backup)
        patched = text.replace(OLD,NEW,1)
        compile(patched,str(source),'exec')
        source.write_text(patched)
    print('Installed desktop keyboard workaround. Restart hhd-power to load it.')


if __name__ == '__main__':
    install()
