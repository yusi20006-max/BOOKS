from books.sync import *


def test_change_and_conflict():
 a=make_change("book","1","update",{"title":"الف"},2); b=make_change("book","1","update",{"title":"ب"},2); c=detect_conflict(a,b); assert c and resolve_conflict(c,"local") is a
def test_queue_and_settings():
 q=SyncQueue(); x=make_change("book","1","create",{}); q.enqueue(x); assert q.drain()==[x] and q.drain()==[]; assert sync_settings({"rtl":True},{"theme":"dark"})=={"theme":"dark","rtl":True}
