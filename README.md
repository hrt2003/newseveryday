# 📰 Daily Global News Digest — GitHub Pages 版

每 6 小时自动抓取全球科技、政治、经济、旅游新闻，DeepSeek AI 翻译为中文，部署为精美网页。

🌐 **用任意设备打开即看**，无需安装任何 App。

## 快速开始

### 1. Fork 或克隆此仓库

```bash
git clone https://github.com/YOUR_USERNAME/daily-news-digest-github.git
cd daily-news-digest-github
```

### 2. 设置 DeepSeek API Key

在 GitHub 仓库页面:
**Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|------|-------|
| `DEEPSEEK_API_KEY` | `sk-your-deepseek-api-key` |

> 获取 Key: [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)

### 3. 启用 GitHub Pages

**Settings → Pages → Source: GitHub Actions**

### 4. 手动触发首次运行

**Actions → Deploy News Digest to GitHub Pages → Run workflow**

完成后，你的网站就在 `https://YOUR_USERNAME.github.io/daily-news-digest-github/` 上线了！

## 自动更新

工作流每 **6 小时**自动运行一次（UTC 0:00, 6:00, 12:00, 18:00），每次生成最新的新闻摘要并部署到 Pages。

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 创建 .env 文件
echo DEEPSEEK_API_KEY=sk-your-key > .env

# 生成 Markdown + HTML
python main.py --html

# 在浏览器中打开
open output/index.html
```

## 新闻来源

| 分类 | 来源 |
|------|------|
| 💻 科技 | TechCrunch, The Verge, Ars Technica |
| 🌍 国际政治 | BBC World, The Guardian, Al Jazeera |
| 💰 经济财经 | CNBC, MarketWatch, NPR Business |
| ✈️ 旅游 | Skift, The Points Guy |

## 自定义

编辑 `config.json` 可以:
- 增删 RSS 新闻源
- 调整每源抓取文章数
- 修改去重相似度阈值
- 更换 DeepSeek 模型参数

编辑 `templates/base.html` 可以定制网页外观。

## 技术栈

- **Python** — RSS 抓取、DeepSeek API 调用、HTML 生成
- **GitHub Actions** — 每 6 小时自动运行
- **GitHub Pages** — 免费静态网站托管
- **DeepSeek API** — AI 翻译与摘要
- **Editorial Bauhaus** — 网页设计风格（Noto Serif SC + DM Mono 字体）
