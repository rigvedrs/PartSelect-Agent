"""YouTube link extraction from HTML (no browser)."""
from scrapers.detail_extractor import _youtube_link_from_page, _youtube_watch_url


class _FakeDriver:
    def __init__(self, html: str):
        self.page_source = html

    def find_elements(self, *args, **kwargs):
        return []


def test_watch_url_from_embed():
    assert _youtube_watch_url("https://www.youtube.com/embed/abc123XY") == (
        "https://www.youtube.com/watch?v=abc123XY"
    )


def test_link_from_page_source():
    html = '<div data-yt-init="m8xZwWBmVFo"></div>'
    assert _youtube_link_from_page(_FakeDriver(html)) == "https://www.youtube.com/watch?v=m8xZwWBmVFo"


def test_link_from_watch_url_in_html():
    html = 'href="https://www.youtube.com/watch?v=QYYmKvfj6Xk"'
    assert _youtube_link_from_page(_FakeDriver(html)) == "https://www.youtube.com/watch?v=QYYmKvfj6Xk"
