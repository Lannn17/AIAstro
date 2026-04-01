"""
Seeds prompt_versions with v1 entries from prompt_registry.
Runs at startup. Skips callers that already have a deployed version.
"""
import uuid
from datetime import datetime, timezone

from .db import db_get_deployed_version, db_insert_prompt_version


def seed_prompt_versions() -> None:
    from .rag.prompt_registry import PROMPTS

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for caller, cfg in PROMPTS.items():
        existing = db_get_deployed_version(caller)
        if existing:
            continue
        id_ = uuid.uuid4().hex[:16]
        db_insert_prompt_version(
            id_=id_,
            caller=caller,
            version_tag="v1",
            prompt_text=cfg["prompt_template"],
            system_instruction=cfg.get("system_instruction") or "",
            status="deployed",
            deployed_at=now,
        )
        print(f"[Seed] Seeded prompt_versions: {caller} v1")