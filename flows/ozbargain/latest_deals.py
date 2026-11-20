import hashlib
import os

import httpx
import msgspec
from dotenv import load_dotenv
from prefect import flow, get_run_logger, task
from prefect.variables import Variable

from client.ozbargain.ozbargain import OzBargainClient
from client.ozbargain.spec import FeedEntry
from parsers.ozbargain.latest_deals import validate_feed_spec, validate_raw_feed
from schema.ozbargain.latest_deals import FeedSchema

__all__ = ["entry_hash", "log_feed_with_history"]

HISTORY_VARIABLE = "ozbargain-history-hashes"
HISTORY_HASH_LIMIT = 70

load_dotenv()


def entry_hash(entry: FeedEntry) -> str:
    """SHA-256 of the complete canonicalized feed entry."""
    payload = msgspec.json.encode(entry)
    return hashlib.sha256(payload).hexdigest()


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


@task
def notify(entries: list[FeedEntry]) -> None:
    logger = get_run_logger()
    webhook = os.environ.get("WEBHOOK_URL")
    for entry in entries:
        message = f"New OzBargain deal: {entry.title}\n{entry.link}"
        if webhook:
            httpx.post(
                webhook, json={"content": message}, timeout=10
            ).raise_for_status()
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
    history = Variable[str].get(HISTORY_VARIABLE)
    if history is None:
        raise RuntimeError(f"Required Prefect Variable {HISTORY_VARIABLE!r} is missing")

    history_hashes = history.splitlines()
    unseen, updated_hashes = log_feed_with_history(entries, history_hashes)
    updated_history = "\n".join(updated_hashes)

    if updated_history != history:
        Variable.set(HISTORY_VARIABLE, updated_history, overwrite=True)

    return unseen


@flow(name="ozbargain-deals", log_prints=True)
def deals_flow() -> None:
    entries = fetch_entries()
    unseen_entries = record_feed(entries)
    if unseen_entries:
        notify(unseen_entries)


if __name__ == "__main__":
    deals_flow()
