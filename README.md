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
│       └── update-news.yml      # Auto-update every 30 min
├── src/
│   ├── fetch_news.py            # News fetching script
│   └── sources.json             # RSS source configuration
├── docs/
│   ├── index.html               # Main page
│   ├── css/
│   │   └── style.css            # Styling
│   └── js/
│       └── app.js               # Frontend logic
├── data/
│   └── news.json                # Generated news data
├── requirements.txt             # Python dependencies
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
