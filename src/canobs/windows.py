"""Reaching the Windows desktop from native Windows or from WSL."""
import base64
import platform
import shutil
import sys


def is_wsl() -> bool:
    """Linux under WSL, where the desktop (and Obsidian) is Windows."""
    return sys.platform == "linux" and "microsoft" in platform.uname().release.lower()


def b64(s: str) -> str:
    """Base64 of a string, for embedding in a script; decode it with DECODE."""
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


# Defines `& $d '<base64>'` for decoding b64() strings inside a script. Passing
# strings this way means no quote or character in them can break the script.
DECODE = "$d = { param($s) [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($s)) }\n"


def powershell(script: str) -> list[str] | None:
    """argv running script in Windows PowerShell, or None if it isn't reachable.

    -EncodedCommand carries the script past the Windows command line (and WSL's
    argument passing) untouched.
    """
    ps = shutil.which("powershell.exe") or shutil.which("powershell")
    if not ps:
        return None
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return [ps, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
