"""Run a Claude Code job on a note in the background.

`spawn()` detaches a worker (`python -m canobs.agent ...`) so the CLI returns
immediately. The worker runs `claude -p` with no tools, no MCP servers and no
settings/CLAUDE.md, so the note content is pure input and can't make the agent
touch or reveal anything; canobs writes the result.
"""
import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import obsidian, prompts

LOG = Path.home() / ".cache" / "canobs" / "agent.log"
TIMEOUT = 600


def output_path(note: Path, suffix: str) -> Path:
    return note.with_name(f"{note.stem}-{suffix}.md")


def _claude() -> str | None:
    """Full path to claude; on Windows it may be claude.cmd, which needs the path."""
    return shutil.which("claude")


def available() -> bool:
    return _claude() is not None


# Detach the worker so it outlives the terminal: a new session on macOS/Linux,
# a new process group without a console on Windows.
if sys.platform == "win32":
    _DETACH = dict(creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    _NO_WINDOW = dict(creationflags=subprocess.CREATE_NO_WINDOW)  # claude.cmd would open a console
else:
    _DETACH = dict(start_new_session=True)
    _NO_WINDOW = {}


def spawn(note: Path, out: Path, label: str, prompt: str, open_result: bool,
          model: str | None = None) -> None:
    """Start the worker detached from this terminal."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "a", encoding="utf-8")
    subprocess.Popen(
        [sys.executable, "-m", "canobs.agent", str(note), str(out), label, prompt,
         "1" if open_result else "0", model or ""],
        stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        **_DETACH,
    )


def _title(note: Path) -> str:
    """The note's '# heading', falling back to its filename."""
    for line in note.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return note.stem


# A toast via Windows PowerShell's WinRT API. Shown under PowerShell's app ID,
# since Windows only shows toasts for registered apps. Strings arrive base64
# encoded, so nothing in a title or filename can break out of the script.
_TOAST_PS = """
$d = {{ param($s) [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($s)) }}
$m = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$x = $m::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$t = $x.GetElementsByTagName('text')
[void]$t.Item(0).AppendChild($x.CreateTextNode((& $d '{summary}')))
[void]$t.Item(1).AppendChild($x.CreateTextNode((& $d '{body}')))
$id = '{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe'
$m::CreateToastNotifier($id).Show([Windows.UI.Notifications.ToastNotification]::new($x))
"""


def _toast(summary: str, body: str) -> None:
    """Windows toast, from native Windows or from WSL."""
    ps = shutil.which("powershell.exe") or shutil.which("powershell")
    if not ps:
        return
    b64 = lambda s: base64.b64encode(s.encode("utf-8")).decode("ascii")
    script = _TOAST_PS.format(summary=b64(summary), body=b64(body))
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        subprocess.run([ps, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       timeout=30, **_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"toast failed: {e}", file=sys.stderr)


def _notify(summary: str, body: str, urgency: str = "normal") -> None:
    """Desktop notification: toast on Windows/WSL, osascript on macOS, notify-send on Linux."""
    if sys.platform == "win32" or obsidian.is_wsl():
        _toast(summary, body)
    elif sys.platform == "darwin":
        subprocess.run(["osascript",
                        "-e", "on run argv",
                        "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
                        "-e", "end run",
                        summary, body])
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "canobs", "-u", urgency, summary, body])


def _run(note: Path, out: Path, label: str, prompt: str, open_result: bool,
         model: str | None) -> None:
    try:
        system = prompts.load().system
    except prompts.PromptsError as e:
        print(e, file=sys.stderr)
        _notify("canobs: bad prompts file", str(e), "critical")
        return
    message = f"{prompt}\n\n<note>\n{note.read_text(encoding='utf-8')}\n</note>"
    try:
        r = subprocess.run(
            [_claude() or "claude", "-p",
             *(["--model", model] if model else []),
             "--tools", "",
             "--strict-mcp-config",
             "--setting-sources=",  # no CLAUDE.md, memory, hooks or user settings
             "--no-session-persistence",
             "--system-prompt", system],
            input=message, capture_output=True, text=True, encoding="utf-8",
            timeout=TIMEOUT, cwd=note.parent, **_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        _notify("canobs: Claude timed out", note.stem, "critical")
        return

    body = r.stdout.strip()
    if r.returncode != 0 or not body:
        print(f"claude failed ({r.returncode}) for {note}:\n{r.stderr}", file=sys.stderr)
        _notify("canobs: Claude failed", f"{note.stem}\nSee {LOG}", "critical")
        return

    out.write_text(f"# {_title(note)} – {label}\n\n_Source: [[{note.stem}]]_\n\n{body}\n",
                   encoding="utf-8")
    _notify(f"{label} ready", out.name)
    if open_result:
        obsidian.open_note(out, focus=False, new_tab=True)


if __name__ == "__main__":
    note, out, label, prompt, open_flag, model = sys.argv[1:7]
    os.environ.pop("CLAUDECODE", None)  # allow running when canobs is launched from Claude Code
    _run(Path(note), Path(out), label, prompt, open_flag == "1", model or None)
