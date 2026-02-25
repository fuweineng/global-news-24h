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
import time

def parse_rss_feed(url: str, source_name: str) -> list:
    """解析 RSS 源"""
    try:
        feed = feedparser.parse(url)
        articles = []
        
        for entry in feed.entries[:20]:  # 每个源取 20 条
            # 解析时间
            published = ''
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    published = dt.isoformat()
                except:
                    published = entry.get('published', '')
            
            article = {
                'id': hashlib.md5(entry.link.encode()).hexdigest()[:12],
                'title': entry.title,
                'link': entry.link,
                'published': published,
                'source': source_name,
                'summary': entry.get('summary', entry.get('description', ''))[:300]
            }
            articles.append(article)
        
        return articles
    except Exception as e:
        print(f"❌ Error fetching {source_name}: {e}")
        return []

def deduplicate_articles(articles: list) -> list:
    """去重 (基于 ID)"""
    seen = set()
    unique = []
    
    for article in articles:
        if article['id'] not in seen:
            seen.add(article['id'])
            unique.append(article)
    
    return unique

def main():
    print("🌍 Global News Fetcher started")
    print("=" * 50)
    
    # 加载配置
    sources_file = Path('src/sources.json')
    if not sources_file.exists():
        print(f"❌ Config file not found: {sources_file}")
        return
    
    with open(sources_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    all_articles = []
    
    # 抓取所有源
    for i, source in enumerate(config['sources'], 1):
        print(f"[{i}/{len(config['sources'])}] Fetching {source['name']}...")
        articles = parse_rss_feed(source['rss'], source['name'])
        
        # 添加分类信息
        for article in articles:
            article['category'] = source['category']
            article['country'] = source['country']
            article['language'] = source['language']
        
        all_articles.extend(articles)
        time.sleep(0.5)  # 避免请求过快
    
    print("=" * 50)
    
    # 去重
    unique_articles = deduplicate_articles(all_articles)
    print(f"📰 Total articles: {len(all_articles)}")
    print(f"✨ Unique articles: {len(unique_articles)}")
    
    # 按时间排序
    unique_articles.sort(
        key=lambda x: x.get('published', ''),
        reverse=True
    )
    
    # 生成输出
    output = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'total': len(unique_articles),
        'sources_count': len(config['sources']),
        'articles': unique_articles[:100]  # 只保留最新 100 条
    }
    
    # 保存到 data/news.json
    output_file = Path('data/news.json')
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved to {output_file}")
    print(f"🕐 Updated at: {output['updated']}")

if __name__ == '__main__':
    main()
