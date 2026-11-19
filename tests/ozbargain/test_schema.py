import msgspec
import pytest

from schema.ozbargain.latest_deals import FeedEntrySchema

VALID = {
    "title": "Switch OLED $299",
    "link": "https://www.ozbargain.com.au/node/1",
    "published": "Mon, 01 Jan 2026 00:00:00 +0000",
    "description": "A deal",
    "comments": "https://www.ozbargain.com.au/node/1#comment",
    "creator": "tester",
    "categories": [
        {"term": "Gaming", "scheme": "https://www.ozbargain.com.au/cat/gaming"}
    ],
    "meta": {
        "comment_count": "0",
        "link": "https://www.ozbargain.com.au/goto/1",
        "click_count": "1",
        "votes_pos": "1",
        "votes_neg": "0",
        "url": "https://example.com",
    },
    "guid": {"guid": "1 at https://www.ozbargain.com.au", "is_perma_link": False},
    "thumbnails": [],
    "title_messages": [],
}


def test_entry_converts():
    entry = msgspec.convert(VALID, FeedEntrySchema)
    assert entry.title == "Switch OLED $299"
    assert entry.published == "Mon, 01 Jan 2026 00:00:00 +0000"


@pytest.mark.parametrize("field", ["title", "link", "published"])
def test_rejects_missing_or_non_string_fields(field):
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert({**VALID, field: None}, FeedEntrySchema)
    with pytest.raises(msgspec.ValidationError):
        msgspec.convert({k: v for k, v in VALID.items() if k != field}, FeedEntrySchema)
