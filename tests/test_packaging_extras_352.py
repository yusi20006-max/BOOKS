"""Regression tests for Audit/P2 #352 optional packaging extras."""

import tomllib
from pathlib import Path
from unittest.mock import patch


def test_extras_declared_in_metadata():
    data = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_bytes().decode())
    extras = data["project"]["optional-dependencies"]
    assert set(extras["crypto"]) != set()
    assert any("cryptography" in r for r in extras["crypto"])
    assert any("openpyxl" in r for r in extras["excel"])
    assert any("reportlab" in r for r in extras["pdf"])
    assert any("openpyxl" in r for r in extras["reports"])
    assert any("reportlab" in r for r in extras["reports"])
    assert "barcode" in extras


def test_crypto_error_names_extra():
    from books import backup_options

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "cryptography.fernet":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        try:
            backup_options.encrypt_backup(b"data", "pw")
        except RuntimeError as exc:
            assert "[crypto]" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


def test_report_errors_name_extras():
    from books import reports

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name in {"openpyxl", "reportlab.pdfgen.canvas"}:
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        try:
            reports.report_excel([{"a": 1}])
        except RuntimeError as exc:
            assert "[excel]" in str(exc)
        else:
            raise AssertionError("expected RuntimeError for excel")
        try:
            reports.report_pdf([{"a": 1}])
        except RuntimeError as exc:
            assert "[pdf]" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


def test_readme_lists_all_extras():
    text = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    for extra in ("[barcode]", "[crypto]", "[excel]", "[pdf]", "[reports]"):
        assert extra in text, extra
