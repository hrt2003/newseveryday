"""
翻译与摘要编排模块。
将英文新闻通过 DeepSeek API 翻译成中文，并生成分类摘要和全局摘要。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from .feed_fetcher import RawArticle
from .deepseek_client import DeepSeekClient, DeepSeekError

logger = logging.getLogger("news_digest.translator")

# ── 常量：Prompt 模板 ─────────────────────────────────────────────

SYSTEM_PROMPT_CATEGORY = """\
You are a professional news editor and translator fluent in both English and Chinese. \
Your task is to:
1. Translate English news headlines into concise, accurate Chinese.
2. Summarize each article's content into 1-2 Chinese sentences covering key facts: who, what, when, where, why.
3. After translating all articles, write a 2-3 sentence Chinese summary of the most impactful stories in this category.

Rules:
- Headlines: keep under 25 Chinese characters, preserve the original meaning.
- Summaries: focus on facts, avoid editorializing. Include the key data/numbers if present.
- Category summary: identify the 1-2 most important stories and explain why they matter.
- Preserve all URLs and source names exactly as provided.
- Output ONLY valid JSON. No markdown fences, no extra commentary."""

SYSTEM_PROMPT_OVERALL = """\
You are a senior global news editor writing for a Chinese-speaking audience. \
Write a concise daily global news overview in Chinese (3-5 sentences) synthesizing \
the most important stories across all categories. \
Prioritize stories with broad global impact. \
Write in a neutral, factual, and engaging tone. \
Output ONLY the Chinese text — no JSON, no markdown, no prefix, no explanation."""


@dataclass
class TranslatedArticle:
    """翻译后的单篇文章。"""
    original_title: str
    translated_title: str
    translated_summary: str
    link: str
    source_name: str


@dataclass
class CategoryDigest:
    """单个分类的翻译摘要结果。"""
    category: str
    articles: list[TranslatedArticle]
    category_summary_cn: str
    is_fallback: bool = False  # 是否为降级结果（API 失败使用原文）


class Translator:
    """新闻翻译与摘要生成器。

    按分类将文章批量发送给 DeepSeek 进行翻译和摘要。
    分类之间顺序执行以避免 API 频率限制。
    """

    def __init__(self, client: DeepSeekClient):
        self.client = client

    def translate_all(
        self, articles_by_category: dict[str, list[RawArticle]]
    ) -> list[CategoryDigest]:
        """翻译所有分类的文章。

        Args:
            articles_by_category: 按分类组织的文章列表。

        Returns:
            CategoryDigest 列表，每项包含该分类的翻译文章和摘要。
        """
        results: list[CategoryDigest] = []
        categories_order = [
            "Politics", "Economy", "Technology", "Science",
            "Sports", "Entertainment", "Health", "Gaming",
            "Automotive", "Environment", "Education", "Music", "Travel"
        ]

        # 按固定顺序处理分类
        for cat in categories_order:
            articles = articles_by_category.get(cat, [])
            if not articles:
                logger.info(f"  翻译 [{cat}]: 无文章，跳过")
                results.append(CategoryDigest(
                    category=cat,
                    articles=[],
                    category_summary_cn=f"今日无{cat}相关重要新闻。",
                ))
                continue

            logger.info(f"  翻译 [{cat}]: {len(articles)} 篇文章...")
            try:
                digest = self._translate_category(cat, articles)
                results.append(digest)
            except DeepSeekError as e:
                logger.error(f"  ✗ [{cat}] 翻译失败: {e}")
                # 降级：使用原文标题
                results.append(self._fallback_digest(cat, articles, str(e)))

        return results

    def create_overall_digest(
        self, category_digests: list[CategoryDigest]
    ) -> str:
        """基于各分类摘要生成全局新闻摘要（3-5句中文）。"""
        # 构建分类摘要文本
        summaries_text = ""
        for cd in category_digests:
            if cd.articles:
                summaries_text += f"\n{cd.category} ({len(cd.articles)}篇): {cd.category_summary_cn}"

        if not summaries_text.strip():
            return "今日未能获取到足够的新闻内容。"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_OVERALL},
            {
                "role": "user",
                "content": (
                    "基于以下各类别的新闻摘要，写一段3-5句的中文全局新闻概述"
                    "（覆盖最重要的全球新闻）：\n"
                    f"{summaries_text}\n\n"
                    "直接输出中文概述文本，不需要JSON格式。"
                ),
            },
        ]

        try:
            result = self.client.chat_completion(messages, json_mode=False)
            return result.strip()
        except DeepSeekError as e:
            logger.error(f"  全局摘要生成失败: {e}")
            return "（全局摘要暂时无法生成，请查看下方各类别新闻。）"

    def _translate_category(
        self, category: str, articles: list[RawArticle]
    ) -> CategoryDigest:
        """翻译单个分类的文章。"""
        # 构建输入的 JSON 数组
        articles_input = []
        for i, a in enumerate(articles):
            articles_input.append({
                "id": i,
                "title": a.title,
                "summary": a.summary or a.title,
                "link": a.link,
                "source": a.source_name,
            })

        # 构建 user message，内嵌期望的 JSON 结构
        category_cn = {
            "Technology": "科技",
            "Politics": "国际政治",
            "Economy": "经济财经",
            "Travel": "旅游",
            "Sports": "体育",
            "Science": "科学",
            "Entertainment": "娱乐",
            "Health": "健康",
            "Gaming": "游戏",
            "Automotive": "汽车",
            "Environment": "环境",
            "Education": "教育",
            "Music": "音乐",
        }.get(category, category)

        user_content = f"""请翻译以下{category_cn}类新闻文章。

