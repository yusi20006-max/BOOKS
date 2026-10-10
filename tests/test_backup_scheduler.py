import json

import pytest

from books.backup import BackupService
from books.backup_options import BackupSchedule, BackupScheduler
from books.db import Database


def test_backup_scheduler_run_once_is_recoverable(tmp_path):
    source=tmp_path/"books.sqlite3"; Database(source).migrate()
    destination=tmp_path/"backups"/"latest.sqlite3"
    scheduler=BackupScheduler(BackupService(source),BackupSchedule(24),destination)
    assert scheduler.run_once()==destination and destination.exists()
    assert destination.with_suffix(".sqlite3.state").exists()
    BackupService(destination).restore_bytes(destination.read_bytes(),overwrite=True)

def test_backup_scheduler_records_failure_without_destroying_last_backup(tmp_path):
    source=tmp_path/"books.sqlite3"; Database(source).migrate()
    destination=tmp_path/"backups"/"latest.sqlite3"
    scheduler=BackupScheduler(BackupService(source),BackupSchedule(24),destination)
    scheduler.run_once()
    class Broken:
        def create_backup_bytes(self): raise OSError("disk unavailable")
    scheduler.service=Broken()
    assert scheduler.run_once_recovering() is None
    assert destination.exists()
    state=json.loads(scheduler.state_path.read_text())
    assert state["status"]=="error"

def test_backup_scheduler_rejects_invalid_retention(tmp_path):
    with pytest.raises(ValueError):
        BackupScheduler(BackupService(tmp_path/"x.sqlite3"),BackupSchedule(24),tmp_path/"x",retention=0)


def test_runtime_starts_and_stops_configured_backup_scheduler(tmp_path, monkeypatch):
    from books.runtime import create_server

    monkeypatch.delenv("BOOKS_BACKUP_PATH", raising=False)
    destination = tmp_path / "scheduled" / "latest.sqlite3"
    server = create_server(
        "127.0.0.1", 0, str(tmp_path / "books.sqlite3"),
        backup_path=str(destination), backup_interval_hours=24, backup_retention=2,
    )
    try:
        assert server.backup_scheduler is not None
        assert server.backup_scheduler._thread is not None
        assert server.backup_scheduler._thread.is_alive()
        assert server.backup_scheduler.run_once() == destination
        snapshots = list(destination.parent.glob("latest-*.sqlite3"))
        assert len(snapshots) == 1
        assert destination.stat().st_mode & 0o777 == 0o600
        assert snapshots[0].stat().st_mode & 0o777 == 0o600
    finally:
        server.server_close()
    assert not server.backup_scheduler._thread.is_alive()


def test_runtime_rejects_invalid_backup_schedule_configuration(tmp_path, monkeypatch):
    from books.runtime import create_server

    monkeypatch.delenv("BOOKS_BACKUP_PATH", raising=False)
    with pytest.raises(ValueError, match="invalid scheduled backup configuration"):
        create_server(
            "127.0.0.1", 0, str(tmp_path / "books.sqlite3"),
            backup_path=str(tmp_path / "backups" / "latest.sqlite3"),
            backup_interval_hours=0,
        )


def test_backup_scheduler_retains_only_newest_timestamped_snapshots(tmp_path):
    source = tmp_path / "books.sqlite3"
    Database(source).migrate()
    destination = tmp_path / "backups" / "latest.sqlite3"
    scheduler = BackupScheduler(BackupService(source), BackupSchedule(24), destination, retention=2)
    for _ in range(4):
        scheduler.run_once()
    assert destination.exists()
    assert len(list(destination.parent.glob("latest-*.sqlite3"))) == 2
