"""
总调度器模块。
将抓取、去重、翻译、格式化、邮件发送等步骤串联为完整的流水线。
"""

import logging
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from .config import Config

# 北京时间 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))
from .feed_fetcher import FeedFetcher, FetchResult
from .deduplicator import Deduplicator
from .deepseek_client import DeepSeekClient
from .translator import Translator
from .formatter import Formatter
from .emailer import Emailer

logger = logging.getLogger("news_digest.pipeline")


class Pipeline:
    """每日新闻摘要生成流水线。

    将所有处理步骤串联：
    1. 抓取 RSS
    2. 去重
    3. 翻译 + 摘要
    4. 格式化 Markdown
    5. 写入文件
    6. 可选发送邮件
    """

    def __init__(self, config: Config):
        self.config = config

        # 初始化各组件
        self.fetcher = FeedFetcher(
            feeds=config.feeds,
            timeout=config.request_timeout,
            max_retries=config.max_retries,
            backoff_factor=config.retry_backoff_factor,
            max_articles=config.max_articles_per_feed,
        )

        self.deduplicator = Deduplicator(
            threshold=config.dedup_threshold,
            get_source_rank=config.get_source_rank,
        )

        self.deepseek = DeepSeekClient(
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            model=config.deepseek_model,
            temperature=config.deepseek_temperature,
            max_tokens=config.deepseek_max_tokens,
            timeout=config.deepseek_timeout,
        )

        self.translator = Translator(client=self.deepseek)

        self.formatter = Formatter(
            output_dir=config.output_dir,
            filename_template=config.filename_template,
        )

        self.emailer = None
        if config.email_enabled and config.smtp:
            self.emailer = Emailer(config.smtp)

    def run(
        self,
        categories: list[str] | None = None,
        send_email: bool = True,
        output_html: bool = False,
    ) -> Path:
        """执行完整的新闻摘要生成流水线。

        Args:
            categories: 要处理的分类列表，None 表示全部。
            send_email: 是否发送邮件（仅在 emailer 已配置时生效）。
            output_html: 是否同时生成 HTML 网页（用于 GitHub Pages）。

        Returns:
            生成的主输出文件路径。
        """
        today = date.today()
        start_time = datetime.now(BEIJING_TZ)

        step_count = 7 if output_html else 6
        logger.info("=" * 60)
        logger.info(f"开始生成 {today} 新闻日报...")
        logger.info("=" * 60)

        # 1. 抓取 RSS
        logger.info(f"[1/{step_count}] 抓取 RSS 新闻源...")
        fetch_results = self.fetcher.fetch_all()

        # 收集抓取错误
        fetch_errors: dict[str, list[str]] = {}
        for cat, result in fetch_results.items():
            if result.errors:
                fetch_errors[cat] = result.errors

        total_articles = sum(len(r.articles) for r in fetch_results.values())
        total_errors = sum(len(r.errors) for r in fetch_results.values())
        logger.info(f"  共抓取 {total_articles} 篇文章，{total_errors} 个源失败")

        if total_articles == 0:
            raise RuntimeError(
                "所有新闻源均抓取失败。请检查网络连接和 config.json 中的 RSS URL。"
            )

        # 按分类组织文章
        articles_by_category: dict[str, list] = {}
        for cat, result in fetch_results.items():
            if categories and cat not in categories:
                continue
            articles_by_category[cat] = result.articles

        # 2. 去重
        logger.info(f"[2/{step_count}] 去重...")
        deduped = self.deduplicator.deduplicate(articles_by_category)
        after_dedup = sum(len(v) for v in deduped.values())
        logger.info(f"  去重后: {after_dedup} 篇文章")

        # 3. 翻译 + 摘要
        logger.info(f"[3/{step_count}] DeepSeek 翻译与摘要生成...")
        category_digests = self.translator.translate_all(deduped)

        # 4. 全局摘要
        logger.info(f"[4/{step_count}] 生成全局摘要...")
        overall_digest = self.translator.create_overall_digest(category_digests)

        # 5. 构建 Markdown 并写入文件
        logger.info(f"[5/{step_count}] 生成 Markdown 日报...")
        markdown = self.formatter.build_markdown(
            report_date=today,
            overall_digest=overall_digest,
            category_digests=category_digests,
            fetch_errors=fetch_errors,
            generation_time=start_time,
        )
        output_path = self.formatter.write_file(markdown, report_date=today)
        logger.info(f"  日报 Markdown 已保存至: {output_path}")

        # 6. 生成 HTML（可选）
        if output_html:
            logger.info(f"[6/{step_count}] 生成 HTML 网页...")
            html = self.formatter.build_html(
                report_date=today,
                overall_digest=overall_digest,
                category_digests=category_digests,
                fetch_errors=fetch_errors,
                generation_time=start_time,
            )
            html_path = self.formatter.write_html(html, report_date=today)
            logger.info(f"  日报 HTML 已保存至: {html_path}")

        # 7. 发送邮件（可选）
        step_n = 7 if output_html else 6
        if send_email and self.emailer:
            logger.info(f"[{step_n}/{step_count}] 发送邮件...")
            subject = self.config.email_subject_template.format(
                date=today.strftime("%Y-%m-%d")
            )
            self.emailer.send_or_warn(subject, markdown)
        else:
            logger.info(f"[{step_n}/{step_count}] 跳过邮件发送")

        elapsed = (datetime.now(BEIJING_TZ) - start_time).total_seconds()
        logger.info(f"✓ 完成！总耗时 {elapsed:.1f}s")
        logger.info("=" * 60)

        return output_path
