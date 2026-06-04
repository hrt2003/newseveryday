"""
格式化输出模块。
将翻译后的新闻摘要格式化为 Markdown 日报和精美 HTML 网页。
HTML 基于 templates/base.html 模板（Editorial Bauhaus 设计风格）。
"""

from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .translator import CategoryDigest

# 北京时间 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

# ── 常量映射 ────────────────────────────────────────────────────

CATEGORY_NAMES_CN: dict[str, str] = {
    "Technology": "💻 科技",
    "Politics": "🌍 国际政治",
    "Economy": "💰 经济财经",
    "Travel": "✈️ 旅游",
    "Sports": "⚽ 体育",
    "Science": "🔬 科学",
    "Entertainment": "🎬 娱乐",
    "Health": "🏥 健康",
    "Gaming": "🎮 游戏",
    "Automotive": "🚗 汽车",
    "Environment": "🌱 环境",
    "Education": "📚 教育",
    "Music": "🎵 音乐",
}

CAT_CSS_CLASS: dict[str, str] = {
    "Technology": "technology",
    "Politics": "politics",
    "Economy": "economy",
    "Travel": "travel",
    "Sports": "sports",
    "Science": "science",
    "Entertainment": "entertainment",
    "Health": "health",
    "Gaming": "gaming",
    "Automotive": "automotive",
    "Environment": "environment",
    "Education": "education",
    "Music": "music",
}

CAT_DOT_CLASS: dict[str, str] = {
    "Technology": "dot-tech",
    "Politics": "dot-politics",
    "Economy": "dot-economy",
    "Travel": "dot-travel",
    "Sports": "dot-sports",
    "Science": "dot-science",
    "Entertainment": "dot-entertainment",
    "Health": "dot-health",
    "Gaming": "dot-gaming",
    "Automotive": "dot-automotive",
    "Environment": "dot-environment",
    "Education": "dot-education",
    "Music": "dot-music",
}

