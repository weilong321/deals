from datetime import datetime
from unittest.mock import Mock, call

import msgspec

from client.ozbargain.spec import FeedEntry
from flows.ozbargain.latest_deals import entry_hash, log_feed_with_history, notify


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


def test_log_feed_with_history_tracks_changed_entry_versions():
    original = make_entry("Deal A", "1")
    changed = msgspec.structs.replace(original, click_count=11)

    unseen, updated_hashes = log_feed_with_history([changed], [entry_hash(original)])

    assert unseen == [changed]
    assert updated_hashes == [entry_hash(original), entry_hash(changed)]


def test_notify_posts_all_entries_from_one_task(monkeypatch):
    entries = [make_entry("Deal A", "1"), make_entry("Deal B", "2")]
    post = Mock()
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setattr("flows.ozbargain.latest_deals.httpx.post", post)
    monkeypatch.setattr("flows.ozbargain.latest_deals.get_run_logger", Mock())

    notify.fn(entries)

    assert post.call_args_list == [
        call(
            "https://example.com/webhook",
            json={"content": f"New OzBargain deal: {entry.title}\n{entry.link}"},
            timeout=10,
        )
        for entry in entries
    ]
