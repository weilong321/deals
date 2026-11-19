"""Parsed, typed shape of one OzBargain deal entry."""

from datetime import datetime

import msgspec


class FeedEntry(msgspec.Struct, frozen=True):
    title: str
    link: str
    published: datetime
    description: str
    comments: str
    creator: str

    categories: list[str]
    category_domains: list[str]

    comment_count: int
    meta_link: str
    click_count: int
    expiry: datetime | None
    starting: datetime | None
    votes_pos: int
    votes_neg: int
    deal_url: str
    image: str | None

    thumbnail_urls: list[str]
    title_message_types: list[str]
    title_message_texts: list[str]

    guid: str
    is_perma_link: bool
    price: float | None
