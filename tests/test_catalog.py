from books.catalog import Copy, Edition, Translation, Work


def test_work_edition_translation_copy_are_distinct():
    w=Work("w1","شازده کوچولو")
    e=Edition("e1",w.id,"ناشر")
    t=Translation("t1",e.id,"fa",("shamloo",))
    c=Copy("c1",e.id)
    assert (w.id,e.work_id,t.edition_id,c.edition_id)==("w1","w1","e1","e1")
