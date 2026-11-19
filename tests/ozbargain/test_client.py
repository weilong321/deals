import httpx
import pytest

from client.ozbargain.ozbargain import BASE_URL, DEALS_FEED_PATH, OzBargainClient

RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xml:base="https://www.ozbargain.com.au"
 xmlns:atom="http://www.w3.org/2005/Atom"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:media="http://search.yahoo.com/mrss/"
 xmlns:ozb="https://www.ozbargain.com.au">
<channel>
  <title>OzBargain</title>
  <link>https://www.ozbargain.com.au/deals/feed</link>
<description></description><language>en</language>
<atom:link
  href="https://www.ozbargain.com.au/deals/feed"
  rel="self"
  type="application/rss+xml" />
<item>
  <title>Switch OLED $299 @ Amazon</title>
  <link>http://example.com/deal</link>
  <description><![CDATA[<p>Deal</p>]]></description>
  <comments>http://example.com/deal#comment</comments>
  <category domain="https://www.ozbargain.com.au/cat/gaming">Gaming</category>
  <ozb:meta
    comment-count="0"
    link="https://www.ozbargain.com.au/goto/1"
    click-count="1"
    votes-pos="1"
    votes-neg="0"
    url="http://example.com/deal" />
  <media:thumbnail url="https://example.com/image.jpg" />
  <pubDate>Mon, 01 Jan 2026 00:00:00 +0000</pubDate>
  <dc:creator>tester</dc:creator>
  <guid isPermaLink="false">1 at https://www.ozbargain.com.au</guid>
</item>
</channel></rss>"""


def make_client(*results):
    """Client backed by MockTransport. Each result is a Response or an exception."""
    queue = list(results)
    requests_seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE_URL)
    return OzBargainClient(client=http), requests_seen


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _: None)


def test_get_latest_deals_parses_entries():
    client, _ = make_client(httpx.Response(200, content=RSS))
    entries = client.get_latest_deals()
    assert len(entries) == 1
    assert entries[0].title == "Switch OLED $299 @ Amazon"
    assert entries[0].link == "http://example.com/deal"


def test_requests_main_feed_url():
    client, seen = make_client(httpx.Response(200, content=RSS))
    client.get_latest_deals()
    assert len(seen) == 1
    assert str(seen[0].url) == f"{BASE_URL}{DEALS_FEED_PATH}"


def test_retries_network_errors_then_succeeds():
    client, seen = make_client(
        httpx.ConnectError("boom"),
        httpx.ReadTimeout("slow"),
        httpx.Response(200, content=RSS),
    )
    assert len(client.get_latest_deals()) == 1
    assert len(seen) == 3


def test_retries_5xx():
    client, seen = make_client(httpx.Response(503), httpx.Response(200, content=RSS))
    assert len(client.get_latest_deals()) == 1
    assert len(seen) == 2


def test_gives_up_after_three_attempts():
    client, seen = make_client(*[httpx.ConnectError("boom")] * 3)
    with pytest.raises(httpx.ConnectError):
        client.get_latest_deals()
    assert len(seen) == 3


def test_does_not_retry_404():
    client, seen = make_client(httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        client.get_latest_deals()
    assert len(seen) == 1


def test_context_manager_closes_client():
    client, _ = make_client()
    with client as c:
        assert c is client
    assert client._client.is_closed
