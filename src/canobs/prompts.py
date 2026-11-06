"""Claude job prompts, loaded from prompts.toml next to this file."""
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROMPTS_FILE = Path(__file__).with_name("prompts.toml")


@dataclass
class Job:
    name: str
    file: str
    prompt: str
    model: str | None = None  # overrides Prompts.model for this job


@dataclass
class Prompts:
    system: str
    jobs: list[Job]
    model: str | None = None  # None = Claude Code's default model

    def model_for(self, job: Job | None) -> str | None:
        return (job.model if job else None) or self.model


class PromptsError(Exception):
    pass


def load() -> Prompts:
    """Read and validate the prompts file."""
    try:
        data = tomllib.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise PromptsError(f"{PROMPTS_FILE}: {e}") from e

    system = str(data.get("system", "")).strip()
    if not system:
        raise PromptsError(f"{PROMPTS_FILE}: 'system' is missing or empty")

    jobs = []
    for i, raw in enumerate(data.get("job", []), 1):
        missing = [k for k in ("name", "file", "prompt") if not str(raw.get(k, "")).strip()]
        if missing:
            raise PromptsError(f"{PROMPTS_FILE}: job #{i} is missing {', '.join(missing)}")
        if not re.fullmatch(r"[a-z0-9-]+", raw["file"]):
            raise PromptsError(
                f"{PROMPTS_FILE}: job '{raw['name']}': file must be lowercase letters, digits or -"
            )
        jobs.append(Job(
            raw["name"].strip(), raw["file"], raw["prompt"].strip(),
            _model(raw.get("model"), f"job '{raw['name']}'"),
        ))
    return Prompts(system, jobs, _model(data.get("model"), "model"))


def _model(value, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._\[\]-]+", value.strip()):
        raise PromptsError(f"{PROMPTS_FILE}: {where}: model must be a model name like 'sonnet'")
    return value.strip()
