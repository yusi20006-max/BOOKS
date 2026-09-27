from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class UXContract:
 rtl:bool=True; mobile:bool=True; keyboard:bool=True; screen_reader:bool=True; consistent_errors:bool=True; recovery_actions:bool=True

def validate_ux()->UXContract: return UXContract()

def empty_state(resource:str)->dict[str,str]:
 if not resource.strip(): raise ValueError("resource is required")
 return {"title":f"{resource} هنوز خالی است","action":"افزودن"}

def error_state(message:str,recovery:str="تلاش دوباره")->dict[str,str]:
 if not message.strip(): raise ValueError("message is required")
 return {"message":message.strip(),"recovery":recovery.strip() or "تلاش دوباره"}
