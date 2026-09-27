from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
import csv
import io
import json


@dataclass(frozen=True,slots=True)
class ReadingMetric:
 day:date; minutes:int; pages:int

def reading_analytics(metrics:Iterable[ReadingMetric],start:date|None=None,end:date|None=None)->dict[str,int]:
 rows=[m for m in metrics if (start is None or m.day>=start) and (end is None or m.day<=end)]
 return {"sessions":len(rows),"minutes":sum(m.minutes for m in rows),"pages":sum(m.pages for m in rows)}

def inventory_analytics(rows:Iterable[dict])->dict[str,int]:
 items=list(rows); return {"books":len(items),"with_isbn":sum(bool(x.get("isbn10") or x.get("isbn13")) for x in items),"with_cover":sum(bool(x.get("cover_url")) for x in items)}

def report_json(data:dict)->str: return json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)
def report_csv(rows:Iterable[dict])->str:
 rows=list(rows); fields=sorted({k for row in rows for k in row})
 out=io.StringIO(); w=csv.DictWriter(out,fieldnames=fields); w.writeheader(); w.writerows(rows); return out.getvalue()

def report_excel(rows:Iterable[dict])->bytes:
 try:
  from openpyxl import Workbook
 except ImportError as exc: raise RuntimeError("openpyxl is required for Excel reports") from exc
 rows=list(rows); wb=Workbook(); ws=wb.active; fields=sorted({k for row in rows for k in row}); ws.append(fields)
 for row in rows: ws.append([row.get(k) for k in fields])
 out=io.BytesIO(); wb.save(out); return out.getvalue()

def report_pdf(rows:Iterable[dict])->bytes:
 try:
  from reportlab.pdfgen.canvas import Canvas
 except ImportError as exc: raise RuntimeError("reportlab is required for PDF reports") from exc
 out=io.BytesIO(); c=Canvas(out); y=800
 for row in rows:
  c.drawString(40,y,str(row)[:110]); y-=16
  if y<40: c.showPage(); y=800
 c.save(); return out.getvalue()
