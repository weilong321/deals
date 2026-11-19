import msgspec
import pytest

from schema.ozbargain.latest_deals import FeedEntrySchema

VALID = {
    "title": "Switch OLED $299",
    "link": "https://www.ozbargain.com.au/node/1",
    "published": "Mon, 01 Jan 2026 00:00:00 +0000",
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
