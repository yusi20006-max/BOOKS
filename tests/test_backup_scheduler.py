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
