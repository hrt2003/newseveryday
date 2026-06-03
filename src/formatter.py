"""
格式化输出模块。
将翻译后的新闻摘要格式化为 Markdown 日报和精美 HTML 网页。
HTML 基于 templates/base.html 模板（Editorial Bauhaus 设计风格）。
"""

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .translator import CategoryDigest

# ── 常量映射 ────────────────────────────────────────────────────

CATEGORY_NAMES_CN: dict[str, str] = {
    "Technology": "💻 科技",
    "Politics": "🌍 国际政治",
    "Economy": "💰 经济财经",
    "Travel": "✈️ 旅游",
}

CAT_CSS_CLASS: dict[str, str] = {
    "Technology": "technology",
    "Politics": "politics",
    "Economy": "economy",
    "Travel": "travel",
}

CAT_DOT_CLASS: dict[str, str] = {
    "Technology": "dot-tech",
    "Politics": "dot-politics",
    "Economy": "dot-economy",
    "Travel": "dot-travel",
}

CATEGORY_ORDER = ["Politics", "Economy", "Technology", "Travel"]

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符。"""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
    )


class Formatter:
    """日报格式化器。

    支持两种输出格式：
    - Markdown：适合本地阅读和邮件发送
    - HTML：基于精美模板，适合 GitHub Pages 部署
    """

    def __init__(self, output_dir: str = "output", filename_template: str = "{date}-news-digest.md"):
        self.output_dir = Path(output_dir)
        self.filename_template = filename_template

    # ── Markdown 输出 ─────────────────────────────────────────

    def build_markdown(
        self,
        report_date: date,
        overall_digest: str,
        category_digests: list[CategoryDigest],
        fetch_errors: dict[str, list[str]] | None = None,
        generation_time: Optional[datetime] = None,
    ) -> str:
        """构建完整的 Markdown 日报。"""
        gen_time = generation_time or datetime.now()
        fetch_errors = fetch_errors or {}
        lines: list[str] = []

        lines.extend([
            f"# 📰 全球新闻日报", "",
            f"**{report_date.strftime('%Y年%m月%d日')}** | "
            f"生成时间: {gen_time.strftime('%Y-%m-%d %H:%M')}", "",
            "---", "",
            "## 📋 今日摘要", "",
            f"{overall_digest}", "",
            "---", "",
        ])

        for cd in category_digests:
            cn_name = CATEGORY_NAMES_CN.get(cd.category, cd.category)
            lines.append(f"## {cn_name}")
            lines.append("")
            if cd.category_summary_cn:
                lines.append(f"> {cd.category_summary_cn}")
                lines.append("")
            if cd.is_fallback:
                lines.append("⚠️ *本分类翻译暂时不可用，以下为英文原文。*")
                lines.append("")
            if cd.articles:
                for i, a in enumerate(cd.articles, 1):
                    lines.append(f"### {i}. {a.translated_title}")
                    lines.append("")
                    lines.append(f"{a.translated_summary}")
                    lines.append("")
                    lines.append(f"📎 [阅读原文]({a.link}) — *{a.source_name}*")
                    lines.append("")
            else:
                lines.append("*今日无相关新闻。*")
                lines.append("")
            lines.append("---")
            lines.append("")

        lines.append("## 📊 数据来源")
        lines.append("")
        for cd in category_digests:
            cn_name = CATEGORY_NAMES_CN.get(cd.category, cd.category)
            sources = list(dict.fromkeys(a.source_name for a in cd.articles)) if cd.articles else []
            sources_str = "、".join(sources) if sources else "无"
            lines.append(f"- **{cn_name}**: {sources_str}")
        lines.append("")

        if fetch_errors:
            all_errors = []
            for cat, errors in fetch_errors.items():
                if errors:
                    cn_name = CATEGORY_NAMES_CN.get(cat, cat)
                    all_errors.append(f"- **{cn_name}**: {', '.join(errors)}")
            if all_errors:
                lines.append("## ⚠️ 今日故障源")
                lines.append("")
                lines.extend(all_errors)
                lines.append("")

        lines.extend([
            "---", "",
            "*本日报由脚本自动生成，内容由 DeepSeek AI 翻译和摘要。*",
            "*所有新闻版权归原来源所有。*",
        ])

        return "\n".join(lines)

    # ── HTML 输出（基于精美模板）─────────────────────────────────

    def build_html(
        self,
        report_date: date,
        overall_digest: str,
        category_digests: list[CategoryDigest],
        fetch_errors: dict[str, list[str]] | None = None,
        generation_time: datetime | None = None,
    ) -> str:
        """使用 templates/base.html 模板构建精美 HTML 网页。"""
        gen_time = generation_time or datetime.now()
        fetch_errors = fetch_errors or {}

        # 读取模板
        template_path = TEMPLATE_DIR / "base.html"
        if template_path.exists():
            template = template_path.read_text(encoding="utf-8")
        else:
            # 回退：模板文件不存在时使用简化版本
            template = _FALLBACK_TEMPLATE

        # 生成各 HTML 片段
        category_cards = self._build_category_cards(category_digests)
        sources_rows = self._build_sources_rows(category_digests)
        errors_html = self._build_errors_html(fetch_errors)

        # 填充模板
        return template.format(
            report_date=report_date.strftime("%Y年%m月%d日"),
            gen_time=gen_time.strftime("%Y-%m-%d %H:%M"),
            overall_digest=_escape_html(overall_digest),
            category_cards=category_cards,
            sources_rows=sources_rows,
            errors_html=errors_html,
        )

    def _build_category_cards(self, category_digests: list[CategoryDigest]) -> str:
        """生成所有分类卡片的 HTML。"""
        cards = []
        for cd in category_digests:
            cn_name = CATEGORY_NAMES_CN.get(cd.category, cd.category)
            css_class = CAT_CSS_CLASS.get(cd.category, "politics")
            dot_class = CAT_DOT_CLASS.get(cd.category, "dot-politics")

            # 文章列表
            if cd.articles:
                articles_html = ""
                for i, a in enumerate(cd.articles, 1):
                    articles_html += f"""\
                    <article class="news-item">
                        <h3><span class="item-num">{i:02d}</span> {_escape_html(a.translated_title)}</h3>
                        <p class="item-summary">{_escape_html(a.translated_summary)}</p>
                        <div class="item-meta">
                            <a href="{_escape_html(a.link)}" target="_blank" rel="noopener" class="item-link">阅读原文</a>
                            <span class="item-source">{_escape_html(a.source_name)}</span>
                        </div>
                    </article>
