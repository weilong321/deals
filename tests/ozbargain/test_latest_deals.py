import csv
from datetime import datetime

import msgspec

from client.ozbargain.spec import FeedEntry
from flows.ozbargain.latest_deals import (
    HISTORY_COLUMNS,
    entry_hash,
    log_feed,
    log_feed_with_history,
    process_feed,
)


def make_entry(title: str, guid: str) -> FeedEntry:
    return FeedEntry(
        title=title,
        link=f"https://example.com/{guid}",
        published=datetime(2026, 1, 1),
        description="A deal",
        comments="https://example.com/comments",
        creator="tester",
        categories=["Gaming"],
        category_domains=["https://example.com/cat/gaming"],
        comment_count=1,
        meta_link="https://example.com/goto",
        click_count=10,
        expiry=None,
        starting=None,
        votes_pos=2,
        votes_neg=0,
        deal_url="https://example.com/deal",
        image="https://example.com/image.jpg",
        thumbnail_urls=["https://example.com/thumb.jpg"],
        title_message_types=["expired"],
        title_message_texts=["expired"],
        guid=guid,
        is_perma_link=False,
        price=299.0,
    )


def test_log_feed_hashes_complete_entries(tmp_path):
    history = tmp_path / "history.csv"
    entries = [make_entry("Deal A", "1")]

    unseen = log_feed(entries, history)

    assert unseen == entries
    assert len(entry_hash(entries[0])) == 64

    unseen_again = process_feed(entries, history)

    assert unseen_again == []

    changed = msgspec.structs.replace(entries[0], click_count=11)
    updated = log_feed([changed], history)

    assert updated == [changed]

    with history.open(newline="") as history_file:
        reader = csv.DictReader(history_file)
        assert reader.fieldnames == HISTORY_COLUMNS
        rows = list(reader)

    assert len(rows) == 2
    assert rows[0]["sha256"] == entry_hash(entries[0])
    assert rows[1]["sha256"] == entry_hash(changed)


def test_log_feed_with_history_deduplicates_and_bounds_history():
    entries = [make_entry("Deal A", "1"), make_entry("Deal B", "2")]
    previous_hashes = [f"{index:064x}" for index in range(70)]

    unseen, updated_hashes = log_feed_with_history(entries, previous_hashes)

    assert unseen == entries
    assert len(updated_hashes) == 70
    assert updated_hashes[-2:] == [entry_hash(entry) for entry in entries]

    unseen_again, unchanged_hashes = log_feed_with_history(entries, updated_hashes)

    assert unseen_again == []
    assert unchanged_hashes == updated_hashes
