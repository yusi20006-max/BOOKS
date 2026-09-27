from dataclasses import dataclass

from books.scanner import BarcodeScanner


@dataclass
class Decoded:
    text: str


def test_scanner_extracts_isbn13_from_barcode_text():
    scanner = BarcodeScanner(
        decoder=lambda image: [Decoded("ISBN 978-0-15-601219-5")],
    )
    result = scanner.scan(object())

    assert result.isbn == "9780156012195"
    assert result.format == "ISBN-13"


def test_scanner_extracts_valid_isbn10():
    scanner = BarcodeScanner(
        decoder=lambda image: [Decoded("0140328726")],
    )
    result = scanner.scan(object())

    assert result.isbn == "0140328726"
    assert result.format == "ISBN-10"


def test_scanner_rejects_invalid_isbn():
    scanner = BarcodeScanner(
        decoder=lambda image: [Decoded("9780156012196")],
    )
    result = scanner.scan(object())

    assert result.isbn is None
    assert result.error == "no valid ISBN barcode found"


def test_scanner_isolates_decoder_failure():
    scanner = BarcodeScanner(
        decoder=lambda image: (_ for _ in ()).throw(RuntimeError("decoder down")),
    )
    result = scanner.scan(object())

    assert result.isbn is None
    assert result.error == "decoder down"


def test_default_decoder_reports_optional_dependency(monkeypatch):
    def fail_import(name, *args, **kwargs):
        if name == "zxingcpp":
            raise ImportError("zxingcpp unavailable")
        return original_import(name, *args, **kwargs)

    import builtins
    original_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", fail_import)

    result = BarcodeScanner().scan(object())

    assert result.isbn is None
    assert result.error == "barcode decoder is not installed; install BOOKS with the [barcode] extra"