"""
            else:
                articles_html = '<p class="no-news">今日无相关新闻。</p>'

            # 分类摘要
            summary_html = ""
            if cd.category_summary_cn:
                summary_html = (
                    f'<div class="category-summary">{_escape_html(cd.category_summary_cn)}</div>'
                )

            # 降级标记
            fallback_html = ""
            if cd.is_fallback:
                fallback_html = '<p class="fallback-note">⚠️ 本分类翻译暂时不可用，以下为英文原文。</p>'

            article_count = len(cd.articles)
            cards.append(f"""\
            <section class="category-card {css_class}">
                <div class="category-header">
                    <span class="category-dot {dot_class}"></span>
                    <h2>{cn_name}</h2>
                    <span class="article-count">{article_count} 篇</span>
                </div>
                {fallback_html}
                {summary_html}
                <div class="articles-list">
                    {articles_html}
                </div>
            </section>""")

        return "\n".join(cards)

    def _build_sources_rows(self, category_digests: list[CategoryDigest]) -> str:
        """生成数据来源表格行。"""
        rows = []
        for cd in category_digests:
            cn_name = CATEGORY_NAMES_CN.get(cd.category, cd.category)
            sources = list(dict.fromkeys(a.source_name for a in cd.articles)) if cd.articles else []
            sources_str = "、".join(_escape_html(s) for s in sources) if sources else "无"
            rows.append(f"<tr><td>{cn_name}</td><td>{sources_str}</td></tr>")
        return "\n".join(rows)

    def _build_errors_html(self, fetch_errors: dict[str, list[str]]) -> str:
        """生成抓取故障提示 HTML。"""
        if not fetch_errors:
            return ""

        error_items = []
        for cat, errors in fetch_errors.items():
            if errors:
                cn_name = CATEGORY_NAMES_CN.get(cat, cat)
                error_items.append(
                    f"<li>{_escape_html(cn_name)}: "
                    f"{', '.join(_escape_html(e) for e in errors)}</li>"
                )

        if not error_items:
            return ""

        return f"""\
            <section class="errors-section">
                <h2>⚠️ 今日故障源</h2>
                <ul>
                    {"".join(error_items)}
                </ul>
            </section>"""

    # ── 文件写入 ──────────────────────────────────────────────

    def write_html(
        self,
        html: str,
        report_date: date | None = None,
    ) -> Path:
        """写入 HTML 文件，同时更新 index.html 作为最新日报。"""
        report_date = report_date or date.today()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 日期命名文件（归档）
        filepath = self.output_dir / f"{report_date.strftime('%Y-%m-%d')}-news-digest.html"
        filepath.write_text(html, encoding="utf-8")

        # index.html（始终指向最新）
        index_path = self.output_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")

        return filepath

    def write_file(
        self,
        markdown: str,
        report_date: Optional[date] = None,
    ) -> Path:
        """写入 Markdown 文件。"""
        report_date = report_date or date.today()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        filename = self.filename_template.format(date=report_date.strftime("%Y-%m-%d"))
        filepath = self.output_dir / filename
        filepath.write_text(markdown, encoding="utf-8")
        return filepath


# ── 回退模板（模板文件缺失时使用）────────────────────────────────

_FALLBACK_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>全球新闻日报 — {report_date}</title>
<style>
    :root {{
        --bg: #faf9f6;
        --surface: #ffffff;
        --text: #1c1917;
        --text-secondary: #5c5a57;
        --border: #e7e4df;
        --accent-tech: #2563eb;
        --accent-politics: #c2410c;
        --accent-economy: #b45309;
        --accent-travel: #047857;
        --radius: 16px;
    }}
    @media (prefers-color-scheme: dark) {{
        :root {{ --bg:#171717; --surface:#24221f; --text:#e8e4e0; --text-secondary:#a8a5a0; --border:#33302b; }}
    }}
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif; background:var(--bg); color:var(--text); line-height:1.75; }}
    .masthead {{ text-align:center; padding:48px 24px 36px; border-bottom:1px solid var(--border); }}
    .masthead h1 {{ font-family:'Noto Serif SC',serif; font-size:2.2rem; font-weight:900; }}
    .dateline {{ color:var(--text-secondary); font-size:0.9rem; margin-top:8px; }}
    .main-container {{ max-width:880px; margin:0 auto; padding:32px 24px 80px; }}
    .overall-digest {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:36px; margin-bottom:40px; }}
    .overall-digest p {{ font-size:1.1rem; line-height:1.9; }}
    .category-card {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:32px; margin-bottom:24px; }}
    .category-card h2 {{ font-family:'Noto Serif SC',serif; font-size:1.3rem; margin-bottom:16px; }}
    .category-summary {{ background:var(--bg); padding:14px 18px; border-radius:8px; margin-bottom:20px; color:var(--text-secondary); }}
    .news-item {{ padding:18px 0; border-bottom:1px solid var(--border); }}
    .news-item:last-child {{ border-bottom:none; }}
    .news-item h3 {{ font-size:1.05rem; margin-bottom:6px; }}
    .item-summary {{ font-size:0.9rem; color:var(--text-secondary); margin-bottom:8px; }}
    .item-link {{ font-size:0.82rem; text-decoration:none; }}
    .technology .item-link {{ color:var(--accent-tech); }}
    .politics .item-link {{ color:var(--accent-politics); }}
    .economy .item-link {{ color:var(--accent-economy); }}
    .travel .item-link {{ color:var(--accent-travel); }}
    .sources-section {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:28px; margin-bottom:24px; }}
    .sources-section td {{ padding:8px 12px; border-bottom:1px solid var(--border); }}
    footer {{ text-align:center; padding:24px; color:var(--text-secondary); font-size:0.8rem; }}
    @media (max-width:640px) {{ .masthead h1 {{ font-size:1.6rem; }} .category-card {{ padding:20px 16px; }} }}
</style>
</head>
<body>
<header class="masthead"><h1>全球新闻日报</h1><div class="dateline">{report_date} · 更新于 {gen_time}</div></header>
<main class="main-container">
<section class="overall-digest"><p>{overall_digest}</p></section>
{category_cards}
<section class="sources-section"><h2>📊 数据来源</h2><table>{sources_rows}</table></section>
{errors_html}
</main>
<footer><p>本日报由脚本自动生成，内容由 <strong>DeepSeek AI</strong> 翻译与摘要</p></footer>
</body>
</html>"""