CATEGORY_ORDER = ["Politics", "Economy", "Technology", "Sports", "Science",
                   "Entertainment", "Health", "Gaming", "Automotive",
                   "Environment", "Education", "Music", "Travel"]

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
        gen_time = generation_time or datetime.now(BEIJING_TZ)
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

    # 精华头条来源优先级（取各分类第1篇）
    FEATURED_ORDER = ["Politics", "Economy", "Technology"]
    FEATURED_FALLBACK = "Travel"

    def build_html(
        self,
        report_date: date,
        overall_digest: str,
        category_digests: list[CategoryDigest],
        fetch_errors: dict[str, list[str]] | None = None,
        generation_time: datetime | None = None,
    ) -> str:
        """使用 templates/base.html 模板构建模块化 HTML 网页。"""
        gen_time = generation_time or datetime.now(BEIJING_TZ)
        fetch_errors = fetch_errors or {}

        # 读取模板
        template_path = TEMPLATE_DIR / "base.html"
        if template_path.exists():
            template = template_path.read_text(encoding="utf-8")
        else:
            template = _FALLBACK_TEMPLATE

        # 生成各 HTML 片段（模块化布局）
        digest_map = {cd.category: cd for cd in category_digests}
        featured_stories = self._build_featured_stories(digest_map)
        category_modules = self._build_category_modules(category_digests)
        sources_rows = self._build_sources_rows(category_digests)
        errors_html = self._build_errors_html(fetch_errors)
        search_data = self._build_search_data_json(category_digests)

        # 填充模板
        format_args = dict(
            report_date=report_date.strftime("%Y年%m月%d日"),
            gen_time=gen_time.strftime("%Y-%m-%d %H:%M"),
            overall_digest=_escape_html(overall_digest),
            featured_stories=featured_stories,
            category_modules=category_modules,
            sources_rows=sources_rows,
            errors_html=errors_html,
        )
        # 只有模板包含 {search_data} 时才传入（兼容旧回退模板）
        if "{search_data}" in template:
            format_args["search_data"] = search_data
        return template.format(**format_args)

    def _build_featured_stories(
        self, digest_map: dict[str, CategoryDigest]
    ) -> str:
        """生成 3 张精华头条卡片（政治/经济/科技各取第1篇）。"""
        cards = []
        used_ids: set[str] = set()  # 避免同一篇文章重复出现

        for cat in self.FEATURED_ORDER:
            cd = digest_map.get(cat)
            article = None
            if cd and cd.articles:
                article = cd.articles[0]
                used_ids.add(article.link)

            if not article and self.FEATURED_FALLBACK:
                # 用 Travel 替补
                fd = digest_map.get(self.FEATURED_FALLBACK)
                if fd and fd.articles:
                    for a in fd.articles:
                        if a.link not in used_ids:
                            article = a
                            used_ids.add(a.link)
                            break

            if article:
                cn_name = CATEGORY_NAMES_CN.get(cat, cat)
                cat_key = cat.lower()
                cards.append(f"""\
                <article class="feature-card {cat_key}">
                    <div class="feature-badge">{cn_name}</div>
                    <h3>{_escape_html(article.translated_title)}</h3>
                    <p class="feature-summary">{_escape_html(article.translated_summary)}</p>
                    <div class="feature-meta">
                        <a href="{_escape_html(article.link)}" target="_blank" rel="noopener">阅读原文 ↗</a>
                        <span>{_escape_html(article.source_name)}</span>
                    </div>
                </article>""")

        return "\n".join(cards) if cards else '<p class="no-news">暂无精华头条。</p>'

    def _build_category_modules(
        self, category_digests: list[CategoryDigest]
    ) -> str:
        """生成 2×2 可折叠分类模块。"""
        modules = []
        for cd in category_digests:
            cn_name = CATEGORY_NAMES_CN.get(cd.category, cd.category)
            css_class = CAT_CSS_CLASS.get(cd.category, "politics")
            dot_class = CAT_DOT_CLASS.get(cd.category, "dot-politics")
            cat_id = cd.category.lower()

            article_count = len(cd.articles)

            if cd.articles:
                # 预览区：只显示前 2 篇
                preview_html = ""
                for i, a in enumerate(cd.articles[:2], 1):
                    preview_html += f"""\
                    <div class="preview-item">
                        <span class="preview-num">{i:02d}</span>
                        <span class="preview-title">{_escape_html(a.translated_title)}</span>
                    </div>"""

                # 完整区：显示全部（默认隐藏）
                full_html = ""
                for i, a in enumerate(cd.articles, 1):
                    full_html += f"""\
                    <article class="news-item">
                        <h3><span class="item-num">{i:02d}</span> {_escape_html(a.translated_title)}</h3>
                        <p class="item-summary">{_escape_html(a.translated_summary)}</p>
                        <div class="item-meta">
                            <a href="{_escape_html(a.link)}" target="_blank" rel="noopener" class="item-link">阅读原文</a>
                            <span class="item-source">{_escape_html(a.source_name)}</span>
                        </div>
                    </article>"""

                expand_btn = f"""\
                <button class="expand-btn" data-target="{cat_id}-full" aria-expanded="false">
                    <span class="btn-text">展开全部 {article_count} 篇</span>
                    <span class="btn-icon">▾</span>
                </button>"""

            else:
                preview_html = '<p class="no-news">今日无相关新闻。</p>'
                full_html = ""
                expand_btn = ""

            modules.append(f"""\
            <section class="category-module {css_class}" id="module-{cat_id}">
                <div class="module-header">
                    <span class="category-dot {dot_class}"></span>
                    <h2>{cn_name}</h2>
                    <span class="article-count">{article_count} 篇</span>
                </div>
                <div class="module-preview">
                    {preview_html}
                </div>
                {expand_btn}
                <div class="module-expanded" id="{cat_id}-full">
                    <div class="articles-list">
                        {full_html}
                    </div>
                    <button class="collapse-btn" data-target="{cat_id}-full">
                        <span>收起</span>
                        <span class="btn-icon">▴</span>
                    </button>
                </div>
            </section>""")

        return "\n".join(modules)

    def _build_category_cards(self, category_digests: list[CategoryDigest]) -> str:
        """生成所有分类卡片的 HTML（旧版平铺，保留兼容）。"""
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

    def _build_search_data_json(
        self, category_digests: list[CategoryDigest]
    ) -> str:
        """生成当天所有文章的 JSON 数据（嵌入页面供搜索用）。"""
        import json as _json
        articles = []
        for cd in category_digests:
            for a in cd.articles:
                articles.append({
                    "title": a.translated_title,
                    "summary": a.translated_summary,
                    "source": a.source_name,
                    "link": a.link,
                    "category": cd.category,
                    "category_cn": CATEGORY_NAMES_CN.get(cd.category, cd.category),
                })
        return _json.dumps(articles, ensure_ascii=False)

    def build_archive_page(self) -> Path | None:
        """扫描 docs/ 中所有历史文件，生成归档索引页 archive.html。"""
        import json as _json
        import re as _re

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 扫描所有 *-news-digest.html 文件
        history: dict[str, dict[str, list[tuple[str, str]]]] = {}  # year → month → [(date, path)]
        pattern = _re.compile(r"^(\d{4})-(\d{2})-(\d{2})-news-digest\.html$")

        for f in sorted(self.output_dir.glob("*-news-digest.html"), reverse=True):
            m = pattern.match(f.name)
            if m:
                year, month, day = m.group(1), m.group(2), m.group(3)
                date_str = f"{year}-{month}-{day}"
                if year not in history:
                    history[year] = {}
                if month not in history[year]:
                    history[year][month] = []
                history[year][month].append((date_str, f.name))

        if not history:
            return None

        # 构建归档 HTML
        archive_template_path = TEMPLATE_DIR / "archive.html"
        if archive_template_path.exists():
            template = archive_template_path.read_text(encoding="utf-8")
        else:
            template = _ARCHIVE_FALLBACK

        # 生成年月列表
        year_sections = ""
        for year in sorted(history.keys(), reverse=True):
            months_html = ""
            for month in sorted(history[year].keys(), reverse=True):
                month_name = f"{int(month):02d}月"
                dates_html = ""
                for date_str, filename in history[year][month]:
                    dates_html += (
                        f'<li><a href="{filename}">{date_str}</a></li>'
                    )
                months_html += f"""
                <div class="archive-month">
                    <h3>{month_name}</h3>
                    <ul class="archive-dates">{dates_html}</ul>
                </div>"""

            year_sections += f"""
            <section class="archive-year">
                <h2>{year} 年</h2>
                <div class="archive-months-grid">{months_html}</div>
            </section>"""

        total_days = sum(len(dates) for ym in history.values() for dates in ym.values())
        html = template.format(
            gen_time=datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M"),
            total_days=str(total_days),
            year_sections=year_sections,
        )

        archive_path = self.output_dir / "archive.html"
        archive_path.write_text(html, encoding="utf-8")
        return archive_path

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
<div class="featured-grid">{featured_stories}</div>
<div class="module-grid">{category_modules}</div>
<section class="sources-section"><h2>📊 数据来源</h2><table>{sources_rows}</table></section>
{errors_html}
</main>
<footer><p>本日报由脚本自动生成，内容由 <strong>DeepSeek AI</strong> 翻译与摘要</p></footer>
</body>
</html>"""


_ARCHIVE_FALLBACK = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>新闻归档 — 全球新闻日报</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700;900&family=Noto+Sans+SC:wght@300;400;500;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
    :root {{
        --bg: #faf9f6;
        --surface: #ffffff;
        --text: #1c1917;
        --text-secondary: #5c5a57;
        --text-tertiary: #8c8a85;
        --border: #e7e4df;
        --radius: 16px;
    }}
    @media (prefers-color-scheme: dark) {{
        :root {{ --bg:#171717; --surface:#24221f; --text:#e8e4e0; --text-secondary:#a8a5a0; --text-tertiary:#787570; --border:#33302b; }}
    }}
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family: 'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif; background:var(--bg); color:var(--text); line-height:1.75; min-height:100vh; }}
    .masthead {{ text-align:center; padding:48px 24px 36px; border-bottom:1px solid var(--border); }}
    .masthead h1 {{ font-family:'Noto Serif SC',serif; font-size:2rem; font-weight:900; }}
    .masthead .sub {{ color:var(--text-tertiary); font-size:0.85rem; margin-top:6px; }}
    .masthead .back {{ margin-top:12px; }}
    .masthead .back a {{ color:var(--text-secondary); font-size:0.8rem; text-decoration:none; }}
    .masthead .back a:hover {{ text-decoration:underline; }}
    .container {{ max-width:760px; margin:0 auto; padding:32px 24px 80px; }}
    .archive-year {{ margin-bottom:36px; }}
    .archive-year h2 {{ font-family:'Noto Serif SC',serif; font-size:1.4rem; margin-bottom:16px; padding-bottom:8px; border-bottom:2px solid var(--border); }}
    .archive-months-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:20px; }}
    .archive-month h3 {{ font-family:'DM Mono',monospace; font-size:0.75rem; letter-spacing:0.2em; color:var(--text-tertiary); margin-bottom:8px; }}
    .archive-dates {{ list-style:none; }}
    .archive-dates li {{ padding:4px 0; }}
    .archive-dates a {{ color:var(--text); text-decoration:none; font-size:0.9rem; font-family:'DM Mono',monospace; }}
    .archive-dates a:hover {{ text-decoration:underline; opacity:0.7; }}
    footer {{ text-align:center; padding:24px; color:var(--text-tertiary); font-size:0.75rem; }}
    @media (max-width:640px) {{ .archive-months-grid {{ grid-template-columns:1fr 1fr; }} }}
</style>
</head>
<body>
<header class="masthead">
    <h1>📅 新闻归档</h1>
    <div class="sub">共 {total_days} 天历史记录 · 更新于 {gen_time}</div>
    <div class="back"><a href="index.html">← 返回最新日报</a></div>
</header>
<main class="container">
    {year_sections}
</main>
<footer><p>所有新闻版权归原来源所有</p></footer>
</body>
</html>"""
