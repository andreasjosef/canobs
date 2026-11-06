"""Run a Claude Code job on a note in the background.

`spawn()` detaches a worker (`python -m canobs.agent ...`) so the CLI returns
immediately. The worker runs `claude -p` with no tools, no MCP servers and no
settings/CLAUDE.md, so the note content is pure input and can't make the agent
touch or reveal anything; canobs writes the result.
"""
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


def available() -> bool:
    return shutil.which("claude") is not None


def spawn(note: Path, out: Path, label: str, prompt: str, open_result: bool,
          model: str | None = None) -> None:
    """Start the worker detached from this terminal."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "a")
    subprocess.Popen(
        [sys.executable, "-m", "canobs.agent", str(note), str(out), label, prompt,
         "1" if open_result else "0", model or ""],
        stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        start_new_session=True,
    )


def _title(note: Path) -> str:
    """The note's '# heading', falling back to its filename."""
    for line in note.read_text().splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return note.stem


def _notify(summary: str, body: str, urgency: str = "normal") -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "canobs", "-u", urgency, summary, body])


def _run(note: Path, out: Path, label: str, prompt: str, open_result: bool,
         model: str | None) -> None:
    try:
        system = prompts.load().system
    except prompts.PromptsError as e:
        print(e, file=sys.stderr)
        _notify("canobs: bad prompts file", str(e), "critical")
        return
    message = f"{prompt}\n\n<note>\n{note.read_text()}\n</note>"
    try:
        r = subprocess.run(
            ["claude", "-p",
             *(["--model", model] if model else []),
             "--tools", "",
             "--strict-mcp-config",
             "--setting-sources=",  # no CLAUDE.md, memory, hooks or user settings
             "--no-session-persistence",
             "--system-prompt", system],
            input=message, capture_output=True, text=True,
            timeout=TIMEOUT, cwd=note.parent,
        )
    except subprocess.TimeoutExpired:
        _notify("canobs: Claude timed out", note.stem, "critical")
        return

    body = r.stdout.strip()
    if r.returncode != 0 or not body:
        print(f"claude failed ({r.returncode}) for {note}:\n{r.stderr}", file=sys.stderr)
        _notify("canobs: Claude failed", f"{note.stem}\nSee {LOG}", "critical")
        return

    out.write_text(f"# {_title(note)} – {label}\n\n_Source: [[{note.stem}]]_\n\n{body}\n")
    _notify(f"{label} ready", out.name)
    if open_result:
        obsidian.open_note(out, focus=False, new_tab=True)


if __name__ == "__main__":
    note, out, label, prompt, open_flag, model = sys.argv[1:7]
    os.environ.pop("CLAUDECODE", None)  # allow running when canobs is launched from Claude Code
    _run(Path(note), Path(out), label, prompt, open_flag == "1", model or None)
