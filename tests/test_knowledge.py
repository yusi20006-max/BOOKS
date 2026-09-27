from books.knowledge import Quote,Note,KnowledgeNode,KnowledgeEdge,knowledge_search


def test_quote_note_and_normalization():
 q=Quote("q","b","  این یک نقل‌قول است  ",12); n=Note("n","b"," یادداشت ")
 assert q.text=="این یک نقل‌قول است" and n.text=="یادداشت"
def test_graph_and_unified_search():
 q=Quote("q","b","کتابخانه شخصی",1); node=KnowledgeNode("k","کتابخانه")
 assert KnowledgeEdge("k","q","مرتبط").relation=="مرتبط"
 assert knowledge_search("کتابخانه",[q],[],[node])==[q,node]
