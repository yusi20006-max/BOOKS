import pytest
from books.cover import CoverMetadata

def test_cover_retains_edition_identity():
    c=CoverMetadata(" https://example.test/a.jpg ","fa-shamloo","fa")
    assert c.url.endswith("a.jpg") and c.edition_key=="fa-shamloo"

def test_cover_requires_url():
    with pytest.raises(ValueError): CoverMetadata(" ")
