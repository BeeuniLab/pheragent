from __future__ import annotations

import re
import uuid


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def slugify(value: str, *, fallback: str = "item") -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or fallback


def tail_text(value: str, *, max_chars: int = 12000) -> str:
    if len(value) <= max_chars:
        return value
    return value[-max_chars:]


def shell_script(body: str) -> str:
    normalized = body.strip() + "\n"
    if normalized.startswith("#!"):
        return normalized
    return "#!/bin/sh\nset -eu\n\n" + normalized
