from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

class ChangeType(str,Enum): CREATE="create"; UPDATE="update"; DELETE="delete"
@dataclass(frozen=True,slots=True)
class Change:
 id:str; entity:str; entity_id:str; operation:ChangeType; version:int; payload:dict; changed_at:str
@dataclass(frozen=True,slots=True)
class Conflict:
 entity:str; entity_id:str; local:Change; remote:Change

def make_change(entity,entity_id,operation,payload,version=1): return Change(entity+":"+entity_id+":"+str(version),entity,entity_id,ChangeType(operation),version,payload,datetime.now(timezone.utc).isoformat())

def detect_conflict(local:Change,remote:Change)->Conflict|None:
 if local.entity==remote.entity and local.entity_id==remote.entity_id and local.version==remote.version and local.payload!=remote.payload: return Conflict(local.entity,local.entity_id,local,remote)
 return None

def resolve_conflict(conflict:Conflict,strategy:str)->Change:
 if strategy not in {"local","remote"}: raise ValueError("strategy must be local or remote")
 return conflict.local if strategy=="local" else conflict.remote

class SyncQueue:
 def __init__(self): self._items=[]
 def enqueue(self,change:Change): self._items.append(change)
 def drain(self)->list[Change]: items=list(self._items); self._items.clear(); return items

def sync_settings(local:dict,remote:dict)->dict: return dict(remote)|{k:v for k,v in local.items() if k not in remote}
