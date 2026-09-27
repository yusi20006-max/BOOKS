from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from time import monotonic


@dataclass(slots=True)
class TTLCache:
 capacity: int = 256
 ttl: float = 60.0
 data: OrderedDict = field(init=False, repr=False)
 def get(self,key):
  item=self.data.get(key)
  if item is None: return None
  value,expires=item
  if monotonic()>expires: self.data.pop(key,None); return None
  self.data.move_to_end(key); return value
 def set(self,key,value):
  self.data[key]=(value,monotonic()+self.ttl); self.data.move_to_end(key)
  while len(self.data)>self.capacity: self.data.popitem(last=False)

class JobQueue:
 def __init__(self): self.jobs=[]
 def submit(self,fn,*args,**kwargs): self.jobs.append((fn,args,kwargs))
 def run_once(self):
  if not self.jobs: return None
  fn,args,kwargs=self.jobs.pop(0); return fn(*args,**kwargs)

def configure_logging(level=logging.INFO): logging.basicConfig(level=level,format="%(asctime)s %(levelname)s %(name)s %(message)s")

def load_test_plan(record_count:int)->dict[str,int]:
 if record_count<1: raise ValueError("record_count must be positive")
 return {"records":record_count,"batch_size":1000,"max_memory_mb":256}
