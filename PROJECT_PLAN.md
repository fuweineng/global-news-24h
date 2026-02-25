# 🌍 24Hr Global News - 国际新闻滚动网站

## 📋 项目概述

类似 24inf.cn，但信息源更国际化，支持多语言新闻聚合。

### 核心特性
- ✅ **24 小时滚动更新** - 每 30 分钟自动刷新
- ✅ **国际化信息源** - 覆盖全球主要媒体
- ✅ **GitHub Pages 部署** - 完全免费
- ✅ **静态网站** - 无需服务器
- ✅ **响应式设计** - 手机/平板/桌面自适应

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    GitHub Actions                        │
│  ┌───────────────────────────────────────────────────┐  │
│  │  fetch_news.py (每 30 分钟运行)                    │  │
│  │  - 抓取 RSS/Atom 源                                │  │
│  │  - 去重、排序、分类                                │  │
│  │  - 生成 news.json                                  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    GitHub Pages                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  index.html │  │  news.json  │  │  styles.css │     │
│  │  (前端展示)  │  │  (新闻数据)  │  │  (样式)     │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│  ┌─────────────┐  ┌─────────────┐                       │
│  │  app.js     │  │  sources.json│                      │
│  │  (交互逻辑)  │  │  (信息源配置)│                      │
│  └─────────────┘  └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 项目结构

```
global-news-24h/
├── .github/
│   └── workflows/
│       └── update-news.yml      # GitHub Actions 定时任务
├── src/
│   ├── fetch_news.py            # 新闻抓取脚本
│   └── sources.json             # 信息源配置
├── docs/
│   ├── index.html               # 主页面
│   ├── css/
│   │   └── style.css            # 样式文件
│   └── js/
│       └── app.js               # 前端逻辑
├── data/
│   └── news.json                # 生成的新闻数据 (自动)
├── requirements.txt             # Python 依赖
└── README.md                    # 项目说明
```

---

## 🌐 信息源配置 (sources.json)

```json
{
  "sources": [
    {
      "id": "reuters",
      "name": "Reuters",
      "country": "US",
      "language": "en",
      "category": "general",
      "rss": "https://www.reutersagency.com/feed/"
    },
    {
      "id": "bbc",
      "name": "BBC News",
      "country": "GB",
      "language": "en",
      "category": "general",
      "rss": "http://feeds.bbci.co.uk/news/rss.xml"
    },
    {
      "id": "cnn",
      "name": "CNN",
      "country": "US",
      "language": "en",
      "category": "general",
      "rss": "http://rss.cnn.com/rss/edition.rss"
    },
    {
      "id": "nhk",
      "name": "NHK World",
      "country": "JP",
      "language": "en",
      "category": "general",
      "rss": "https://www3.nhk.or.jp/nhkworld/en/news/feeds/rss/index.xml"
    },
    {
      "id": "dw",
      "name": "Deutsche Welle",
      "country": "DE",
      "language": "en",
      "category": "general",
      "rss": "https://rss.dw.com/xml/rss-en-all"
    },
    {
      "id": "france24",
      "name": "France 24",
      "country": "FR",
      "language": "en",
      "category": "general",
      "rss": "https://www.france24.com/en/rss"
    },
    {
      "id": "scmp",
      "name": "South China Morning Post",
      "country": "HK",
      "language": "en",
      "category": "asia",
      "rss": "https://www.scmp.com/rss/318224/feed"
    },
    {
      "id": "economist",
      "name": "The Economist",
      "country": "GB",
      "language": "en",
      "category": "business",
      "rss": "https://www.economist.com/the-world-this-week/rss.xml"
    }
  ]
}
```

---

## 🐍 新闻抓取脚本 (fetch_news.py)

```python
#!/usr/bin/env python3
"""
Global News Fetcher
从 RSS 源抓取新闻，生成 JSON 数据
"""

import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib

def parse_rss_feed(url: str) -> list:
    """解析 RSS 源"""
    feed = feedparser.parse(url)
    articles = []
    
    for entry in feed.entries[:20]:  # 每个源取 20 条
        article = {
            'title': entry.title,
            'link': entry.link,
            'published': entry.get('published', ''),
            'source': feed.feed.get('title', 'Unknown'),
            'summary': entry.get('summary', '')[:200]  # 限制摘要长度
        }
        articles.append(article)
    
    return articles

def deduplicate_articles(articles: list) -> list:
    """去重 (基于标题哈希)"""
    seen = set()
    unique = []
    
    for article in articles:
        title_hash = hashlib.md5(article['title'].encode()).hexdigest()
        if title_hash not in seen:
            seen.add(title_hash)
            unique.append(article)
    
    return unique

def main():
    # 加载配置
    sources_file = Path('src/sources.json')
    with open(sources_file, 'r') as f:
        config = json.load(f)
    
    all_articles = []
    
    # 抓取所有源
    for source in config['sources']:
        print(f"Fetching {source['name']}...")
        articles = parse_rss_feed(source['rss'])
        
        # 添加分类信息
        for article in articles:
            article['category'] = source['category']
            article['country'] = source['country']
            article['language'] = source['language']
        
        all_articles.extend(articles)
    
    # 去重
    unique_articles = deduplicate_articles(all_articles)
    
    # 按时间排序
    unique_articles.sort(
        key=lambda x: x.get('published', ''),
        reverse=True
    )
    
    # 生成输出
    output = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'total': len(unique_articles),
        'articles': unique_articles[:100]  # 只保留最新 100 条
    }
    
    # 保存到 data/news.json
    output_file = Path('data/news.json')
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved {len(unique_articles)} articles to {output_file}")

if __name__ == '__main__':
    main()
```

