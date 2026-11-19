"""Thin HTTP client for OzBargain's public RSS feeds."""

import logging

import httpx
from prefect.logging import get_logger
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)
from typing_extensions import Self

from client.ozbargain.spec import FeedEntry
from parsers.ozbargain.latest_deals import parse_entries

logger = get_logger(__name__)

BASE_URL = "https://www.ozbargain.com.au"
DEALS_FEED_PATH = "/deals/feed"
DEFAULT_USER_AGENT = "deal-tracker/0.1 (personal use; contact: mtthwchn123@gmail.com)"


def _is_retryable(exc: BaseException) -> bool:
    """Retry network errors, timeouts, 429s and 5xx. Never retry other 4xx."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


retry_transient = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class OzBargainClient:
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = client or httpx.Client(
            base_url=BASE_URL,
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get_latest_deals(self) -> list[FeedEntry]:
        """Latest deals from the main OzBargain feed."""
        return self.get_feed(DEALS_FEED_PATH)

    @retry_transient
    def get_feed(self, path: str) -> list[FeedEntry]:
        """Fetch and parse any OzBargain feed by path."""
        resp = self._client.get(path)
        resp.raise_for_status()
        return parse_entries(resp.content)

    @retry_transient
    def get_feed_content(self, path: str) -> bytes:
        """Fetch raw feed content without parsing or validation."""
        resp = self._client.get(path)
        resp.raise_for_status()
        return resp.content

    def get_latest_deals_content(self) -> bytes:
        """Fetch raw content from the main OzBargain feed."""
        return self.get_feed_content(DEALS_FEED_PATH)


if __name__ == "__main__":
    client = OzBargainClient()
    latest_deals = client.get_latest_deals()
    for item in latest_deals:
        print(item.title)
