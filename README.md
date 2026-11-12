# canobs

Turn Canvas course pages into clean markdown notes in Obsidian, from the terminal.

Made for my classmates at Chas Academy: it reads our course (course 585 on
`chasacademy.instructure.com`). For another school or course, change the
two constants listed under [Configuration](#configuration).

`canobs create` lists the modules of a Canvas course, lets you pick a page or
assignment, and saves it as markdown in your notes folder (`~/notes/chas/`
unless you [configure another](#configuration)). The note then opens in
Obsidian. Works on macOS, Windows and Linux. Optionally, Claude writes a
follow-up file in the background, such
as a checklist for finishing the workshop.

```
› Module    Kurs 8 + 9: veckomaterial v.38–51
› Resource  Övning 1 – Funktionen i molnet: Azure Functions från pipelinen (ny version)
› Note name ovning-1-funktionen-i-molnet-azure-functions-fran-pipelinen-ny-version
› Claude    Checklist to finish it
✓ Created ~/notes/chas/ovning-1-funktionen-i-molnet-….md
⠿ Claude is writing ovning-1-…-checklist.md in the background. You'll get a notification.
```

## Requirements

- [uv](https://docs.astral.sh/uv/) (it provides Python 3.11+)
- git, to clone the repo
- A Canvas access token
- Optional:
  - [Obsidian](https://obsidian.md), with your notes folder inside a vault, to
    open notes automatically
  - [Claude Code](https://claude.com/claude-code) (`claude` on `PATH`) for Claude jobs
  - Linux only: `notify-send` for desktop notifications (macOS, Windows and
    WSL have them built in), and sway to move focus to Obsidian
  - WSL: canobs opens notes in Windows Obsidian through PowerShell, so
    keep your notes folder on the Windows side (`/mnt/c/...`)

## Setup

1. **Get the code:**
   ```sh
   git clone https://github.com/andreasjosef/canobs.git
   cd canobs
   ```
2. **Create a Canvas token:** in Canvas, go to *Account → Settings → Approved
   integrations → New access token*. Give it an expiry date.
3. **Store it** in `.env` in the project folder. Copy the example and fill in
   `CANVAS_TOKEN` in your editor (and `NOTES_DIR` if you want another folder):
   ```sh
   cp .env.example .env          # Windows (PowerShell): copy .env.example .env
   chmod 600 .env                # macOS/Linux: keep it private
   ```
   An exported `CANVAS_TOKEN` environment variable takes precedence over `.env`.
   `.env` is in `.gitignore`. Don't share your token.
4. **Install** the command:
   ```sh
   uv tool install --editable .
   ```
   If `canobs` isn't found afterwards, run `uv tool update-shell` and open a
   new terminal. canobs runs from this folder and reads `.env` from it, so
   don't move the folder. To uninstall, run `uv tool uninstall canobs`.

### Updating

```sh
cd canobs
git pull
```

The install is editable, so that's all. If a pull adds a dependency, reinstall
with `uv tool install --editable --force .`.

## Usage

```sh
canobs                        # same as canobs create
canobs create                 # Canvas page/assignment → note
canobs ask                    # run a Claude job on an existing note
canobs create --no-open       # don't open anything in Obsidian
canobs create --dir ~/vault/x # save into this folder instead
canobs ask --prompt "…"       # skip the job menu and use this prompt
```

Both commands take `--no-open`, `--prompt` and `--dir`.

In the menus, use ↑↓ to move and Enter to pick. Type to filter the list.
Ctrl-C quits at any step.

### create

1. **Module:** module titles, with emoji and course numbers removed.
2. **Resource:** only Pages and Assignments, grouped under each module's
   sub-headers (for example by week). Clips, links and quizzes are left out.
3. **Note name:** pre-filled with a filename-safe version of the title
   (lowercase ASCII, words joined by `-`). Whatever you type is converted the
   same way. If the file exists, you're asked before it's overwritten.
4. **Claude:** an optional follow-up job. Pick *None* to skip.

The note starts with the original title and a link back to Canvas:

```markdown
# M0 – Teamet redo

_Source: https://chasacademy.instructure.com/courses/585/modules/items/24042_

…
```

It then opens in Obsidian. If Obsidian is running, the existing window is
used; if not, it starts. On sway, the Obsidian window gets focus. The notes
folder must be inside an Obsidian vault for this to work.

### ask

Pick a note in the notes folder (newest first), then a job. This is for when
you want a checklist or summary after the note already exists.

## Claude jobs

A job runs in the background, so the terminal is free right away. When it's
done (usually under a minute):

- The result is saved next to the note as `<note>-<file>.md`, for example
  `m0-teamet-redo-checklist.md`. It starts with a `[[link]]` back to the note.
- You get a desktop notification.
- The file opens in a new Obsidian tab, without taking focus.

If a job fails, you get a red notification and the details go to
`~/.cache/canobs/agent.log`.

### Prompts

Jobs are defined in `src/canobs/prompts.toml` in this repo, so everyone gets
the same jobs and improvements arrive with `git pull`. Edits apply on the next
run. To share a new job, commit it.

```toml
# model = "sonnet"      # all jobs; omit to use Claude Code's default model

system = """…"""        # sent with every job

[[job]]
name = "Checklist to finish it"   # menu label
file = "checklist"                # output suffix: lowercase letters, digits, -
prompt = """…"""                  # what Claude should do with the note
# model = "opus"                  # optional: override the model for this job
```

Jobs appear in the menu in the order they're listed. *Custom prompt…* is
always the last option and uses the top-level model.

`model` accepts an alias (`sonnet`, `opus`, `haiku`) or a full model ID.

## Prompt-injection safety

Canvas content goes to Claude as input, so canobs gives Claude nothing to act
with:

- `--tools ""`: no shell, no file access, no web.
- `--strict-mcp-config`: no MCP servers.
- `--setting-sources=`: no CLAUDE.md, memory, hooks or user settings.
- `--no-session-persistence`: no saved session.
- The note goes in on stdin, inside `<note>` tags. The system prompt says it
  is source material, not instructions.
- canobs, not Claude, chooses the output path and writes the file.

So an injected instruction can change the text Claude writes back, but it
can't touch your machine. That leaves one risk: a generated checklist could
contain a wrong or harmful command. Check commands against the source note
(linked at the top of each output file) before you run them.

## Configuration

Per-user settings go in `.env` (see `.env.example`). An exported environment
variable with the same name wins over `.env`.

| Setting | Meaning | Default |
|---|---|---|
| `CANVAS_TOKEN` | Your Canvas access token | required |
| `NOTES_DIR` | Folder notes are saved in and `ask` lists; `~` works on every OS | `~/notes/chas` |

`--dir PATH` on `create` or `ask` overrides `NOTES_DIR` for one run.

These values are constants in the code:

| What | Where |
|---|---|
| Canvas URL | `BASE_URL` in `src/canobs/canvas.py` |
| Course | `COURSE_ID` in `src/canobs/cli.py` |
| Claude timeout | `TIMEOUT` in `src/canobs/agent.py` |

## Project layout

```
src/canobs/
  cli.py                  commands, menus, note naming
  canvas.py               Canvas REST client (stdlib, follows pagination)
  convert.py              Canvas HTML → markdown
  config.py               reads .env / environment (token, notes folder)
  obsidian.py             open via obsidian:// URI, focus on sway
  agent.py                background Claude worker and notifications
  windows.py              reach the Windows desktop (PowerShell) from Windows or WSL
  prompts.py              loads and validates prompts.toml
  prompts.toml            Claude jobs, shared via the repo
```

## Troubleshooting

Canvas problems are reported as one red `✗` line, without a traceback:

- **`CANVAS_TOKEN is not set`:** add it to `.env` in the project folder, or
  export it.
- **`Canvas rejected the token (401)`:** the token has expired or been
  revoked. Create a new one and replace the value in `.env`.
- **`Couldn't reach Canvas`:** you're offline, or Canvas is down.
- **No Claude menu:** `claude` isn't on `PATH`. The rest of canobs works
  without it.
- **"Claude failed" notification:** see `~/.cache/canobs/agent.log`. A common
  cause is an expired Claude Code sign-in. Run `claude auth login`, or use
  `claude setup-token` for a long-lived token.
- **Images don't show in notes:** images uploaded to Canvas need a Canvas
  login, so the image links in your notes won't load.

## License

[MIT](LICENSE). Found a bug or wrote a useful job? Open an issue or a pull
request.