---

## ⚙️ GitHub Actions 配置 (.github/workflows/update-news.yml)

```yaml
name: Update News

on:
  schedule:
    # 每 30 分钟运行一次 (UTC 时间)
    - cron: '*/30 * * * *'
  workflow_dispatch:  # 允许手动触发

jobs:
  fetch-news:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Fetch news
        run: python src/fetch_news.py
      
      - name: Commit and push changes
        run: |
          git config --local user.email "github-actions[bot]@users.noreply.github.com"
          git config --local user.name "github-actions[bot]"
          git add data/news.json
          git diff --staged --quiet || git commit -m "Update news: $(date -u)"
          git push
```

---

## 🎨 前端页面 (docs/index.html)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>24Hr Global News</title>
    <link rel="stylesheet" href="css/style.css">
</head>
<body>
    <header>
        <h1>🌍 24Hr Global News</h1>
        <p>Real-time international news feed</p>
        <div id="last-updated"></div>
    </header>
    
    <main>
        <div class="filters">
            <button class="filter-btn active" data-category="all">All</button>
            <button class="filter-btn" data-category="general">General</button>
            <button class="filter-btn" data-category="business">Business</button>
            <button class="filter-btn" data-category="asia">Asia</button>
        </div>
        
        <div id="news-container" class="news-grid">
            <!-- News items will be loaded here -->
        </div>
    </main>
    
    <footer>
        <p>Updated every 30 minutes | Data from global RSS feeds</p>
    </footer>
    
    <script src="js/app.js"></script>
</body>
</html>
```

---

## 📦 依赖文件 (requirements.txt)

```
feedparser==6.0.10
requests==2.31.0
```

---

## 🚀 部署步骤

### 1. 创建 GitHub 仓库
```bash
# 本地初始化
mkdir global-news-24h
cd global-news-24h
git init

# 创建文件后
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/global-news-24h.git
git push -u origin main
```

### 2. 启用 GitHub Pages
1. 进入仓库 Settings → Pages
2. Source: **GitHub Actions**
3. 等待首次部署

### 3. 配置 Actions 权限
1. Settings → Actions → General
2. Workflow permissions: **Read and write permissions**
3. 允许 Actions 创建 PRs

### 4. 验证部署
- 访问：`https://YOUR_USERNAME.github.io/global-news-24h/`
- 检查 data/news.json 是否自动生成

---

## 🎯 优化建议

### 性能优化
- ✅ 只保留最新 100 条新闻
- ✅ 前端懒加载
- ✅ 使用 CDN 加速

### 内容优化
- ✅ 增加更多语言源 (中文、日文、西班牙文等)
- ✅ 添加 AI 摘要 (用你的 Lite 套餐)
- ✅ 分类标签系统

### 功能扩展
- 🔄 添加搜索功能
- 🔄 支持 RSS 订阅
- 🔄 添加新闻热度排序
- 🔄 支持多语言界面

---

## 💰 成本分析

| 项目 | 费用 |
|------|------|
| GitHub Pages | 免费 |
| GitHub Actions | 免费 (2000 分钟/月) |
| 域名 (可选) | ~$10/年 |
| RSS 源 | 免费 |
| **总计** | **$0/月** |

---

## 📊 与 24inf.cn 对比

| 特性 | 24inf.cn | 本项目 |
|------|----------|--------|
| 信息源 | 中文媒体为主 | 全球媒体 |
| 更新频率 | 实时 | 30 分钟 |
| 部署方式 | 服务器 | GitHub Pages |
| 成本 | 服务器费用 | 免费 |
| 可定制性 | 低 | 高 |

---

## 🎬 下一步

1. **创建仓库** - 我帮你生成完整代码
2. **配置信息源** - 添加你喜欢的媒体
3. **定制前端** - 调整样式和布局
4. **设置域名** (可选) - 绑定自定义域名

**要我帮你生成完整的项目文件吗？** 🚀
