"""Background scheduler for automated backups.

Uses a plain asyncio loop — no external scheduler library needed.
The loop reads the schedule from the database, sleeps until the next
backup is due, then calls backup_service.create_backup() in an executor.
An asyncio.Event allows the API to wake the loop when settings change.
"""

import asyncio
import logging
from datetime import UTC, datetime, time, timedelta

from app.database import SessionLocal
from app.models.backup_schedule import BackupSchedule
from app.services import backup_service

logger = logging.getLogger(__name__)

# Signaling event: set by the API to wake the loop on config change
_reconfigure_event = asyncio.Event()


def signal_reconfigure():
    """Wake the scheduler loop so it re-reads settings from the database."""
    _reconfigure_event.set()


def _get_schedule() -> dict | None:
    """Read the schedule row from the database (outside request context)."""
    db = SessionLocal()
    try:
        row = db.query(BackupSchedule).filter(BackupSchedule.id == 1).first()
        if row is None:
            return None
        return {
            "enabled": row.enabled,
            "interval_hours": row.interval_hours,
            "max_backups": row.max_backups,
            "last_backup_at": row.last_backup_at,
            "next_backup_at": row.next_backup_at,
            "preferred_time": row.preferred_time,
        }
    finally:
        db.close()


def _update_after_backup(next_at: datetime):
    """Update last_backup_at and next_backup_at after a successful backup."""
    db = SessionLocal()
    try:
        row = db.query(BackupSchedule).filter(BackupSchedule.id == 1).first()
        if row:
            row.last_backup_at = datetime.now(UTC)
            row.next_backup_at = next_at
            row.updated_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()


def _compute_next_backup(interval: timedelta, preferred: time) -> datetime:
    """Compute next backup time, aligned to preferred_time for intervals >= 24h."""
    now = datetime.now(UTC)
    if interval >= timedelta(hours=24):
        # Align to preferred time of day
        candidate = now.replace(hour=preferred.hour, minute=preferred.minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        # For intervals > 24h, step forward in interval-sized increments
        days = int(interval.total_seconds() // 86400)
        if days > 1:
            candidate += timedelta(days=days - 1)
        return candidate
    else:
        return now + interval


def _run_backup(max_backups: int):
    """Synchronous: create backup and enforce retention."""
    try:
        backup_service.create_backup()
        backup_service.enforce_retention(max_backups)
        logger.info("Scheduled backup completed successfully")
    except Exception:
        logger.exception("Scheduled backup failed")


async def backup_scheduler_loop():
    """Main scheduler loop. Runs as an asyncio background task."""
    logger.info("Backup scheduler started")

    while True:
        try:
            schedule = _get_schedule()

            if schedule is None or not schedule["enabled"]:
                # Disabled or no config: wait until reconfigured
                logger.debug("Backup scheduler disabled, waiting for reconfiguration")
                _reconfigure_event.clear()
                await _reconfigure_event.wait()
                _reconfigure_event.clear()
                continue

            # Compute when to run next
            now = datetime.now(UTC)
            interval = timedelta(hours=schedule["interval_hours"])

            if schedule["next_backup_at"] and schedule["next_backup_at"].tzinfo:
                next_at = schedule["next_backup_at"]
            elif schedule["last_backup_at"] and schedule["last_backup_at"].tzinfo:
                next_at = schedule["last_backup_at"] + interval
            else:
                # No previous backup — run immediately
                next_at = now

            seconds_to_wait = max(0, (next_at - now).total_seconds())

            if seconds_to_wait > 0:
                logger.info(f"Next backup scheduled at {next_at.isoformat()} ({seconds_to_wait:.0f}s)")
                try:
                    _reconfigure_event.clear()
                    await asyncio.wait_for(_reconfigure_event.wait(), timeout=seconds_to_wait)
                    # Event was set — settings changed, re-read
                    _reconfigure_event.clear()
                    continue
                except TimeoutError:
                    # Timeout reached — time to run the backup
                    pass

            # Run backup in executor (blocking subprocess)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _run_backup, schedule["max_backups"])

            # Update timestamps
            preferred = schedule.get("preferred_time") or time(3, 0)
            new_next = _compute_next_backup(interval, preferred)
            _update_after_backup(new_next)

        except asyncio.CancelledError:
            logger.info("Backup scheduler shutting down")
            raise
        except Exception:
            logger.exception("Unexpected error in backup scheduler, retrying in 60s")
            await asyncio.sleep(60)
