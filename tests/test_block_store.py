from __future__ import annotations

import json
from pathlib import Path

from pheragent.block_store import BlockStore
from pheragent.models import CommandBlock, RepoContext


def test_block_store_persists_context_blocks_and_scripts(tmp_path: Path) -> None:
    store = BlockStore(tmp_path / "run")
    context = RepoContext(repo_path=tmp_path, languages=["python"])
    block = CommandBlock(
        id="01-python",
        title="Python",
        goal="Install deps",
        script="#!/bin/sh\necho ok\n",
        order=1,
    )

    store.save_context(context)
    store.write_blocks([block])

    assert json.loads(store.context_path.read_text(encoding="utf-8"))["languages"] == ["python"]
    assert store.script_path("01-python").read_text(encoding="utf-8") == block.script
    assert store.list_blocks()[0].id == "01-python"


def test_block_store_normalizes_source_for_posix_sh(tmp_path: Path) -> None:
    store = BlockStore(tmp_path / "run")
    block = CommandBlock(
        id="01-python",
        title="Python",
        goal="Activate venv",
        script="#!/bin/sh\nset -eu\nsource .venv/bin/activate\npython -m pip --version\n",
        order=1,
    )

    written = store.write_block(block)

    script = store.script_path("01-python").read_text(encoding="utf-8")
    assert "source .venv/bin/activate" not in script
    assert ". .venv/bin/activate" in script
    assert written.script == script


def test_block_store_does_not_rewrite_python_source_assignment_in_heredoc(tmp_path: Path) -> None:
    store = BlockStore(tmp_path / "run")
    block = CommandBlock(
        id="30-python-deps",
        title="Python Dependencies",
        goal="Sanitize requirements",
        script=(
            "#!/bin/sh\n"
            "set -eu\n"
            ".venv/bin/python - requirements.txt <<'PY'\n"
            "from pathlib import Path\n"
            "source = Path('requirements.txt')\n"
            "print(source)\n"
            "PY\n"
        ),
        order=30,
    )

    written = store.write_block(block)

    script = store.script_path("30-python-deps").read_text(encoding="utf-8")
    assert "source = Path('requirements.txt')" in script
    assert ". = Path('requirements.txt')" not in script
    assert written.script == script
