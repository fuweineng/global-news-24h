#!/usr/bin/env python3
"""全球新闻抓取 - MyMemory 翻译 + 中立表达 + 智能去重"""

import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import time
import urllib.request
import urllib.parse
import re

MYMEMORY_API = "https://api.mymemory.translated.net/get"
CACHE_FILE = Path('data/news_cache.json')

# ── 标感词/头缀 过滤 ─────────────────────────────────
SENSATIONAL_PREFIXES = [
    r'^BREAKING\s*:?\s*', r'^BREAKING NEWS\s*:?\s*',
    r'^EXCLUSIVE\s*:?\s*', r'^URGENT\s*:?\s*',
    r'^JUST IN\s*:?\s*', r'^UPDATE\s*:?\s*',
    r'^FLASH\s*:?\s*', r'^DEVELOPING\s*:?\s*',
    r'^WATCH\s*:?\s*', r'^LIVE\s*:?\s*',
    r'^VIDEO\s*:?\s*',
]
SENSATIONAL_PATTERN = re.compile('|'.join(SENSATIONAL_PREFIXES), re.IGNORECASE)

def is_chinese(text):
    """检测字符串是否以中文为主"""
    if not text:
        return False
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return cjk > len(text) * 0.3

def normalize_title(title):
    """标准化标题用于去重比较"""
    title = title.lower()
    title = re.sub(r'[^a-z0-9\u4e00-\u9fff\s]', '', title)
    title = ' '.join(title.split())
    return title

def neutralize_title(title):
    """移除标感词/头缀，返回中立标题"""
    title = SENSATIONAL_PATTERN.sub('', title).strip()
    # 清理多余标点
    title = re.sub(r'\s{2,}', ' ', title)
    title = title.strip(' :;,!?-')
    return title

def translate_text(text, src_lang='en'):
    """调用 MyMemory 翻译单段文字"""
    if not text or len(text.strip()) < 3:
        return text
    try:
        url = f"{MYMEMORY_API}?q={urllib.parse.quote(text[:500])}&langpair={src_lang}|zh"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            translation = result.get('responseData', {}).get('translatedText', '')
            return translation if translation else text
    except Exception:
        return text

def translate_articles(articles):
    """翻译全部文章为中文 + 中立化"""
    if not articles:
        return articles

    print(f"🤖 翻译 {len(articles)} 篇...")
    for i, article in enumerate(articles):
        title = article.get('title', '')
        summary = article.get('summary', '')

        # 1. 中立化英文标题（去掉标感词）
        neutral_title = neutralize_title(title)

        # 2. 生成中文标题
        if is_chinese(neutral_title):
            zh_title = neutral_title
        else:
            zh_title = translate_text(neutral_title, article.get('original_lang', 'en'))
            time.sleep(0.15)

        # 3. 生成中文摘要
        if summary:
            zh_summary = translate_text(summary[:300], article.get('original_lang', 'en'))
            time.sleep(0.15)
        else:
            zh_summary = ''

        article['zh_title'] = zh_title
        article['zh_summary'] = zh_summary
        article['one_line'] = zh_title  # 向后兼容

        if (i + 1) % 15 == 0:
            print(f"  翻译进度 {i+1}/{len(articles)}")

    print("✅ 翻译完成")
    return articles

def fetch_news():
    sources_file = Path('src/sources.json')
    if not sources_file.exists():
        print("❌ sources.json not found")
        return []

    with open(sources_file, 'r') as f:
        sources = json.load(f)['sources']

    sources.sort(key=lambda s: s.get('priority', 99))

    cache = load_cache()
    cached_ids = {a['id'] for a in cache.get('articles', [])}

    articles = []
    seen_normalized = set()
    print(f"📰 抓取 {len(sources)} 个源...")

    for source in sources:
        try:
            feed = feedparser.parse(source['rss'])
            for entry in feed.entries[:10]:
                article_id = hashlib.md5(f"{source['id']}-{entry.title}".encode()).hexdigest()[:12]

                if article_id in cached_ids:
                    continue

                normalized = normalize_title(entry.title)
                if normalized in seen_normalized:
                    print(f"  ⚠️ 跳过重复：{entry.title[:40]}...")
                    continue
                seen_normalized.add(normalized)

                try:
                    dt = datetime.fromisoformat(entry.get('published', '').replace('Z', '+00:00'))
                    time_str = dt.strftime('%H:%M')
                except:
                    time_str = '--:--'

                article = {
                    'id': article_id,
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.get('published', datetime.now(timezone.utc).isoformat()),
                    'time': time_str,
                    'source': source['name'],
                    'summary': entry.get('summary', '')[:300],
                    'category': source['categories'][0] if source.get('categories') else 'world',
                    'original_lang': source.get('language', 'en'),
                    'priority': source.get('priority', 2),
                    'zh_title': '',
                    'zh_summary': '',
                    'one_line': ''
                }
                articles.append(article)
        except Exception as e:
            print(f"⚠️ {source['name']} 失败：{e}")
        time.sleep(0.2)

    articles.sort(key=lambda a: (a.get('priority', 2), a['published']))

    cache['articles'] = articles[:500]
    cache['updated'] = datetime.now(timezone.utc).isoformat()
    save_cache(cache)

    print(f"✅ 抓取 {len(articles)} 篇（缓存 {len(cache['articles'])} 篇）")
    return articles

def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {'articles': [], 'updated': None}

def save_cache(data):
    CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    articles = fetch_news()
    if not articles:
        print("ℹ️ 无新新闻")
        return

    articles = translate_articles(articles)

    # 重新输出全部缓存文章（包括历史文章）以获取中文标题
    cache = load_cache()
    all_cached = cache.get('articles', [])

    # 对新文章补充翻译，历史文章若有缺失则补译
    updated = []
    new_ids = {a['id'] for a in articles}
    for a in all_cached:
        if a['id'] in new_ids:
            # 用新翻译覆盖
            merged = {**a, **next(x for x in articles if x['id'] == a['id'])}
        else:
            merged = a
            # 对旧文章也补翻译
            if not merged.get('zh_title'):
                merged['zh_title'] = merged.get('one_line', '') or merged.get('title', '')
            if not merged.get('zh_summary'):
                merged['zh_summary'] = ''
            if not merged.get('one_line'):
                merged['one_line'] = merged['zh_title']
        updated.append(merged)

    data = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'total': len(updated),
        'articles': updated
    }

    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    with open(data_dir / 'news.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ 保存到 data/news.json ({len(updated)} 篇)")

if __name__ == '__main__':
    main()
