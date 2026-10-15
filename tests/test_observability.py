import json
import logging
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from books.db import BookRepository, Database
from books.observability import configure_logging, log_event
from books.runtime import Runtime, create_server, make_handler


def test_log_event_is_json_and_allow_lists_fields(caplog):
    with caplog.at_level(logging.INFO, logger="books.runtime"):
        log_event("INFO", "test_event", request_id="abc123", route="/health",
                  secret="do-not-log", query="private-search-term")
    record = json.loads(caplog.records[-1].message)
    assert record["event"] == "test_event"
    assert record["request_id"] == "abc123"
    assert record["route"] == "/health"
    assert "secret" not in record and "query" not in record
    assert "do-not-log" not in caplog.text
    assert "private-search-term" not in caplog.text


def test_configure_logging_rejects_unknown_level():
    import pytest
    with pytest.raises(ValueError, match="BOOKS_LOG_LEVEL"):
        configure_logging("VERBOSE")


def test_http_logs_request_id_and_safe_route_without_query_or_token(tmp_path, caplog):
    server = create_server("127.0.0.1", 0, str(tmp_path / "books.sqlite3"), token="sentinel-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with caplog.at_level(logging.INFO, logger="books.runtime"):
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            connection.request("GET", "/v1/books?private_query=private-search-term",
                               headers={"Authorization": "Bearer sentinel-token"})
            response = connection.getresponse()
            response.read()
            request_id = response.getheader("X-Request-ID")
            assert response.status == 200
            connection.close()
        assert request_id
        events = [json.loads(row.message) for row in caplog.records if row.name == "books.runtime"]
        request_event = next(event for event in events if event["event"] == "http_request")
        assert request_event["request_id"] == request_id
        assert request_event["route"] == "/v1/books"
        assert request_event["status"] == 200
        assert "sentinel-token" not in caplog.text
        assert "private-search-term" not in caplog.text
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def test_unexpected_http_error_is_diagnosable_without_exception_text(tmp_path, caplog):
    db = Database(tmp_path / "books.sqlite3")
    db.migrate()
    runtime = Runtime(BookRepository(db), token="sentinel-token", database=db)

    def fail_list(*args, **kwargs):
        raise RuntimeError("private database path and sentinel exception text")

    runtime.api.repo.list = fail_list
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(runtime))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with caplog.at_level(logging.INFO, logger="books.runtime"):
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            connection.request("GET", "/v1/books", headers={"Authorization": "Bearer sentinel-token"})
            response = connection.getresponse()
            payload = json.loads(response.read())
            request_id = response.getheader("X-Request-ID")
            connection.close()
        assert response.status == 500
        assert payload == {"error": "internal error"}
        assert request_id
        events = [json.loads(row.message) for row in caplog.records if row.name == "books.runtime"]
        failure = next(event for event in events if event["event"] == "http_request_failed")
        assert failure["error_type"] == "RuntimeError"
        assert failure["request_id"] == request_id
        assert "sentinel-token" not in caplog.text
        assert "private database path" not in caplog.text
        assert "sentinel exception text" not in caplog.text
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()
