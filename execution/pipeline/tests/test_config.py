"""Offline tests for the .env loader."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from lib import config


@pytest.fixture(autouse=True)
def _reset_env_cache():
    """
    The lru_cache on _parse_env_file persists across tests. Ensure each test
    starts fresh and post-test the real .env state is restored — otherwise
    test_subgraph (online) sees the patched state from these tests.
    """
    config._parse_env_file.cache_clear()
    yield
    config._parse_env_file.cache_clear()


def test_strip_pattern_handles_paste_artifacts(tmp_path: Path):
    """Verify the loader strips angle brackets, quotes, and whitespace."""
    fake_env = tmp_path / ".env"
    fake_env.write_text(
        "THEGRAPH_API_KEY=  <abc123>  \n"
        "QUOTED='hello'\n"
        "DOUBLE_QUOTED=\"world\"\n"
        "# this is a comment\n"
        "MALFORMED no equals\n"
        "lower_case_skipped=value\n"
    )

    with patch.object(config, "_env_path", return_value=fake_env):
        config._parse_env_file.cache_clear()
        parsed = config._parse_env_file()

    assert parsed["THEGRAPH_API_KEY"] == "abc123"
    assert parsed["QUOTED"] == "hello"
    assert parsed["DOUBLE_QUOTED"] == "world"
    assert "lower_case_skipped" not in parsed
    assert "MALFORMED no equals" not in parsed


def test_real_env_var_overrides_dotenv(tmp_path: Path):
    """Real os.environ values must take precedence over .env file."""
    fake_env = tmp_path / ".env"
    fake_env.write_text("FOO=from_dotenv\n")

    with patch.object(config, "_env_path", return_value=fake_env), \
         patch.dict(os.environ, {"FOO": "from_env"}, clear=False):
        config._parse_env_file.cache_clear()
        assert config.get("FOO") == "from_env"


def test_require_raises_clear_error_for_missing(tmp_path: Path):
    """A missing required var should raise with a clear, actionable message."""
    fake_env = tmp_path / ".env"
    fake_env.write_text("")

    with patch.object(config, "_env_path", return_value=fake_env):
        config._parse_env_file.cache_clear()
        try:
            config.require("NOPE_NEVER_SET")
        except RuntimeError as e:
            assert "NOPE_NEVER_SET" in str(e)
            assert ".env" in str(e)
        else:
            assert False, "require() should have raised"
