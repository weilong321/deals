"""Raw OzBargain RSS shapes.

Every field is raw XML/feed text. Parsing and type conversion happen in the parser.
"""

import msgspec


class AtomLinkSchema(msgspec.Struct, frozen=True):
    href: str
    rel: str
    type: str


class CategorySchema(msgspec.Struct, frozen=True):
    term: str
    scheme: str


class OzbMetaSchema(msgspec.Struct, frozen=True):
    comment_count: str
    link: str
    click_count: str
    votes_pos: str
    votes_neg: str
    url: str
    expiry: str | None = None
    starting: str | None = None
    image: str | None = None


class ThumbnailSchema(msgspec.Struct, frozen=True):
    url: str


class TitleMessageSchema(msgspec.Struct, frozen=True):
    message_type: str
    text: str


class GuidSchema(msgspec.Struct, frozen=True):
    guid: str
    is_perma_link: bool


class FeedEntrySchema(msgspec.Struct, frozen=True):
    title: str
    link: str
    published: str
    description: str
    comments: str
    creator: str
    categories: list[CategorySchema]
    meta: OzbMetaSchema
    guid: GuidSchema
    thumbnails: list[ThumbnailSchema]
    title_messages: list[TitleMessageSchema]


class FeedChannelSchema(msgspec.Struct, frozen=True):
    title: str
    link: str
    description: str
    language: str
    atom_link: AtomLinkSchema


class RssSchema(msgspec.Struct, frozen=True):
    version: str
    xml_base: str


class FeedSchema(msgspec.Struct, frozen=True):
    rss: RssSchema
    channel: FeedChannelSchema
    entries: list[FeedEntrySchema]
