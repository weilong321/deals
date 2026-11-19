"""Raw shape of data from OzBargain. Every field is a plain string."""

import msgspec


class FeedEntrySchema(msgspec.Struct, frozen=True):
    title: str
    link: str
    published: str
