"""Secrets from the process environment and a local `.env` file.

The Mylonics competition token lives here, not in YAML and not in git.
`.env` is gitignored. Existing process environment wins, so CI can inject
values without a file on disk.

Never print the token. ``CompetitionSecrets.__repr__`` only says whether it
is set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from valiant.core.config import repo_root

ENV_FILE = ".env"

TOKEN_KEY = "AEAC_COMP_TOKEN"
URL_KEY = "AEAC_COMP_URL"
UAV_ID_KEY = "AEAC_COMP_UAV_ID"
LIVE_KEY = "AEAC_COMP_LIVE"

DEFAULT_URL = "https://aeac.mylonics.com"
DEFAULT_UAV_ID = "valiant-1"


def env_path() -> Path:
    return repo_root() / ENV_FILE


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines. Quotes optional. Comments and blanks ignored."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    """Load `.env` into ``os.environ`` for keys that are not already set."""
    target = path or env_path()
    if not target.is_file():
        return {}
    parsed = parse_dotenv(target.read_text(encoding="utf-8"))
    for key, value in parsed.items():
        os.environ.setdefault(key, value)
    return parsed


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class CompetitionSecrets:
    token: str | None
    url: str = DEFAULT_URL
    uav_id: str = DEFAULT_UAV_ID
    live: bool = False

    def __repr__(self) -> str:
        return (
            f"CompetitionSecrets(token={'set' if self.token else 'missing'}, "
            f"url={self.url!r}, uav_id={self.uav_id!r}, live={self.live})"
        )


def competition_secrets(*, env_file: Path | None = None) -> CompetitionSecrets:
    load_dotenv(env_file)
    token = (os.environ.get(TOKEN_KEY) or "").strip() or None
    url = (os.environ.get(URL_KEY) or DEFAULT_URL).strip() or DEFAULT_URL
    uav_id = (os.environ.get(UAV_ID_KEY) or DEFAULT_UAV_ID).strip() or DEFAULT_UAV_ID
    live = _truthy(os.environ.get(LIVE_KEY))
    return CompetitionSecrets(token=token, url=url, uav_id=uav_id, live=live)
