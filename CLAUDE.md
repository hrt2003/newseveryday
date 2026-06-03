# CLAUDE.md — Daily Global News Digest

## 项目概述

每 6 小时自动抓取全球新闻，DeepSeek AI 翻译成中文，部署为 GitHub Pages 网页。

- **本地路径**: `e:\项目\daily-news-digest-github\`
- **GitHub 仓库**: `https://github.com/hrt2003/newseveryday`
- **网站地址**: `https://hrt2003.github.io/newseveryday/`
- **当前分支**: `master`

## 技术栈

| 层 | 技术 |
|----|------|
| 新闻抓取 | Python + feedparser + requests（22 个 RSS 源） |
| AI 翻译 | DeepSeek API（deepseek-chat，OpenAI 兼容） |
| HTML 模板 | Jinja-less 纯字符串模板（`templates/base.html`） |
| 定时运行 | GitHub Actions（`cron: 0 */6 * * *`） |
| 部署托管 | GitHub Pages（免费静态托管） |
| 字体 | Noto Serif SC + Noto Sans SC + DM Mono（Google Fonts） |

## 项目结构

```
daily-news-digest-github/
├── main.py                     # CLI 入口（python main.py --html）
├── config.json                 # RSS 源、API 参数、去重阈值
├── requirements.txt            # feedparser, requests, python-dotenv
├── .env.example                # 密钥模板
├── CLAUDE.md                   # 本文件
├── templates/
│   └── base.html               # Editorial Bauhaus 风格网页模板
├── src/
│   ├── config.py               # 配置加载与验证
│   ├── feed_fetcher.py         # RSS 抓取（每源独立重试）
│   ├── deduplicator.py         # Jaccard 相似度去重
│   ├── deepseek_client.py      # DeepSeek API 封装（含 JSON fallback）
│   ├── translator.py           # 翻译 + 摘要 Prompt 工程
│   ├── formatter.py            # Markdown + HTML 输出生成
│   ├── emailer.py              # SMTP 邮件（可选）
│   └── pipeline.py             # 总调度器
├── output/
│   ├── index.html              # 最新日报（GitHub Pages 根文件）
│   └── YYYY-MM-DD-*.md         # 归档 Markdown
├── logs/                       # 轮转日志
└── .github/workflows/
    └── deploy.yml              # 6h 自动部署 + 手动触发
```

## 开发流程（用户偏好）

**始终使用方式一：本地修改 → 测试 → 推送**

```powershell
# 1. 修改代码
# 2. 本地测试
cd "e:\项目\daily-news-digest-github"
python main.py --html

# 3. 确认无误后推送
git add .
git commit -m "描述改动"
git push origin master
# GitHub Actions 自动部署，1-2 分钟后网站更新
```

## 关键配置

### config.json 核心参数

| 参数 | 当前值 | 说明 |
|------|--------|------|
| `deepseek.model` | `deepseek-chat` | DeepSeek 模型 |
| `deepseek.max_tokens` | `16384` | 输出上限（175 篇需要大值） |
| `dedup.similarity_threshold` | `0.6` | 去重相似度阈值 |
| `fetch.max_articles_per_feed` | `8` | 每源最多抓取数 |
| `fetch.max_retries` | `2` | 失败重试次数 |

### GitHub Secrets（必需）

| Secret | 说明 |
|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |

## 网页功能

- **3 张精华头条卡片** — 政治/经济/科技各取第 1 篇
- **4 个可折叠分类模块** — 2×2 网格，默认显示 2 条预览，点击展开全部
- **手动刷新按钮** — 距上次更新 ≥ 2 小时才显示，跳转 Actions 页面触发
- **自动暗色模式** — 跟随系统 `prefers-color-scheme`
- **响应式** — 手机端单列布局
- **北京时间** — 所有时间戳使用 UTC+8

## RSS 源（22 个）

| 分类 | 来源 |
|------|------|
| 💻 科技 (6) | TechCrunch, The Verge, Ars Technica, Wired, The Register, Hacker News |
| 🌍 政治 (6) | BBC World, The Guardian, Al Jazeera, NPR World, France 24, Deutsche Welle |
| 💰 经济 (6) | CNBC, MarketWatch, NPR Business, Yahoo Finance, Investing.com, The Economist |
| ✈️ 旅游 (4) | Skift, The Points Guy, Nomadic Matt, Travel Off Path |

## Token 用量

- 单次运行 175 篇文章，约 37,000 tokens
- 每日 4 次运行，约 150,000 tokens
- 月费用约 ¥12-13（DeepSeek 定价）

## 常见扩展

| 需求 | 改动文件 | 难度 |
|------|----------|------|
| 增删 RSS 源 | `config.json` → feeds + source_priority | 无代码 |
| 调整翻译风格 | `config.json` → deepseek.temperature | 无代码 |
| 改网页配色/字体 | `templates/base.html` → CSS 变量 | 只改 CSS |
| 新增分类 | `config.json` + `templates/base.html` | 10 行 |
| 改手动刷新冷却 | `templates/base.html` → `diffHours >= 2` | 1 个数字 |
