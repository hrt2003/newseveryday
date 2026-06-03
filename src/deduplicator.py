"""
文章去重模块。
基于 Jaccard 相似度在同类别内检测并移除重复文章。
"""

import re
import logging
from typing import Callable

from .feed_fetcher import RawArticle

logger = logging.getLogger("news_digest.dedup")


class Deduplicator:
    """跨源文章去重器。

    在同一类别内，比较每对文章的标题+摘要的 token 集合重叠度。
    相似度超过阈值的文章被视为重复，保留来源优先级更高的那篇。
    """

    # 常见英文停用词（不参与相似度计算）
    STOP_WORDS: set[str] = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "shall", "it", "its", "this",
        "that", "these", "those", "he", "she", "they", "we", "you", "his", "her",
        "their", "our", "my", "your", "as", "not", "no", "so", "if", "than",
        "then", "also", "just", "about", "into", "over", "after", "before",
        "between", "under", "out", "up", "down", "off", "very", "too", "more",
        "some", "such", "each", "every", "all", "both", "few", "most", "other",
        "new", "now", "says", "said",
    }

    def __init__(
        self,
        threshold: float = 0.6,
        get_source_rank: Callable[[str], int] | None = None,
    ):
        self.threshold = threshold
        self.get_source_rank = get_source_rank or (lambda _: 999)

    def deduplicate(
        self, articles_by_category: dict[str, list[RawArticle]]
    ) -> dict[str, list[RawArticle]]:
        """对每个分类内的文章去重。

        Args:
            articles_by_category: 按分类组织的文章列表。

        Returns:
            去重后的文章列表，按分类组织。
        """
        result: dict[str, list[RawArticle]] = {}

        for category, articles in articles_by_category.items():
            before = len(articles)
            deduped = self._deduplicate_one_category(articles)
            after = len(deduped)
            if before > after:
                logger.info(f"  去重 [{category}]: {before} → {after} (移除 {before - after} 篇)")
            result[category] = deduped

        return result

    def _deduplicate_one_category(
        self, articles: list[RawArticle]
    ) -> list[RawArticle]:
        """在单个类别内去重。"""
        if len(articles) <= 1:
            return articles

        # 按来源优先级排序（排名高的在前）
        sorted_articles = sorted(articles, key=lambda a: self.get_source_rank(a.source_name))

        kept: list[RawArticle] = []

        for article in sorted_articles:
            is_duplicate = False
            for existing in kept:
                sim = self._similarity(article, existing)
                if sim >= self.threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                kept.append(article)
            else:
                logger.debug(f"    去重移除: [{article.source_name}] {article.title[:50]}...")

        return kept

    def _similarity(self, a: RawArticle, b: RawArticle) -> float:
        """计算两篇文章的 Jaccard 相似度（基于标题+摘要的 token 集合）。"""
        # 提取和 tokenize
        tokens_a = self._tokenize(f"{a.title} {a.summary[:150]}")
        tokens_b = self._tokenize(f"{b.title} {b.summary[:150]}")

        if not tokens_a or not tokens_b:
            return 0.0

        set_a = set(tokens_a)
        set_b = set(tokens_b)

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)

        if union == 0:
            return 0.0

        return intersection / union

    def _tokenize(self, text: str) -> list[str]:
        """将文本分词并去停用词。

        对中文按字符 n-gram 处理，对英文按单词处理。
        """
        # 转小写
        text = text.lower()

        # 检测是否包含中文字符
        if any("一" <= ch <= "鿿" for ch in text):
            # 中文：按 2-gram 字符切分
            return [text[i : i + 2] for i in range(len(text) - 1)]

        # 英文：提取英文单词
        words = re.findall(r"[a-z0-9]+", text)
        # 过滤停用词和太短的词
        return [w for w in words if w not in self.STOP_WORDS and len(w) > 1]
