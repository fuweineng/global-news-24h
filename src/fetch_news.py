#!/usr/bin/env python3
"""全球新闻抓取 - DeepL 翻译"""

import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import time
import os
import urllib.request

DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

def get_api_key():
    api_key = os.environ.get('DEEPL_API_KEY', '')
    if api_key:
        print(f"✅ DeepL API Key 已配置")
        return api_key
    print("⚠️ 未找到 DEEPL_API_KEY 环境变量")
    return ""

def translate_batch(articles, api_key):
    """使用 DeepL 翻译新闻标题为中文"""
    if not api_key:
        print("⚠️ 无 API Key，跳过翻译")
        for a in articles:
            a['one_line'] = a['title']
        return articles
    
    print(f"🤖 DeepL 翻译 {len(articles)} 篇...")
    
    # 批量翻译，每次最多 50 篇
    for i in range(0, len(articles), 50):
        batch = articles[i:i+50]
        texts = [a['title'] for a in batch]
        
        try:
            req = urllib.request.Request(
                DEEPL_API_URL,
                data=urllib.parse.urlencode({
                    'auth_key': api_key,
                    'text': texts,
                    'target_lang': 'ZH',
                    'tag_handling': 'html',
                    'preserve_format': 'true'
                }).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
                translations = result.get('translations', [])
                for j, article in enumerate(batch):
                    if j < len(translations):
                        article['one_line'] = translations[j]['text']
                    else:
                        article['one_line'] = article['title']
        except Exception as e:
            print(f"⚠️ 翻译失败：{e}")
            for a in batch:
                a['one_line'] = a['title']
        time.sleep(0.5)
    
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
    api_key = get_api_key()
    articles = fetch_news()
    if not articles:
        return
    
    articles = translate_batch(articles, api_key)
    
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
