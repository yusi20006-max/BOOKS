from __future__ import annotations
import os
import re
from dataclasses import dataclass


_SECRET_PATTERNS=(re.compile(r"(?i)(token|secret|password|api[_-]?key)(\\s*[=:]\\s*)[^\\s,]+"),)
def redact_secrets(text:str)->str:
 out=text
 for p in _SECRET_PATTERNS: out=p.sub(lambda m:m.group(1)+m.group(2)+"[REDACTED]",out)
 return out

def validate_secret(value:str|None)->bool: return bool(value and len(value)>=16)

def harden_file(path:str,mode:int=0o600)->None: os.chmod(path,mode)
@dataclass(frozen=True,slots=True)
class PrivacyPolicy:
 allow_cloud_ai:bool=False; allow_sync:bool=False; retain_deleted:bool=False
 def can_delete(self)->bool: return True
 def cloud_allowed(self)->bool: return self.allow_cloud_ai

def deletion_plan(entity_id:str)->dict[str,object]:
 if not entity_id.strip(): raise ValueError("entity id is required")
 return {"entity_id":entity_id,"delete_related":True,"audit_retention":"minimal"}
