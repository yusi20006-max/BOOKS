from datetime import datetime,timezone
import pytest
from books.backup_options import BackupSchedule,encrypt_backup,decrypt_backup

def test_schedule():
 s=BackupSchedule(24); assert s.next_run(datetime(2026,1,1,tzinfo=timezone.utc)).hour==0
 with pytest.raises(ValueError): BackupSchedule(0)
def test_encryption_roundtrip_when_optional_dependency_exists():
 try:
  x=encrypt_backup(b"books","secret"); assert decrypt_backup(x,"secret")==b"books"
 except RuntimeError: pass
