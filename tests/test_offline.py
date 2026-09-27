from books.offline import local_capabilities


def test_core_library_capabilities_do_not_require_network():
    c=local_capabilities()
    assert c.view and c.search and c.edit and c.delete and c.reading and c.notes and c.backup
    assert not c.discovery and not c.enrichment and not c.ai_cloud and not c.sync
