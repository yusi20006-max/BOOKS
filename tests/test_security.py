from books.security import *

def test_secret_redaction_and_validation():
 assert "[REDACTED]" in redact_secrets("api_key=supersecret") and validate_secret("1234567890123456")
def test_privacy_defaults_are_local():
 p=PrivacyPolicy(); assert not p.cloud_allowed() and p.can_delete(); assert deletion_plan("b1")["delete_related"]
def test_file_mode_validation():
 import tempfile,os
 with tempfile.NamedTemporaryFile() as f: harden_file(f.name); assert os.stat(f.name).st_mode & 0o777 == 0o600
