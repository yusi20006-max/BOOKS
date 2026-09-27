from books.ai import FailoverAI,book_assistant,summarize_book,summarize_chapter,personalized_reading_plan


class P:
 def __init__(self,name,out=None,fail=False): self.name=name; self.out=out or name; self.fail=fail
 def complete(self,prompt):
  if self.fail: raise RuntimeError("down")
  return self.out

def test_local_first_and_failover():
 assert FailoverAI([P("local","پاسخ"),P("cloud","ابر")]).complete("x")=="پاسخ"
 assert FailoverAI([P("local",fail=True),P("cloud","ابر")]).complete("x")=="ابر"
def test_actions_are_provider_agnostic():
 p=P("mock","نتیجه"); assert "نتیجه"==summarize_book(p,"کتاب","متن"); assert summarize_chapter(p,"کتاب","فصل","متن")=="نتیجه"; assert personalized_reading_plan(p,"کتاب‌ها","هفته‌ای یک کتاب")=="نتیجه"; assert book_assistant(p,"summary","کتاب")=="نتیجه"
