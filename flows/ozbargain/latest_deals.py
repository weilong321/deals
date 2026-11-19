import csv
import datetime as dt
import os
import re
from pathlib import Path

import httpx
from prefect import flow, get_run_logger, task

from client.ozbargain.ozbargain import OzBargainClient
from schema.ozbargain.latest_deals import FeedEntrySchema

ITEMS = [s.strip().lower() for s in os.environ.get("ITEMS", "nintendo switch").split(",")]
HISTORY = Path("data/history.csv")
PRICE_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")


def parse_price(title: str) -> float | None:
    m = PRICE_RE.search(title)
    return float(m.group(1).replace(",", "")) if m else None


def match_deals(entries: list[FeedEntrySchema], item: str) -> list[dict]:
    words = item.split()
    return [
        {"title": e.title, "link": e.link, "price": parse_price(e.title)}
        for e in entries
        if all(w in e.title.lower() for w in words)
    ]


def best_deal(deals: list[dict]) -> dict | None:
    priced = [d for d in deals if d["price"] is not None]
    if priced:
        return min(priced, key=lambda d: d["price"])
    return deals[0] if deals else None


def log_deals(item: str, deals: list[dict]) -> None:
    HISTORY.parent.mkdir(exist_ok=True)
    new_file = not HISTORY.exists()
    with HISTORY.open("a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "item", "price", "title", "link"])
        today = dt.date.today().isoformat()
        for d in deals:
            w.writerow([today, item, d["price"], d["title"], d["link"]])


@task
def notify(message: str) -> None:
    logger = get_run_logger()
    webhook = os.environ.get("WEBHOOK_URL")
    if webhook:
        httpx.post(webhook, json={"content": message}, timeout=10).raise_for_status()
    else:
        logger.info(message)


@task
def fetch_entries() -> list[FeedEntrySchema]:
    with OzBargainClient() as client:
        return client.get_latest_deals()


@task
def process_item(entries: list[FeedEntrySchema], item: str) -> dict | None:
    logger = get_run_logger()
    deals = match_deals(entries, item)
    if not deals:
        logger.info("No deals for %s", item)
        return None
    log_deals(item, deals)
    return best_deal(deals)


@flow(name="ozbargain-deals", log_prints=True)
def deals_flow(items: list[str] = ITEMS) -> None:
    entries = fetch_entries()
    for item in items:
        best = process_item(entries, item)
        if best:
            notify(f"Best OzBargain deal for {item}: {best['title']}\n{best['link']}")


if __name__ == "__main__":
    deals_flow()