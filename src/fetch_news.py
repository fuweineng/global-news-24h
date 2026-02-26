#!/usr/bin/env python3
"""
Global News Fetcher with Local Translation (Ollama)
从 RSS 源抓取新闻，使用本地 Ollama 翻译并生成 JSON 数据
"""

import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import time
import re
import urllib.request
import urllib.error

# 本地 Ollama API
OLLAMA_API = "http://localhost:11434/api/generate"

def translate_text(text: str, source_lang: str = "en", target_lang: str = "zh") -> str:
    """使用本地 Ollama 翻译文本"""
    if not text or len(text.strip()) == 0:
        return text
    
    # 如果已经是中文，不需要翻译
    if contains_chinese(text) and target_lang == "zh":
        return text
    
    # 只翻译纯英文内容
    if not is_mostly_english(text):
        return text
    
    try:
        # 限制文本长度
        text = text[:400]
        
        # 构建提示词
        prompt = f"Translate the following text from {source_lang} to {target_lang}. Only output the translation, nothing else:\n\n{text}"
        
        # 构建请求
        data = json.dumps({
            "model": "qwen2.5:7b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 512
            }
        }).encode('utf-8')
        
        req = urllib.request.Request(
            OLLAMA_API,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if 'response' in result:
                translated = result['response'].strip()
                # 清理翻译结果
                translated = re.sub(r'\s+', ' ', translated).strip()
                if translated and translated != text:
                    return translated
    
    except Exception as e:
        print(f"⚠️  Translation error: {e}")
    
    # 翻译失败时返回原文
    return text

def contains_chinese(text: str) -> bool:
    """检查文本是否包含中文"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def is_mostly_english(text: str) -> bool:
    """检查文本是否主要是英文"""
    if not text:
        return False
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    ratio = english_chars / len(text) if len(text) > 0 else 0
    return ratio > 0.8

def parse_rss_feed(url: str, source_name: str, source_lang: str = "en") -> list:
    """解析 RSS 源"""
    try:
        feed = feedparser.parse(url)
        articles = []
        
        for entry in feed.entries[:15]:
            published = ''
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    published = dt.isoformat()
                except:
                    published = entry.get('published', '')
            
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
    failed_count = 0
    
    for i, article in enumerate(articles, 1):
        # 跳过已经是中文的文章
        if article.get('original_lang') == 'zh' or contains_chinese(article['title']):
            article['title_zh'] = article['title']
            article['summary_zh'] = article['summary']
            continue
        
        print(f"  [{i}/{len(articles)}] Translating: {article['title'][:50]}...")
        
        article['title_zh'] = translate_text(article['title'], 'en', target_lang)
        time.sleep(0.1)  # Ollama 本地调用，短暂延迟即可
        
        if article['summary']:
            article['summary_zh'] = translate_text(article['summary'], 'en', target_lang)
            time.sleep(0.1)
        else:
            article['summary_zh'] = ''
        
        # 检查翻译是否成功
        if article['title_zh'] != article['title']:
            translated_count += 1
        else:
            failed_count += 1
    
    print(f"✅ Translated {translated_count} articles, {failed_count} unchanged")
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
    print("🌍 Global News Fetcher started (with Ollama Translation)")
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
            article['category'] = source.get('categories', ['general'])[0]
            article['country'] = source.get('country', 'US')
            article['language'] = source.get('language', 'en')
        
        all_articles.extend(articles)
        time.sleep(0.3)
    
    print("=" * 50)
    
    # 去重
    unique_articles = deduplicate_articles(all_articles)
    print(f"📰 Total articles: {len(all_articles)}")
    print(f"✨ Unique articles: {len(unique_articles)}")
    
    # 翻译文章 (英文→中文，使用本地 Ollama)
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
        'articles': unique_articles[:100]
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
