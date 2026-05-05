"""
Lightweight .env loader + typed access to required environment variables.

Avoids the python-dotenv dependency. Parses `KEY=VALUE` lines from the pipeline's
`.env` file (located alongside `pyproject.toml`), strips common paste artifacts
(angle brackets, surrounding quotes, whitespace), and overlays values on top of
`os.environ` so real env vars still win.

Usage:
    from lib.config import THEGRAPH_API_KEY
    # Raises a clear error at import time if the key isn't set.

Or query optional config:
    from lib.config import get
    foo = get("FOO", default="bar")
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path


# Strip surrounding quotes, angle brackets, and whitespace from a value.
# Examples that all parse to "abc123":
#   "abc123"          (quotes)
#   '<abc123>'        (angle brackets — common from copy-pasting placeholder)
#   ` abc123 \n`      (leading/trailing whitespace)
_STRIP_PATTERN = re.compile(r'^[\s<"\']*(.*?)[\s>"\']*$', re.DOTALL)


def _env_path() -> Path:
    """Resolve the project's .env path: same dir as pyproject.toml."""
    return Path(__file__).resolve().parents[1] / ".env"


@lru_cache(maxsize=1)
def _parse_env_file() -> dict[str, str]:
    """Parse the .env file once, lazily, on first access."""
    path = _env_path()
    if not path.exists():
        return {}
    parsed: dict[str, str] = {}
    for line_num, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            # Tolerate malformed lines silently to avoid breaking on user edits.
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
            continue  # not a conventional env var name
        m = _STRIP_PATTERN.match(value)
        clean = m.group(1) if m else value.strip()
        parsed[key] = clean
    return parsed


def get(name: str, default: str | None = None) -> str | None:
    """Read a config value: real env first, then .env file, then default."""
    if name in os.environ:
        return os.environ[name]
    return _parse_env_file().get(name, default)


def require(name: str) -> str:
    """Read a required config value or raise a clear error."""
    value = get(name)
    if not value:
        env_path = _env_path()
        example_path = env_path.parent / ".env.example"
        raise RuntimeError(
            f"Missing required env var {name!r}. "
            f"Set it in the environment or in {env_path} "
            f"(see {example_path} for format)."
        )
    return value


# ── named accessors for required values ──────────────────────────────────────
# Lazy — collectors that don't need TheGraph (peg, supply, scorecard, etc.)
# can still import this module without an API key configured.

def thegraph_api_key() -> str:
    """The Graph gateway API key. Raises if unset. See `.env.example`."""
    return require("THEGRAPH_API_KEY")


def etherscan_api_key() -> str:
    """Etherscan API key (V2 multichain). Raises if unset. See `.env.example`."""
    return require("ETHERSCAN_API_KEY")
