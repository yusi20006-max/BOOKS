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


def test_scheduler_restores_remaining_delay_after_runtime_restart(tmp_path):
    from datetime import datetime, timedelta, timezone

    source = tmp_path / "books.sqlite3"
    Database(source).migrate()
    destination = tmp_path / "backups" / "latest.sqlite3"
    scheduler = BackupScheduler(BackupService(source), BackupSchedule(24), destination)
    now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    scheduler.state_path.parent.mkdir(parents=True)
    scheduler.state_path.write_text(
        json.dumps({"last_run": (now - timedelta(hours=2)).isoformat(), "status": "ok"}),
        encoding="utf-8",
    )
    assert scheduler._seconds_until_next_run(now) == pytest.approx(22 * 3600)


def test_scheduler_uses_full_interval_when_no_successful_run_is_recorded(tmp_path):
    source = tmp_path / "books.sqlite3"
    Database(source).migrate()
    scheduler = BackupScheduler(
        BackupService(source), BackupSchedule(6), tmp_path / "backups" / "latest.sqlite3"
    )
    assert scheduler._seconds_until_next_run() == 6 * 3600


@pytest.mark.parametrize("interval", [True, 0, -1, 1.5, "24"])
def test_backup_schedule_rejects_non_positive_or_non_integer_intervals(interval):
    with pytest.raises(ValueError, match="positive integer"):
        BackupSchedule(interval)


@pytest.mark.parametrize("retention", [True, 0, -1, 1.5, "5"])
def test_backup_scheduler_rejects_non_integer_retention(tmp_path, retention):
    with pytest.raises(ValueError, match="positive integer"):
        BackupScheduler(
            BackupService(tmp_path / "missing.sqlite3"),
            BackupSchedule(24),
            tmp_path / "backups" / "latest.sqlite3",
            retention=retention,
        )


def test_concurrent_manual_runs_are_serialized_and_keep_unique_snapshots(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    source = tmp_path / "books.sqlite3"
    Database(source).migrate()
    destination = tmp_path / "backups" / "latest.sqlite3"
    scheduler = BackupScheduler(
        BackupService(source), BackupSchedule(24), destination, retention=10
    )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: scheduler.run_once(), range(4)))

    assert results == [destination] * 4
    snapshots = list(destination.parent.glob("latest-*.sqlite3"))
    assert len(snapshots) == 4
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in snapshots)
    assert destination.stat().st_mode & 0o777 == 0o600
    assert json.loads(scheduler.state_path.read_text(encoding="utf-8"))["status"] == "ok"


def test_pruning_ignores_symlinks_and_directories(tmp_path):
    source = tmp_path / "books.sqlite3"
    Database(source).migrate()
    destination = tmp_path / "backups" / "latest.sqlite3"
    scheduler = BackupScheduler(BackupService(source), BackupSchedule(24), destination, retention=1)
    scheduler.run_once()
    outside = tmp_path / "keep.sqlite3"
    outside.write_bytes(b"do not delete")
    link = destination.parent / "latest-000-symlink.sqlite3"
    directory = destination.parent / "latest-000-directory.sqlite3"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")
    directory.mkdir()
    scheduler.run_once()
    assert outside.read_bytes() == b"do not delete"
    assert link.is_symlink()
    assert directory.is_dir()

def test_background_scheduler_runs_backup_when_timer_expires(tmp_path, monkeypatch):
    import threading

    source = tmp_path / "books.sqlite3"
    Database(source).migrate()
    destination = tmp_path / "backups" / "latest.sqlite3"
    scheduler = BackupScheduler(BackupService(source), BackupSchedule(1), destination)
    completed = threading.Event()
    original_run = scheduler.run_once_recovering

    def run_due_backup():
        result = original_run()
        if result is not None:
            completed.set()
        # Keep this test deterministic: the worker exits after its first due run.
        scheduler._stop.set()
        return result

    # Exercise the real background loop and Event.wait path without waiting an hour.
    monkeypatch.setattr(scheduler, "_seconds_until_next_run", lambda: 0.01)
    monkeypatch.setattr(scheduler, "run_once_recovering", run_due_backup)
    scheduler.start()
    try:
        assert completed.wait(timeout=3), "scheduled worker did not create a backup"
        assert destination.is_file()
        state = json.loads(scheduler.state_path.read_text(encoding="utf-8"))
        assert state["status"] == "ok"
        assert state["last_run"]
        assert len(list(destination.parent.glob("latest-*.sqlite3"))) == 1
    finally:
        scheduler.stop()

    assert scheduler._thread is not None
    assert not scheduler._thread.is_alive()
