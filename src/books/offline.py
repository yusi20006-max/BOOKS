from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OfflineCapabilities:
    view=True
    search=True
    edit=True
    delete=True
    reading=True
    notes=True
    backup=True
    discovery=False
    enrichment=False
    ai_cloud=False
    sync=False

def local_capabilities() -> OfflineCapabilities:
    return OfflineCapabilities()
