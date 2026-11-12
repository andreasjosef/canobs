"""Open a note in Obsidian and bring its window to the front."""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

from . import windows


def _focus_sway(timeout: float = 8.0) -> None:
    """Focus the Obsidian window, waiting for it if Obsidian is just starting."""
    if not (os.environ.get("SWAYSOCK") and shutil.which("swaymsg")):
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = subprocess.run(
            ["swaymsg", '[app_id="obsidian"]', "focus"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if r.returncode == 0:
            return
        time.sleep(0.25)


def _vault_path(path: Path) -> str:
    """The note's path as Obsidian sees it. Under WSL, Obsidian runs on Windows,
    so /mnt/c/... has to become C:\\..."""
    resolved = str(path.resolve())
    if windows.is_wsl() and shutil.which("wslpath"):
        r = subprocess.run(["wslpath", "-w", resolved], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return resolved


def _open_uri(uri: str, focus: bool) -> bool:
    """Hand a URI to the OS. False if this OS has no way to do that."""
    if sys.platform == "win32":
        os.startfile(uri)
        return True
    if windows.is_wsl():
        # Start-Process goes through ShellExecute, like os.startfile above.
        # (explorer.exe opens Documents instead of following obsidian:// links.)
        cmd = windows.powershell(f"{windows.DECODE}Start-Process (& $d '{windows.b64(uri)}')")
        if not cmd:
            return False
    elif sys.platform == "darwin":
        cmd = ["open", *([] if focus else ["-g"]), uri]  # -g: don't bring to front
    elif shutil.which("xdg-open"):
        cmd = ["xdg-open", uri]
    else:
        return False
    subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True


def open_note(path: Path, focus: bool = True, new_tab: bool = False) -> bool:
    """Open path via the obsidian:// URI; reuses a running instance or starts one."""
    uri = f"obsidian://open?path={quote(_vault_path(path), safe='')}"
    if new_tab:
        uri += "&paneType=tab"
    if not _open_uri(uri, focus):
        return False
    if focus:
        _focus_sway()
    return True
