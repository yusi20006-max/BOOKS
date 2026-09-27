from books.performance import TTLCache,JobQueue,load_test_plan

def test_cache_and_jobs():
 c=TTLCache(1,60); c.set("a",1); assert c.get("a")==1; c.set("b",2); assert c.get("a") is None
 q=JobQueue(); q.submit(lambda x:x+1,1); assert q.run_once()==2
def test_load_plan(): assert load_test_plan(10000)["batch_size"]==1000
