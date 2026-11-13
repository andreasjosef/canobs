import argparse
import re
import sys
import unicodedata
from pathlib import Path

import questionary
from questionary import Choice, Separator, Style

from . import agent, canvas, config, obsidian, prompts
from .convert import to_markdown

COURSE_ID = 585

RESOURCE_TYPES = ("Page", "Assignment")

STYLE = Style([
    ("qmark", "fg:#7aa2f7 bold"),
    ("question", "bold"),
    ("answer", "fg:#9ece6a bold"),
    ("pointer", "fg:#bb9af7 bold"),
    ("highlighted", "fg:#bb9af7 bold"),
    ("separator", "fg:#e0af68"),
    ("instruction", "fg:#565f89 italic"),
    ("search_success", "fg:#9ece6a"),
    ("search_none", "fg:#f7768e"),
    ("text", ""),
])


def clean(text: str) -> str:
    """Drop emoji/symbols and collapse whitespace."""
    kept = "".join(
        c for c in text
        if unicodedata.category(c) not in ("So", "Sk", "Cf", "Cs")
        and c not in "️⃣"
    )
    return re.sub(r"\s+", " ", kept).strip()


def clean_module(name: str) -> str:
    """Clean a module title and drop its leading course number ("8. ")."""
    return re.sub(r"^\d+\.\s*", "", clean(name))


def slugify(text: str) -> str:
    """Code-friendly filename: ASCII, lowercase, words joined by '-'."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def say(text: str, style: str = "fg:#565f89 italic") -> None:
    questionary.print(text, style=style)


def answer(question: questionary.Question):
    """Run a prompt; Ctrl-C exits cleanly."""
    result = question.ask()
    if result is None:
        sys.exit(1)
    return result


def select(message: str, choices: list):
    return answer(questionary.select(
        message,
        choices=choices,
        style=STYLE,
        qmark="›",
        pointer="❯",
        use_search_filter=True,
        use_jk_keys=False,
        instruction="(↑↓ to move, type to search)",
    ))


def resource_choices(items: list) -> list:
    """Pages/Assignments, grouped under the SubHeader they sit beneath."""
    choices, header = [], None
    for item in items:
        if item["type"] == "SubHeader":
            header = clean(item["title"])
        elif item["type"] in RESOURCE_TYPES:
            if header:
                choices.append(Separator(f"── {header}"))
                header = None
            choices.append(Choice(clean(item["title"]), value=item))
    return choices


def select_resource() -> dict:
    """Pick a module, then a Page/Assignment within it."""
    say("Fetching modules…")
    mods = canvas.modules(COURSE_ID)
    mod = select("Module", [Choice(clean_module(m["name"]), value=m) for m in mods])

    say("Fetching module items…")
    choices = resource_choices(canvas.module_items(COURSE_ID, mod["id"]))
    if not choices:
        say("No pages or assignments in that module.", "fg:#f7768e")
        sys.exit(1)
    return select("Resource", choices)


CUSTOM = "Custom prompt…"

Job = tuple[str, str, str, str | None]


def choose_jobs(prompt: str | None, allow_none: bool) -> list[Job]:
    """Return (label, file suffix, prompt, model) for each picked Claude job; may be empty."""
    if not agent.available():
        return []
    try:
        config = prompts.load()
    except prompts.PromptsError as e:
        say(str(e), "fg:#f7768e")
        sys.exit(1)
    if prompt:
        return [("Claude", "claude", prompt, config.model)]
    jobs = {j.name: j for j in config.jobs}
    picked = answer(questionary.checkbox(
        "Claude", choices=list(jobs) + [CUSTOM], style=STYLE, qmark="›", pointer="❯",
        use_jk_keys=False,
        instruction="(space to select, enter to confirm" + (", none to skip)" if allow_none else ")"),
        validate=lambda xs: allow_none or bool(xs) or "Pick at least one job",
    ))
    result = [
        (jobs[name].file.replace("-", " ").capitalize(), jobs[name].file,
         jobs[name].prompt, config.model_for(jobs[name]))
        for name in picked if name != CUSTOM
    ]
    if CUSTOM in picked:
        text = answer(questionary.text("Prompt", style=STYLE, qmark="›")).strip()
        if text:
            result.append(("Claude", "claude", text, config.model))
    return result


def start_job(note: Path, job: Job, open_result: bool) -> None:
    label, suffix, text, model = job
    out = agent.output_path(note, suffix)
    agent.spawn(note, out, label, text, open_result, model)
    say(f"⠿ Claude is writing {out.name} in the background. You'll get a notification.",
        "fg:#7aa2f7")


def ask(notes_dir: Path, open_result: bool = True, prompt: str | None = None) -> None:
    """Run a Claude job on an existing note."""
    if not agent.available():
        say("The claude command was not found on PATH.", "fg:#f7768e")
        sys.exit(1)
    notes = sorted(notes_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not notes:
        say(f"No notes in {notes_dir}.", "fg:#f7768e")
        sys.exit(1)
    note = select("Note", [Choice(n.stem, value=n) for n in notes])
    for job in choose_jobs(prompt, allow_none=False):
        start_job(note, job, open_result)


def create(notes_dir: Path, open_note: bool = True, prompt: str | None = None) -> None:
    item = select_resource()
    title = clean(item["title"])

    name = slugify(answer(questionary.text(
        "Note name", default=slugify(title), style=STYLE, qmark="›"
    )).strip().removesuffix(".md")) or slugify(title)
    path = notes_dir / f"{name}.md"
    if path.exists() and not answer(questionary.confirm(
        f"{path.name} already exists. Overwrite?", default=False, style=STYLE, qmark="›"
    )):
        sys.exit(1)
    jobs = choose_jobs(prompt, allow_none=True)

    body = to_markdown(canvas.item_html(COURSE_ID, item))
    notes_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n_Source: {item['html_url']}_\n\n{body}", encoding="utf-8")
    say(f"✓ Created {path}", "fg:#9ece6a bold")

    if open_note and not obsidian.open_note(path):
        say("Could not open Obsidian (no way to open obsidian:// links found).", "fg:#f7768e")
    for job in jobs:
        start_job(path, job, open_note)


def main() -> None:
    parser = argparse.ArgumentParser(prog="canobs", description="Canvas modules to Obsidian notes.")
    sub = parser.add_subparsers(dest="cmd")
    for name, help_text in (
        ("create", "create a note from a Canvas page or assignment (default)"),
        ("ask", "run a Claude job on an existing note"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--no-open", action="store_true", help="don't open results in Obsidian")
        p.add_argument("--prompt", help="custom Claude prompt (skips the job menu)")
        p.add_argument("--dir", metavar="PATH",
                       help="notes folder (default: NOTES_DIR in .env, else ~/notes/chas)")
    args = parser.parse_args()

    notes_dir = config.notes_dir(getattr(args, "dir", None))
    open_note = not getattr(args, "no_open", False)
    prompt = getattr(args, "prompt", None)
    try:
        if args.cmd == "ask":
            ask(notes_dir, open_result=open_note, prompt=prompt)
        else:
            create(notes_dir, open_note=open_note, prompt=prompt)
    except canvas.CanvasError as e:
        say(f"✗ {e}", "fg:#f7768e bold")
        sys.exit(1)
