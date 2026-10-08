from books.security import *


def test_secret_redaction_and_validation():
 assert "[REDACTED]" in redact_secrets("api_key=supersecret") and validate_secret("1234567890123456")


def test_cli_token_form_is_redacted():
 redacted = redact_secrets("python -m books.runtime --port 8080 --token hunter2-secret")
 assert "hunter2-secret" not in redacted
 assert "--token [REDACTED]" in redacted
 redacted_eq = redact_secrets("python -m books.runtime --token=hunter2-secret")
 assert "hunter2-secret" not in redacted_eq


def test_bearer_header_is_redacted():
 redacted = redact_secrets("Authorization: Bearer hunter2-secret")
 assert "hunter2-secret" not in redacted
 assert "Bearer [REDACTED]" in redacted


def test_redaction_leaves_innocent_text_alone():
 assert redact_secrets("no secrets here") == "no secrets here"
 assert "books" in redact_secrets("python -m books.runtime --port 8080")
def test_privacy_defaults_are_local():
 p=PrivacyPolicy(); assert not p.cloud_allowed() and p.can_delete(); assert deletion_plan("b1")["delete_related"]
def test_file_mode_validation():
 import os
 import tempfile
 with tempfile.NamedTemporaryFile() as f: harden_file(f.name); assert os.stat(f.name).st_mode & 0o777 == 0o600
