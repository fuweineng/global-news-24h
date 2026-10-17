# 🌍 24Hr Global News

> Real-time international news aggregation from global RSS feeds

A 24-hour rolling news website similar to 24inf.cn, but with a focus on **international news sources**. Built with GitHub Pages and GitHub Actions - **100% free hosting**.

![GitHub Actions](https://img.shields.io/github/actions/workflow/status/fuoweineng/global-news-24h/update-news.yml)
![GitHub Pages](https://img.shields.io/badge/hosting-GitHub_Pages-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## ✨ Features

- 🔄 **Auto-updates every 30 minutes** via GitHub Actions
- 🌐 **10+ international news sources** (Reuters, BBC, CNN, NHK, DW, France24, etc.)
- 📱 **Responsive design** - works on mobile, tablet, and desktop
- 🏷️ **Category filtering** - General, Business, Asia
- ⚡ **Fast & lightweight** - static site, no backend required
- 💰 **Completely free** - no server costs

## 🚀 Live Demo

Visit: **https://fuoweineng.github.io/global-news-24h/**

## 📁 Project Structure

```
global-news-24h/
├── .github/
│   └── workflows/
│       ├── update-news.yml      # 国际新闻，每 15/60 分钟自动更新
│       └── update-nanhai.yml    # 南海政务新闻，每小时自动更新
├── src/
│   ├── fetch_news.py            # 国际新闻抓取脚本
│   ├── sources.json             # RSS 源配置
│   ├── fetch_nanhai.py          # 南海政务新闻抓取（标准库，无需额外依赖）
│   └── nanhai_sources.json      # 南海栏目 / 搜索 / 标签规则配置
├── docs/
│   ├── index.html               # 国际新闻主页面
│   ├── nanhai.html              # 南海政务页面（含“租金”标签）
│   ├── css/
│   │   ├── style.css            # 主站样式
│   │   └── nanhai.css           # 南海政务页面样式
│   └── js/
│       ├── app.js               # 主站逻辑
│       └── nanhai.js            # 南海政务页面逻辑
├── data/
│   ├── news.json                # 国际新闻数据
│   └── nanhai.json              # 南海政务数据（供页面与 AI 分析）
├── requirements.txt             # Python 依赖
└── README.md                    # This file
```

## 🛠️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/fuoweineng/global-news-24h.git
cd global-news-24h
```

### 2. Enable GitHub Pages

1. Go to **Settings** → **Pages**
2. Under **Source**, select **GitHub Actions**
3. Save

### 3. Configure Actions Permissions

1. Go to **Settings** → **Actions** → **General**
2. Under **Workflow permissions**, select **Read and write permissions**
3. Check **Allow GitHub Actions to create and approve pull requests**
4. Save

### 4. Trigger First Update

1. Go to **Actions** → **Update News**
2. Click **Run workflow**
3. Wait for the workflow to complete (~1-2 minutes)

### 5. Access Your Site

Visit: `https://fuoweineng.github.io/global-news-24h/`

## 📰 News Sources

Current sources include:

| Source | Country | Category |
|--------|---------|----------|
| Reuters | US | General |
| BBC News | UK | General |
| CNN | US | General |
| NHK World | Japan | Asia |
| Deutsche Welle | Germany | General |
| France 24 | France | General |
| SCMP | Hong Kong | Asia |
| The Economist | UK | Business |
| Bloomberg | US | Business |
| Al Jazeera | Qatar | General |

Want to add more sources? Edit `src/sources.json`!

## 🏛 南海政务模块（Nanhai Gov）

独立模块：抓取**佛山市南海区人民政府网**政务新闻，并自动打标，重点跟踪**租金**相关条目。
与 souse 等下游项目解耦——只产出结构化数据，不并入 souse 代码库。

- 页面：`https://news.neng.page/nanhai.html`
- 数据：`data/nanhai.json`（同步复制到 `docs/data/nanhai.json` 供页面读取）
- 抓取：`python src/fetch_nanhai.py`（仅用标准库，CI 无需 pip 安装）

### 数据来源

| 来源 | 说明 |
|------|------|
| 南海区政府网栏目 | 工作动态 / 部门动态 / 镇街要闻 / 通知公告 / 南海新闻（每栏最新 20 条） |
| 广东省政务搜索 API | `search.gd.gov.cn`（站点 757006）关键词「房租 / 租金」，覆盖历年政策、公示、招标等 |

### 标签规则

`src/nanhai_sources.json` 中 `tags` 定义关键词 → 标签映射：租金、公租房、物业、停车、住房、教育、医疗、社保、交通、产业、政策、文化、安全。
命中租金类关键词的条目会标记 `is_rent: true`，页面上有「租金」筛选与高亮，并从正文中摘出**租金要点**句子。

### nanhai.json 结构

```json
{
  "updated": "2026-10-17T05:22:09+00:00",
  "region": "佛山市南海区",
  "total": 149,
  "rent_total": 50,
  "stats": { "by_category": {}, "by_tag": {}, "rent": 50 },
  "articles": [
    {
      "id": "nh9f2c1a0b3d",
      "title": "2026年桂城街道各项目公租房租金核准收费标准",
      "link": "http://www.nanhai.gov.cn/...",
      "published": "2026-06-11",
      "category": "政策公告",
      "source": "佛山市南海区住房城乡建设和水务局",
      "sources": ["佛山市南海区住房城乡建设和水务局"],
      "tags": ["租金", "公租房", "住房", "政策"],
      "is_rent": true,
      "summary": "……",
      "rent_snippets": ["……租金标准……"],
      "attachments": [
        { "name": "附件：佛山市南海区2025年公共租赁住房租金政府指导价目表.pdf",
          "url": "http://www.nanhai.gov.cn/fsnhslj/attachment/0/596/596847/7110166.pdf" }
      ],
      "detail_checked": true
    }
  ]
}
```

- `rent_snippets`：从正文里摘出的租金相关句子，便于快速读取价格信息。
- `attachments`：正文附件（租金标准 / 指导价目表通常是 PDF 表格，需要时可直接下载或 OCR）。
- `detail_checked`：正文详情是否已抓取过（用于增量回填，避免重复请求）。

> 下游 AI（如 souse 项目）可直接读取 `data/nanhai.json`，用 `is_rent` / `tags` / `rent_snippets` 做租金趋势与政策分析。

### 手动运行

```bash
python src/fetch_nanhai.py             # 栏目 + 搜索 + 补正文详情
python src/fetch_nanhai.py --no-detail # 只抓列表，速度更快
python src/fetch_nanhai.py --dry-run   # 只打印统计
```

### 部署说明（重要）

`www.nanhai.gov.cn` 只对境内网络可访问，GitHub Actions 的海外 runner 会返回
`Network is unreachable`（栏目抓不到，但 `search.gd.gov.cn` 搜索接口可用）。
因此分两条腿跑：

| 执行环境 | 频率 | 覆盖范围 |
|----------|------|----------|
| GitHub Actions（`update-nanhai.yml`）| 每小时 | 搜索接口（房租/租金政策、历年指导价文档）|
| 境内服务器 cron（推荐）| 每小时 | 栏目新闻 + 搜索接口，完整数据 |

境内服务器的 cron 示例（`/root/nanhai/nanhai-cron.sh`）：

```bash
35 * * * * /root/nanhai/nanhai-cron.sh
```

脚本内容：`git pull --rebase` → `python3 src/fetch_nanhai.py` → 复制到 `docs/data/` →
有变化才 commit & push（数据无变化时保留原 `updated`，不产生空提交）。
遇到网络抖动会自动重试。

## 🔧 Customization

### Add New News Sources

Edit `src/sources.json`:

```json
{
  "id": "your-source",
  "name": "Your Source Name",
  "country": "XX",
  "language": "en",
  "category": "general",
  "rss": "https://example.com/rss"
}
```

### Change Update Frequency

Edit `.github/workflows/update-news.yml`:

```yaml
on:
  schedule:
    # Change from */30 to your preferred interval
    - cron: '*/30 * * * *'  # Every 30 minutes
```

### Customize Styling

Edit `docs/css/style.css` to change colors, fonts, and layout.

## 📊 How It Works

```
┌─────────────────────────────────────────┐
│         GitHub Actions (Every 30m)      │
│  ┌───────────────────────────────────┐  │
│  │  1. Checkout code                 │  │
│  │  2. Install Python dependencies   │  │
│  │  3. Run fetch_news.py             │  │
│  │  4. Commit & push news.json       │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│            GitHub Pages                 │
│  ┌───────────────────────────────────┐  │
│  │  index.html loads news.json       │  │
│  │  JavaScript renders news cards    │  │
│  │  Auto-refresh every 5 minutes     │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## 🛠️ Local Development

### Test News Fetching Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the fetcher
python src/fetch_news.py

# Check output
cat data/news.json
```

### Preview Locally

```bash
# Simple HTTP server
cd docs
python -m http.server 8000

# Visit http://localhost:8000
```

## 📝 License

MIT License - feel free to use and modify!

## 🙏 Acknowledgments

- News data from various RSS feeds
- Inspired by [24inf.cn](http://24inf.cn/)
- Built with ❤️ using GitHub Pages

## 📬 Contact

- **GitHub**: [@fuoweineng](https://github.com/fuoweineng)
- **Issues**: [Report bugs or request features](https://github.com/fuoweineng/global-news-24h/issues)

---

**Enjoy staying informed with global news!** 🌍📰
