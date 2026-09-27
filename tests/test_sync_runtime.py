import threading

from books.runtime import create_server
from books.sync import RemoteSyncClient, SyncQueue, flush_queue, make_change


def test_persistent_queue_survives_restart(tmp_path):
    path = tmp_path / "sync.sqlite3"
    change = make_change("book", "1", "update", {"title": "الف"})
    first = SyncQueue(path)
    assert first.enqueue(change)
    assert not first.enqueue(change)
    second = SyncQueue(path)
    assert second.drain() == [change]


def test_remote_push_and_idempotent_flush(tmp_path):
    server = create_server("127.0.0.1", 0, str(tmp_path / "books.sqlite3"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        queue = SyncQueue(tmp_path / "sync.sqlite3")
        queue.enqueue(make_change("book", "1", "update", {"title": "الف"}))
        client = RemoteSyncClient(f"http://127.0.0.1:{server.server_port}")
        assert flush_queue(queue, client) == 1
        assert queue.pending_count() == 0
    finally:
        server.shutdown()
        thread.join(timeout=3)
