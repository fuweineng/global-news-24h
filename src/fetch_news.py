#!/usr/bin/env python3
"""
Global News Fetcher with Translation
从 RSS 源抓取新闻，翻译并生成 JSON 数据
"""

import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import time
import re
import urllib.request
import urllib.parse

# 翻译 API (使用 MyMemory 免费 API)
TRANSLATE_API = "https://api.mymemory.translated.net/get"

def translate_text(text: str, source_lang: str = "en", target_lang: str = "zh") -> str:
    """翻译文本 (使用 MyMemory 免费 API)"""
    if not text or len(text.strip()) == 0:
        return text
    
    # 如果已经是中文，不需要翻译
    if contains_chinese(text) and target_lang == "zh":
        return text
    
    try:
        # 限制文本长度 (API 限制 500 字符)
        text = text[:500]
        
        # 构建请求
        params = urllib.parse.urlencode({
            'q': text,
            'langpair': f"{source_lang}|{target_lang}"
        })
        
        url = f"{TRANSLATE_API}?{params}"
        
        # 发送请求
        req = urllib.request.Request(url, headers={'User-Agent': 'GlobalNewsFetcher/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if 'responseData' in data and 'translatedText' in data['responseData']:
                translated = data['responseData']['translatedText']
                # 清理翻译结果
                translated = re.sub(r'\s+', ' ', translated).strip()
                return translated
    except Exception as e:
        print(f"⚠️  Translation error: {e}")
    
    # 翻译失败时返回原文
    return text

def contains_chinese(text: str) -> bool:
    """检查文本是否包含中文"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def parse_rss_feed(url: str, source_name: str, source_lang: str = "en") -> list:
    """解析 RSS 源"""
    try:
        feed = feedparser.parse(url)
        articles = []
        
        for entry in feed.entries[:15]:  # 每个源取 15 条
            # 解析时间
            published = ''
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    published = dt.isoformat()
                except:
                    published = entry.get('published', '')
            
            # 清理 HTML 标签
            title = re.sub(r'<[^>]+>', '', entry.title).strip()
            summary = re.sub(r'<[^>]+>', '', entry.get('summary', entry.get('description', ''))).strip()[:300]
            
            article = {
                'id': hashlib.md5(entry.link.encode()).hexdigest()[:12],
                'title': title,
                'link': entry.link,
                'published': published,
                'source': source_name,
                'summary': summary,
                'original_lang': source_lang
            }
            articles.append(article)
        
        return articles
    except Exception as e:
        print(f"❌ Error fetching {source_name}: {e}")
        return []

def translate_articles(articles: list, target_lang: str = "zh") -> list:
    """批量翻译新闻"""
    print(f"🌐 Translating {len(articles)} articles to {target_lang}...")
    
    translated_count = 0
    for i, article in enumerate(articles, 1):
        # 跳过已经是中文的文章
        if article.get('original_lang') == 'zh' or contains_chinese(article['title']):
            article['title_zh'] = article['title']
            article['summary_zh'] = article['summary']
            continue
        
        # 翻译标题和摘要
        print(f"  [{i}/{len(articles)}] Translating: {article['title'][:50]}...")
        
        article['title_zh'] = translate_text(article['title'], 'en', target_lang)
        time.sleep(0.3)  # 避免 API 限流
        
        if article['summary']:
            article['summary_zh'] = translate_text(article['summary'], 'en', target_lang)
            time.sleep(0.3)
        else:
            article['summary_zh'] = ''
        
        translated_count += 1
    
    print(f"✅ Translated {translated_count} articles")
    return articles

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
        articles = parse_rss_feed(source['rss'], source['name'], source.get('language', 'en'))
        
        # 添加分类信息
        for article in articles:
            article['categories'] = source.get('categories', ['general'])
            article['category'] = source.get('categories', ['general'])[0]  # 主分类
            article['country'] = source.get('country', 'US')
            article['language'] = source.get('language', 'en')
        
        all_articles.extend(articles)
        time.sleep(0.5)  # 避免请求过快
    
    print("=" * 50)
    
    # 去重
    unique_articles = deduplicate_articles(all_articles)
    print(f"📰 Total articles: {len(all_articles)}")
    print(f"✨ Unique articles: {len(unique_articles)}")
    
    # 翻译文章 (英文→中文)
    unique_articles = translate_articles(unique_articles, 'zh')
    
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
        'category_groups': config.get('categoryGroups', {}),
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
