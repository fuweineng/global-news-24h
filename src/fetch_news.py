#!/usr/bin/env python3
"""全球新闻抓取 - LibreTranslate 免费翻译"""

import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import time
import os
import urllib.request
import urllib.parse

# LibreTranslate 公共服务器（免费，无需 API Key）
LIBRETRANSLATE_URL = "https://libretranslate.com/translate"

def translate_batch(articles):
    """使用 LibreTranslate 翻译新闻标题为中文"""
    if not articles:
        return articles
    
    print(f"🤖 LibreTranslate 翻译 {len(articles)} 篇...")
    
    # 批量翻译
    for i in range(0, len(articles), 10):
        batch = articles[i:i+10]
        
        for article in batch:
            try:
                req = urllib.request.Request(
                    LIBRETRANSLATE_URL,
                    data=urllib.parse.urlencode({
                        'q': article['title'],
                        'source': 'en',
                        'target': 'zh',
                        'format': 'text'
                    }).encode(),
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode())
                    article['one_line'] = result.get('translatedText', article['title'])
            except Exception as e:
                print(f"⚠️ 翻译失败：{e}")
                article['one_line'] = article['title']
            time.sleep(0.3)
    
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
    
    articles = []
    seen_titles = set()
    print(f"📰 抓取 {len(sources)} 个源...")
    
    for source in sources:
        try:
            feed = feedparser.parse(source['rss'])
            for entry in feed.entries[:8]:
                title_key = entry.title[:50]
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)
                
                try:
                    dt = datetime.fromisoformat(entry.get('published', '').replace('Z', '+00:00'))
                    time_str = dt.strftime('%H:%M')
                except:
                    time_str = '--:--'
                
                article = {
                    'id': hashlib.md5(f"{source['id']}-{entry.title}".encode()).hexdigest()[:12],
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.get('published', datetime.now(timezone.utc).isoformat()),
                    'time': time_str,
                    'source': source['name'],
                    'summary': entry.get('summary', '')[:200],
                    'category': source['categories'][0] if source.get('categories') else 'world',
                    'original_lang': source.get('language', 'en'),
                    'priority': source.get('priority', 2)
                }
                articles.append(article)
        except Exception as e:
            print(f"⚠️ {source['name']} 失败：{e}")
        time.sleep(0.3)
    
    articles.sort(key=lambda a: (a.get('priority', 2), a['published']), reverse=False)
    print(f"✅ 抓取 {len(articles)} 篇（去重后）")
    return articles

def main():
    articles = fetch_news()
    if not articles:
        return
    
    articles = translate_batch(articles)
    
    data = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'total': len(articles),
        'articles': articles
    }
    
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    with open(data_dir / 'news.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ 保存到 data/news.json")

if __name__ == '__main__':
    main()
