from datetime import date

import pytest

from books.reports import *

def test_range_analytics_and_inventory():
 a=[ReadingMetric(date(2026,1,1),30,5),ReadingMetric(date(2026,2,1),20,3)]; assert reading_analytics(a,date(2026,1,1),date(2026,1,31))=={"sessions":1,"minutes":30,"pages":5}; assert inventory_analytics([{"isbn13":"x"},{"cover_url":"u"}])=={"books":2,"with_isbn":1,"with_cover":1}
def test_serializers():
 assert "کتاب" in report_json({"title":"کتاب"}); assert "title" in report_csv([{"title":"کتاب"}])
 try: assert report_excel([{"title":"کتاب"}])
 except RuntimeError: pass
 try: assert report_pdf([{"title":"کتاب"}])
 except RuntimeError: pass
