"""
配置加载与验证模块。
从 config.json 和 .env 文件加载配置，并在启动时验证必填项。
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class ConfigError(Exception):
    """配置错误（致命，应阻止程序运行）。"""
    pass


@dataclass
class Feed:
    """单个 RSS 新闻源配置。"""
    name: str
    url: str
    category: str


@dataclass
class SmtpConfig:
    """SMTP 邮件发送配置（可选）。"""
    host: str
    port: int
    user: str
    password: str
    to: list[str]


@dataclass
class Config:
    """完整应用配置，合并 config.json 与 .env。"""
    feeds: dict[str, list[Feed]]
    source_priority: list[str]
    dedup_threshold: float
    max_articles_per_feed: int
    request_timeout: int
    max_retries: int
    retry_backoff_factor: float
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    deepseek_temperature: float
    deepseek_max_tokens: int
    deepseek_timeout: int
    output_dir: str
    filename_template: str
    smtp: Optional[SmtpConfig] = None
    email_enabled: bool = False
    email_subject_template: str = "Daily News Digest - {date}"

    @classmethod
    def from_files(cls, config_path: str, env_path: str = ".env") -> "Config":
        """从 config.json 与 .env 文件加载并验证配置。"""
        # 加载 .env（如果存在）
        env_values = {}
        if os.path.exists(env_path):
            from dotenv import load_dotenv
            load_dotenv(env_path, override=True)
            env_values = dict(os.environ)

        # 加载 JSON 配置
        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # 解析 feeds
        feeds: dict[str, list[Feed]] = {}
        for category, feed_list in raw.get("feeds", {}).items():
            feeds[category] = [
                Feed(
                    name=f["name"],
                    url=f["url"],
                    category=category,
                )
                for f in feed_list
            ]

        # 解析 DeepSeek 配置
        ds = raw.get("deepseek", {})
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                "缺少 DEEPSEEK_API_KEY 环境变量。\n"
                "请复制 .env.example 为 .env 并填入你的 API Key。\n"
                "获取地址: https://platform.deepseek.com/api_keys"
            )

        # 解析 SMTP 配置（可选）
        smtp = None
        email_enabled = raw.get("email", {}).get("enabled", False)
        smtp_host = os.getenv("SMTP_HOST", "").strip()
        if email_enabled and smtp_host:
            smtp_to_raw = os.getenv("SMTP_TO", "").strip()
            if not smtp_to_raw:
                raise ConfigError("启用了邮件但缺少 SMTP_TO 环境变量")
            smtp = SmtpConfig(
                host=smtp_host,
                port=int(os.getenv("SMTP_PORT", "587")),
                user=os.getenv("SMTP_USER", "").strip(),
                password=os.getenv("SMTP_PASSWORD", "").strip(),
                to=[addr.strip() for addr in smtp_to_raw.split(",") if addr.strip()],
            )
            if not smtp.user or not smtp.password:
                raise ConfigError("SMTP 配置不完整：缺少 SMTP_USER 或 SMTP_PASSWORD")

        fetch = raw.get("fetch", {})
        output = raw.get("output", {})
        dedup = raw.get("dedup", {})

        config = cls(
            feeds=feeds,
            source_priority=raw.get("source_priority", []),
            dedup_threshold=dedup.get("similarity_threshold", 0.6),
            max_articles_per_feed=fetch.get("max_articles_per_feed", 8),
            request_timeout=fetch.get("request_timeout_seconds", 30),
            max_retries=fetch.get("max_retries", 2),
            retry_backoff_factor=fetch.get("retry_backoff_factor", 2.0),
            deepseek_api_key=api_key,
            deepseek_base_url=ds.get("base_url", "https://api.deepseek.com/v1"),
            deepseek_model=ds.get("model", "deepseek-chat"),
            deepseek_temperature=ds.get("temperature", 0.3),
            deepseek_max_tokens=ds.get("max_tokens", 4096),
            deepseek_timeout=ds.get("request_timeout_seconds", 90),
            output_dir=output.get("directory", "output"),
            filename_template=output.get("filename_template", "{date}-news-digest.md"),
            smtp=smtp,
            email_enabled=email_enabled,
            email_subject_template=raw.get("email", {}).get("subject_template", "Daily News Digest - {date}"),
        )

        # 验证
        config._validate()
        return config

    def _validate(self) -> None:
        """验证配置完整性。"""
        if not self.feeds:
            raise ConfigError("config.json 中没有配置任何 RSS 新闻源")

        total_feeds = sum(len(fl) for fl in self.feeds.values())
        if total_feeds == 0:
            raise ConfigError("config.json 中所有分类的新闻源列表均为空")

        # 验证每个 feed 的 URL
        for category, feed_list in self.feeds.items():
            for feed in feed_list:
                if not feed.url.startswith("http"):
                    raise ConfigError(
                        f"无效的 RSS URL: [{feed.name}] {feed.url}"
                    )

        if not (0.0 <= self.dedup_threshold <= 1.0):
            raise ConfigError(
                f"相似度阈值必须在 0.0~1.0 之间，当前值: {self.dedup_threshold}"
            )

    def get_all_feeds(self) -> list[Feed]:
        """获取所有新闻源的扁平列表。"""
        result = []
        for feed_list in self.feeds.values():
            result.extend(feed_list)
        return result

    def get_source_rank(self, name: str) -> int:
        """获取新闻源的优先级排名（数字越小越优先）。"""
        try:
            return self.source_priority.index(name)
        except ValueError:
            return len(self.source_priority)  # 未列出的排在最后
