import csv
import hashlib
import os
from datetime import date
from pathlib import Path

import httpx
import msgspec
from prefect import flow, get_run_logger, task

from client.ozbargain.ozbargain import OzBargainClient
from client.ozbargain.spec import FeedEntry
from parsers.ozbargain.latest_deals import validate_feed_spec, validate_raw_feed
from schema.ozbargain.latest_deals import FeedSchema

__all__ = ["process_feed", "log_feed", "entry_hash"]

HISTORY_PATH = Path("data/history.csv")
HISTORY_COLUMNS = ["alerted_at", "sha256"]


def entry_hash(entry: FeedEntry) -> str:
    """SHA-256 of the complete canonicalized feed entry."""
    payload = msgspec.json.encode(entry)
    return hashlib.sha256(payload).hexdigest()


def load_seen_entries(history_path: Path = HISTORY_PATH) -> set[str]:
    if not history_path.exists():
        return set()

    seen: set[str] = set()
    with history_path.open(newline="") as history:
        reader = csv.DictReader(history)
        if "sha256" not in (reader.fieldnames or []):
            return set()
        for row in reader:
            digest = row.get("sha256")
            if digest:
                seen.add(digest)
    return seen


def log_feed(
    entries: list[FeedEntry], history_path: Path = HISTORY_PATH
) -> list[FeedEntry]:
    """Append unseen entry hashes and return entries that should be alerted."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    if history_path.exists():
        with history_path.open(newline="") as history:
            reader = csv.DictReader(history)
            if (reader.fieldnames or []) != HISTORY_COLUMNS:
                history_path.unlink()

    seen = load_seen_entries(history_path)
    unseen: list[FeedEntry] = []

    for entry in entries:
        digest = entry_hash(entry)
        if digest not in seen:
            unseen.append(entry)
            seen.add(digest)

    if unseen:
        new_file = not history_path.exists()
        with history_path.open("a", newline="") as history:
            writer = csv.DictWriter(history, fieldnames=HISTORY_COLUMNS)
            if new_file:
                writer.writeheader()

            alerted_at = date.today().isoformat()
            for entry in unseen:
                writer.writerow({"alerted_at": alerted_at, "sha256": entry_hash(entry)})

    return unseen


process_feed = log_feed


@task
def notify(message: str) -> None:
    logger = get_run_logger()
    webhook = os.environ.get("WEBHOOK_URL")
    if webhook:
        httpx.post(webhook, json={"content": message}, timeout=10).raise_for_status()
    else:
        logger.info(message)


@task
def fetch_raw_feed() -> bytes:
    with OzBargainClient() as client:
        return client.get_latest_deals_content()


@task
def validate_schema(raw_feed: bytes) -> FeedSchema:
    """Step 1: validate raw RSS shape against FeedSchema."""
    return validate_raw_feed(raw_feed)


@task
def validate_spec(raw_feed: FeedSchema) -> list[FeedEntry]:
    """Step 2: parse raw values and validate against the flat FeedEntry spec."""
    return validate_feed_spec(raw_feed)


@task
def fetch_entries() -> list[FeedEntry]:
    raw_feed = fetch_raw_feed()
    schema_feed = validate_schema(raw_feed)
    return validate_spec(schema_feed)


@task
def record_feed(entries: list[FeedEntry]) -> list[FeedEntry]:
    return log_feed(entries)


@flow(name="ozbargain-deals", log_prints=True)
def deals_flow() -> None:
    entries = fetch_entries()
    unseen_entries = record_feed(entries)
    for entry in unseen_entries:
        notify(f"New OzBargain deal: {entry.title}\n{entry.link}")


if __name__ == "__main__":
    deals_flow()
