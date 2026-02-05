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


def get_applied_schema_version() -> str:
    """Read the actually applied schema version from the database.

    Queries the alembic_version table to determine which migration
    has been applied. This may differ from CURRENT_SCHEMA_VERSION
    if migrations are pending.
    """
    from sqlalchemy import create_engine, text

    from app.config import settings

    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).fetchone()
            if row is None:
                return "unknown"
            return row[0]
    finally:
        engine.dispose()


CURRENT_SCHEMA_VERSION = get_current_schema_version()