输出格式要求（严格的JSON，不要markdown代码块）：
{{
  "translated_articles": [
    {{
      "id": 0,
      "translated_title": "中文标题（25字以内）",
      "translated_summary": "1-2句中文摘要，包含关键事实",
      "link": "原文链接",
      "source": "来源名称"
    }}
  ],
  "category_summary": "2-3句中文总结本类别今日最重要的新闻"
}}

待翻译文章列表：
{json.dumps(articles_input, ensure_ascii=False)}"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_CATEGORY},
            {"role": "user", "content": user_content},
        ]

        # 调用 API（强制 JSON 模式）
        response = self.client.chat_json(messages)

        # 解析响应
        translated_articles: list[TranslatedArticle] = []
        raw_translated = response.get("translated_articles", [])

        for item in raw_translated:
            idx = item.get("id", -1)
            original = articles[idx] if 0 <= idx < len(articles) else None

            translated_articles.append(TranslatedArticle(
                original_title=original.title if original else item.get("title", ""),
                translated_title=item.get("translated_title", "").strip() or "(翻译失败)",
                translated_summary=item.get("translated_summary", "").strip() or "暂无摘要。",
                link=item.get("link", ""),
                source_name=item.get("source", ""),
            ))

        category_summary = response.get("category_summary", "").strip()
        if not category_summary:
            category_summary = f"今日{category_cn}类新闻已更新 {len(translated_articles)} 篇。"

        return CategoryDigest(
            category=category,
            articles=translated_articles,
            category_summary_cn=category_summary,
        )

    def _fallback_digest(
        self, category: str, articles: list[RawArticle], error_msg: str
    ) -> CategoryDigest:
        """当 API 翻译失败时，使用原文标题构建降级摘要。"""
        category_cn = {
            "Technology": "科技",
            "Politics": "国际政治",
            "Economy": "经济财经",
            "Travel": "旅游",
            "Sports": "体育",
            "Science": "科学",
            "Entertainment": "娱乐",
            "Health": "健康",
            "Gaming": "游戏",
            "Automotive": "汽车",
            "Environment": "环境",
            "Education": "教育",
            "Music": "音乐",
        }.get(category, category)

        fallback_articles = [
            TranslatedArticle(
                original_title=a.title,
                translated_title=a.title,  # 保持原文
                translated_summary=f"[原文] {a.summary[:200]}" if a.summary else "暂无摘要。",
                link=a.link,
                source_name=a.source_name,
            )
            for a in articles[:5]  # 降级时只保留前5篇
        ]

        return CategoryDigest(
            category=category,
            articles=fallback_articles,
            category_summary_cn=(
                f"（{category_cn}类翻译暂时不可用，以下为英文原文。"
                f"错误: {error_msg[:100]}）"
            ),
            is_fallback=True,
        )
