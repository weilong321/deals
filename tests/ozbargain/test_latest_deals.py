from flows.ozbargain.latest_deals import parse_price, match_deals, best_deal
from schema.ozbargain.latest_deals import FeedEntrySchema


def test_parse_price():
    assert parse_price("Nintendo Switch OLED $299 @ Amazon") == 299.0
    assert parse_price("Free shipping") is None


def test_match_and_best():
    entries = [
        FeedEntrySchema(title="Switch OLED $349 @ A", link="http://a", published=""),
        FeedEntrySchema(title="Switch OLED $299 @ B", link="http://b", published=""),
        FeedEntrySchema(title="Unrelated $5", link="http://c", published=""),
    ]
    found = match_deals(entries, "switch oled")
    assert len(found) == 2
    assert best_deal(found)["link"] == "http://b"
