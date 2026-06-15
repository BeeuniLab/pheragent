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
