"""
RSS Feed 抓取模块。
从配置的 RSS 源抓取文章，每个源独立错误处理，失败不阻塞整体流程。
"""

import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import feedparser

from .config import Feed

logger = logging.getLogger("news_digest.fetcher")


@dataclass
class RawArticle:
    """从 RSS 抓取的原始文章数据。"""
    title: str
    summary: str
    link: str
    published: Optional[datetime]
    source_name: str
    category: str
    guid: str


@dataclass
class FetchResult:
    """单个分类的抓取结果。"""
    category: str
    articles: list[RawArticle]
    errors: list[str]  # 抓取失败的源名称列表


class FeedFetcher:
    """RSS Feed 抓取器。

    遍历所有配置的 RSS 源并抓取文章。每个源具有独立的错误处理和重试机制，
    单个源的失败不会阻塞其他源的抓取。
    """

    def __init__(
        self,
        feeds: dict[str, list[Feed]],
        timeout: int = 30,
        max_retries: int = 2,
        backoff_factor: float = 2.0,
        max_articles: int = 8,
    ):
        self.feeds = feeds
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_articles = max_articles

    def fetch_all(self) -> dict[str, FetchResult]:
        """抓取所有分类的所有新闻源。

        Returns:
            dict[category, FetchResult]: 按分类组织的抓取结果。
        """
        results: dict[str, FetchResult] = {}

        for category, feed_list in self.feeds.items():
            category_articles: list[RawArticle] = []
            category_errors: list[str] = []

            for feed in feed_list:
                try:
                    articles = self._fetch_one(feed)
                    category_articles.extend(articles)
                    logger.info(f"  ✓ {feed.name}: {len(articles)} 篇文章")
                except Exception as e:
                    category_errors.append(feed.name)
                    logger.warning(f"  ✗ {feed.name}: {e}")

            results[category] = FetchResult(
                category=category,
                articles=category_articles,
                errors=category_errors,
            )

        return results

    def _fetch_one(self, feed: Feed) -> list[RawArticle]:
        """抓取单个 RSS 源，带重试机制。"""
        import requests as _requests
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                # 先通过 requests 获取 RSS 内容（支持 timeout），再交给 feedparser 解析
                resp = _requests.get(
                    feed.url,
                    timeout=self.timeout,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; DailyNewsDigest/1.0)"
                    },
                )
                resp.raise_for_status()
                parsed = feedparser.parse(resp.content)

                # 检查是否是合法的 RSS 解析结果
                if parsed.bozo and not parsed.entries:
                    bozo_msg = str(getattr(parsed, "bozo_exception", "Unknown parse error"))
                    raise RuntimeError(f"RSS 解析失败: {bozo_msg}")

                articles = []
                for entry in parsed.entries[: self.max_articles]:
                    article = self._parse_entry(entry, feed)
                    if article:
                        articles.append(article)

                return articles

            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = self.backoff_factor ** attempt
                    logger.debug(f"    {feed.name} 重试 {attempt+1}/{self.max_retries}，等待 {wait}s")
                    time.sleep(wait)

        raise RuntimeError(f"抓取失败（已重试 {self.max_retries} 次）: {last_error}")

    def _parse_entry(self, entry: dict, feed: Feed) -> Optional[RawArticle]:
        """将 feedparser entry 标准化为 RawArticle。"""
        title = getattr(entry, "title", "").strip()
        if not title:
            return None

        summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
        summary = _strip_html(summary).strip()

        link = getattr(entry, "link", "").strip()

        # 解析发布时间
        published = None
        pub_parsed = getattr(entry, "published_parsed", None)
        if pub_parsed:
            try:
                published = datetime(*pub_parsed[:6])
            except (TypeError, ValueError):
                pass

        guid = getattr(entry, "id", "") or getattr(entry, "link", "") or title

        return RawArticle(
            title=title,
            summary=summary[:500],  # 限制摘要长度
            link=link,
            published=published,
            source_name=feed.name,
            category=feed.category,
            guid=guid,
        )


def _strip_html(text: str) -> str:
    """去除 HTML 标签，保留纯文本。"""
    import re
    # 移除 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 解码 HTML 实体
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'")
    text = text.replace("&nbsp;", " ")
    return text
