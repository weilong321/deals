"""Validated, typed shape of an OzBargain deal.

Built from ``FeedEntrySchema`` by the validation step in the flow.
"""

from datetime import datetime

import msgspec


class FeedEntry(msgspec.Struct, frozen=True):
    title: str
    link: str
    published: datetime
    price: float | None = None
