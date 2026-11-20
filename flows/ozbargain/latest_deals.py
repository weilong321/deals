import csv
import hashlib
import os
from datetime import date
from pathlib import Path

import httpx
import msgspec
from prefect import flow, get_run_logger, task
from prefect.variables import Variable

from client.ozbargain.ozbargain import OzBargainClient
from client.ozbargain.spec import FeedEntry
from parsers.ozbargain.latest_deals import validate_feed_spec, validate_raw_feed
from schema.ozbargain.latest_deals import FeedSchema

__all__ = ["process_feed", "log_feed", "entry_hash"]

HISTORY_PATH = Path("data/history.csv")
HISTORY_COLUMNS = ["alerted_at", "sha256"]
HISTORY_VARIABLE = "ozbargain-history-hashes"
HISTORY_HASH_LIMIT = 70


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


def load_recent_history_hashes(history_path: Path = HISTORY_PATH) -> list[str]:
    if not history_path.exists():
        return []

    with history_path.open(newline="") as history:
        reader = csv.DictReader(history)
        if "sha256" not in (reader.fieldnames or []):
            return []
        hashes = [row["sha256"] for row in reader if row.get("sha256")]
    return hashes[-HISTORY_HASH_LIMIT:]


def log_feed_with_history(
    entries: list[FeedEntry], history_hashes: list[str]
) -> tuple[list[FeedEntry], list[str]]:
    recent_hashes = list(dict.fromkeys(history_hashes))
    seen = set(recent_hashes)
    unseen: list[FeedEntry] = []

    for entry in entries:
        digest = entry_hash(entry)
        if digest not in seen:
            unseen.append(entry)
            recent_hashes.append(digest)
            seen.add(digest)

    return unseen, recent_hashes[-HISTORY_HASH_LIMIT:]


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
    history = Variable.get(HISTORY_VARIABLE, default=None)
    history_hashes = (
        history.splitlines() if history is not None else load_recent_history_hashes()
    )
    unseen, updated_hashes = log_feed_with_history(entries, history_hashes)
    updated_history = "\n".join(updated_hashes)

    if history is None or updated_history != history:
        Variable.set(
            HISTORY_VARIABLE,
            updated_history,
            overwrite=history is not None,
        )

    return unseen


@flow(name="ozbargain-deals", log_prints=True)
def deals_flow() -> None:
    entries = fetch_entries()
    unseen_entries = record_feed(entries)
    for entry in unseen_entries:
        notify(f"New OzBargain deal: {entry.title}\n{entry.link}")


if __name__ == "__main__":
    deals_flow()
