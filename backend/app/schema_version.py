"""Automatic schema version detection from Alembic migrations."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def get_current_schema_version() -> str:
    """Derive the current schema version from Alembic's head revision automatically.

    Scans the alembic/versions/ directory and returns the head revision ID.
    This means CURRENT_SCHEMA_VERSION stays in sync with migrations without
    any manual updates.
    """
    alembic_cfg = Config()
    alembic_cfg.set_main_option(
        "script_location",
        str(Path(__file__).parent.parent / "alembic"),
    )
    script = ScriptDirectory.from_config(alembic_cfg)
    head = script.get_current_head()
    if head is None:
        raise RuntimeError("No Alembic migrations found")
    return head


CURRENT_SCHEMA_VERSION = get_current_schema_version()
