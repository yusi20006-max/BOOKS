import json
import threading
import urllib.request

from books.runtime import create_server
from books.sync import RemoteSyncClient, SyncQueue, flush_queue, make_change

def test_persistent_queue_survives_restart(tmp_path):
    path=tmp_path/"sync.sqlite3"; change=make_change("book","1","update",{"title":"الف"})
    assert SyncQueue(path).enqueue(change)
    assert not SyncQueue(path).enqueue(change)
    assert SyncQueue(path).drain()==[change]

def test_remote_push_applies_and_is_idempotent(tmp_path):
    server=create_server("127.0.0.1",0,str(tmp_path/"books.sqlite3")); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        queue=SyncQueue(tmp_path/"sync.sqlite3"); queue.enqueue(make_change("book","1","create",{"title":"الف"}))
        client=RemoteSyncClient(f"http://127.0.0.1:{server.server_port}")
        assert flush_queue(queue,client)==1 and queue.pending_count()==0
        assert flush_queue(queue,client)==0
        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/v1/sync/changes?since=0") as r:
            body=json.loads(r.read())
        assert body["changes"][0]["entity_id"]=="1"
    finally: server.shutdown(); thread.join(timeout=3)

def test_pull_change_can_be_applied_to_second_device(tmp_path):
    first=create_server("127.0.0.1",0,str(tmp_path/"one.sqlite3")); second=create_server("127.0.0.1",0,str(tmp_path/"two.sqlite3"))
    threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (first,second)]
    for t in threads:t.start()
    try:
        change=make_change("book","2","create",{"title":"دو"})
        client=RemoteSyncClient(f"http://127.0.0.1:{second.server_port}")
        assert client.push(change)["applied"] is True
        assert client.push(change)["applied"] is False
    finally:
        for s in (first,second): s.shutdown()
        for t in threads:t.join(timeout=3)
