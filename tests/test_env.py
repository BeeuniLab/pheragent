from __future__ import annotations

import os
from pathlib import Path

from pheragent.env import load_dotenv


def test_load_dotenv_sets_missing_keys_without_overriding(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
# comment
OPENAI_BASE_URL="https://example.test/v1"
OPENAI_API_KEY=from-file
export PHERAGENT_MODEL='gpt-5.5'
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "already-set")

    loaded = load_dotenv(env_file)

    assert loaded == ["OPENAI_BASE_URL", "PHERAGENT_MODEL"]
    assert os.environ["OPENAI_BASE_URL"] == "https://example.test/v1"
    assert os.environ["OPENAI_API_KEY"] == "already-set"
    assert os.environ["PHERAGENT_MODEL"] == "gpt-5.5"
