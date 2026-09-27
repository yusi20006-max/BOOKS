from books.backup import BackupService
from books.backup_options import BackupSchedule, BackupScheduler
from books.db import Database


def test_backup_scheduler_run_once_is_recoverable(tmp_path):
    source = tmp_path / "books.sqlite3"
    Database(source).migrate()
    destination = tmp_path / "backups" / "latest.sqlite3"
    scheduler = BackupScheduler(
        BackupService(source), BackupSchedule(24), destination
    )
    assert scheduler.run_once() == destination
    assert destination.exists()
    assert destination.with_suffix(".sqlite3.state").exists()
    BackupService(destination).restore_bytes(destination.read_bytes(), overwrite=True)
