"""Parsing functions for OzBargain RSS data."""

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import msgspec

from client.ozbargain.spec import FeedEntry
from schema.ozbargain.latest_deals import FeedSchema

NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
    "ozb": "https://www.ozbargain.com.au",
}

PRICE_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")


def _text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    text = "".join(element.itertext()).strip()
    return text or None


def _datetime(value: str | None) -> datetime:
    if not value:
        raise ValueError("A date is required")
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return parsedate_to_datetime(value.strip())


def _optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return _datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _int(value: str | None) -> int:
    try:
        return int(value or "0")
    except (TypeError, ValueError):
        return 0


def parse_price(title: str) -> float | None:
    match = PRICE_RE.search(title)
    return float(match.group(1).replace(",", "")) if match else None


def _required_text(element: ET.Element | None) -> str:
    if element is None:
        raise ValueError("Required RSS text is missing")
    return "".join(element.itertext()).strip()


def _entry_schema_dict(element: ET.Element) -> dict:
    category_items = []
    for category in element.findall("category"):
        category_items.append(
            {
                "term": _required_text(category),
                "scheme": category.get("domain", ""),
            }
        )

    meta_element = element.find("ozb:meta", NS)
    if meta_element is None:
        raise ValueError("Required ozb:meta is missing")

    meta = {
        "comment_count": meta_element.get("comment-count", ""),
        "link": meta_element.get("link", ""),
        "click_count": meta_element.get("click-count", ""),
        "votes_pos": meta_element.get("votes-pos", ""),
        "votes_neg": meta_element.get("votes-neg", ""),
        "url": meta_element.get("url", ""),
        "expiry": meta_element.get("expiry"),
        "starting": meta_element.get("starting"),
        "image": meta_element.get("image"),
    }

    guid_element = element.find("guid")
    if guid_element is None:
        raise ValueError("Required guid is missing")

    return {
        "title": _required_text(element.find("title")),
        "link": _required_text(element.find("link")),
        "published": _required_text(element.find("pubDate")),
        "description": _required_text(element.find("description")),
        "comments": _required_text(element.find("comments")),
        "creator": _required_text(element.find("dc:creator", NS)),
        "categories": category_items,
        "meta": meta,
        "guid": {
            "guid": _required_text(guid_element),
            "is_perma_link": guid_element.get("isPermaLink", "false").lower() == "true",
        },
        "thumbnails": [
            {"url": thumbnail.get("url", "")}
            for thumbnail in element.findall("media:thumbnail", NS)
        ],
        "title_messages": [
            {"message_type": message.get("type", ""), "text": _required_text(message)}
            for message in element.findall("ozb:title-msg", NS)
        ],
    }


def raw_feed_schema_dict(content: bytes | str) -> dict:
    root = ET.fromstring(content)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("OzBargain RSS response has no channel")

    atom_link = channel.find("{http://www.w3.org/2005/Atom}link")
    if atom_link is None:
        raise ValueError("Required Atom link is missing")

    return {
        "rss": {
            "version": root.get("version", ""),
            "xml_base": root.get("{http://www.w3.org/XML/1998/namespace}base", ""),
        },
        "channel": {
            "title": _required_text(channel.find("title")),
            "link": _required_text(channel.find("link")),
            "description": _required_text(channel.find("description")),
            "language": _required_text(channel.find("language")),
            "atom_link": {
                "href": atom_link.get("href", ""),
                "rel": atom_link.get("rel", ""),
                "type": atom_link.get("type", ""),
            },
        },
        "entries": [_entry_schema_dict(item) for item in channel.findall("item")],
    }


def validate_raw_feed(content: bytes | str) -> FeedSchema:
    """Step 1: validate the raw RSS shape."""
    return msgspec.convert(raw_feed_schema_dict(content), FeedSchema)


def validate_feed_spec(raw_feed: FeedSchema) -> list[FeedEntry]:
    """Step 2: parse raw values and validate the flat typed entry spec."""
    entries = []
    for raw_entry in raw_feed.entries:
        title = raw_entry.title
        entries.append(
            FeedEntry(
                title=title,
                link=raw_entry.link,
                published=_datetime(raw_entry.published),
                description=raw_entry.description,
                comments=raw_entry.comments,
                creator=raw_entry.creator,
                categories=[category.term for category in raw_entry.categories],
                category_domains=[category.scheme for category in raw_entry.categories],
                comment_count=_int(raw_entry.meta.comment_count),
                meta_link=raw_entry.meta.link,
                click_count=_int(raw_entry.meta.click_count),
                expiry=_optional_datetime(raw_entry.meta.expiry),
                starting=_optional_datetime(raw_entry.meta.starting),
                votes_pos=_int(raw_entry.meta.votes_pos),
                votes_neg=_int(raw_entry.meta.votes_neg),
                deal_url=raw_entry.meta.url,
                image=raw_entry.meta.image,
                thumbnail_urls=[thumbnail.url for thumbnail in raw_entry.thumbnails],
                title_message_types=[
                    message.message_type for message in raw_entry.title_messages
                ],
                title_message_texts=[
                    message.text for message in raw_entry.title_messages
                ],
                guid=raw_entry.guid.guid,
                is_perma_link=raw_entry.guid.is_perma_link,
                price=parse_price(title),
            )
        )

    return msgspec.convert(msgspec.to_builtins(entries), list[FeedEntry])


def parse_feed(content: bytes | str) -> list[FeedEntry]:
    raw_feed = validate_raw_feed(content)
    return validate_feed_spec(raw_feed)


def parse_entries(content: bytes | str) -> list[FeedEntry]:
    return parse_feed(content)


def match_deals(entries: list[FeedEntry], item: str) -> list[FeedEntry]:
    words = item.lower().split()
    return [
        entry for entry in entries if all(word in entry.title.lower() for word in words)
    ]


def best_deal(deals: list[FeedEntry]) -> FeedEntry | None:
    if not deals:
        return None

    priced_entries = [deal for deal in deals if deal.price is not None]
    if priced_entries:
        return min(priced_entries, key=lambda deal: deal.price or 0)
    return deals[0]
