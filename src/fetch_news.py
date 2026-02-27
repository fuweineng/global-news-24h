#!/usr/bin/env python3
"""全球新闻抓取 - MyMemory 免费翻译 + 智能去重"""

import feedparser
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import time
import urllib.request
import urllib.parse
import re

MYMEMORY_API = "https://api.mymemory.translated.net/get"
CACHE_FILE = Path('data/news_cache.json')

def normalize_title(title):
    """标准化标题用于去重比较"""
    # 转小写，移除特殊字符，保留字母数字
    title = title.lower()
    title = re.sub(r'[^a-z0-9\s]', '', title)
    # 移除多余空格
    title = ' '.join(title.split())
    return title

def load_cache():
    """加载缓存的新闻 ID"""
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {'articles': [], 'updated': None}

def save_cache(data):
    """保存缓存"""
    CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def translate_batch(articles):
    """使用 MyMemory 翻译新闻标题为中文"""
    if not articles:
        return articles
    
    print(f"🤖 MyMemory 翻译 {len(articles)} 篇...")
    
    for i, article in enumerate(articles):
        try:
            url = f"{MYMEMORY_API}?q={urllib.parse.quote(article['title'])}&langpair=en|zh"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                translation = result.get('responseData', {}).get('translatedText', '')
                article['one_line'] = translation if translation else article['title']
        except Exception as e:
            print(f"⚠️ 翻译失败：{e}")
            article['one_line'] = article['title']
        time.sleep(0.15)
        
        if (i + 1) % 20 == 0:
            print(f"  已翻译 {i+1}/{len(articles)} 篇")
    
    print("✅ 翻译完成")
    return articles

def fetch_news():
    sources_file = Path('src/sources.json')
    if not sources_file.exists():
        print("❌ sources.json not found")
        return []
    
    with open(sources_file, 'r') as f:
        sources = json.load(f)['sources']
    
    # 按优先级排序（数字越小优先级越高）
    sources.sort(key=lambda s: s.get('priority', 99))
    
    # 加载缓存，用于去重
    cache = load_cache()
    cached_ids = {a['id'] for a in cache.get('articles', [])}
    
    articles = []
    seen_normalized = set()  # 标准化后的标题用于去重
    print(f"📰 抓取 {len(sources)} 个源...")
    
    for source in sources:
        try:
            feed = feedparser.parse(source['rss'])
            for entry in feed.entries[:10]:  # 每个源抓取 10 篇
                # 生成唯一 ID
                article_id = hashlib.md5(f"{source['id']}-{entry.title}".encode()).hexdigest()[:12]
                
                # 跳过缓存中已有的文章
                if article_id in cached_ids:
                    continue
                
                # 标准化标题去重（处理不同来源的相同新闻）
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
                    'summary': entry.get('summary', '')[:200],
                    'category': source['categories'][0] if source.get('categories') else 'world',
                    'original_lang': source.get('language', 'en'),
                    'priority': source.get('priority', 2)
                }
                articles.append(article)
        except Exception as e:
            print(f"⚠️ {source['name']} 失败：{e}")
        time.sleep(0.2)
    
    # 按优先级和时间排序
    articles.sort(key=lambda a: (a.get('priority', 2), a['published']), reverse=False)
    
    # 更新缓存（保留最近 500 篇）
    cache['articles'] = articles[:500]
    cache['updated'] = datetime.now(timezone.utc).isoformat()
    save_cache(cache)
    
    print(f"✅ 抓取 {len(articles)} 篇（去重后，缓存 {len(cache['articles'])} 篇）")
    return articles

def main():
    articles = fetch_news()
    if not articles:
        print("ℹ️ 无新新闻，跳过更新")
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
