from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.formatter import MessageFormatter
from app.rss import FeedClient


RSS_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>NodeSeek</title>
    <item>
      <title>First post</title>
      <link>https://www.nodeseek.com/post-1-1</link>
      <dc:creator>Alice &amp; Bob</dc:creator>
    </item>
    <item>
      <title>Second post</title>
      <link>https://www.nodeseek.com/post-2-1</link>
    </item>
  </channel>
</rss>"""


class AuthorNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_rss_creator_is_used_as_author(self) -> None:
        response = MagicMock()
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=None)
        response.read = AsyncMock(return_value=RSS_SAMPLE)

        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session.get.return_value = response

        with patch("app.rss.aiohttp.ClientSession", return_value=session):
            result = await FeedClient(timeout_seconds=20, max_entries_per_feed=10).fetch(
                "https://rss.nodeseek.com/"
            )

        self.assertEqual([entry.author for entry in result.entries], ["Alice & Bob", "未知"])

    async def test_author_is_escaped_in_telegram_html(self) -> None:
        message = MessageFormatter().render(
            title="First post",
            author="Alice <Bob> & Co",
            link="https://www.nodeseek.com/post-1-1",
            matched_keywords=["First"],
            category_name="日常",
        )
        self.assertIn("👤 作   者： Alice &lt;Bob&gt; &amp; Co", message)
        self.assertNotIn("<Bob>", message)
