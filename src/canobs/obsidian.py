"""Open a note in Obsidian and bring its window to the front."""
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import quote


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


def open_note(path: Path, focus: bool = True, new_tab: bool = False) -> bool:
    """Open path via the obsidian:// URI; reuses a running instance or starts one."""
    if not shutil.which("xdg-open"):
        return False
    uri = f"obsidian://open?path={quote(str(path.resolve()), safe='')}"
    if new_tab:
        uri += "&paneType=tab"
    subprocess.Popen(
        ["xdg-open", uri],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    if focus:
        _focus_sway()
    return True
