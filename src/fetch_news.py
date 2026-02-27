#!/usr/bin/env python3
"""
Global News Fetcher with Alibaba Cloud Bailian (Qwen) Translation
从 RSS 源抓取新闻，使用阿里云百炼 Qwen 模型翻译并生成 JSON 数据
"""

import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import time
import re
import os
from typing import List, Dict, Optional

# 阿里云百炼 API (Qwen)
DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

# 翻译配置
USE_TRANSLATION = True
BATCH_TRANSLATE = True
MAX_BATCH_SIZE = 10
CACHE_TRANSLATION = True

def get_api_key() -> str:
    """获取阿里云 API Key"""
    # 1. 从环境变量 (GitHub Actions)
    if os.environ.get('DASHSCOPE_API_KEY'):
        return os.environ.get('DASHSCOPE_API_KEY')
    
    # 2. 从 OpenClaw auth-profiles.json
    auth_file = Path.home() / '.openclaw' / 'agents' / 'main' / 'agent' / 'auth-profiles.json'
    if auth_file.exists():
        try:
            with open(auth_file, 'r') as f:
                auth = json.load(f)
                if 'dashscope' in auth and auth['dashscope'].get('apiKey'):
                    return auth['dashscope']['apiKey']
        except:
            pass
    
    return ""

def contains_chinese(text: str) -> bool:
    """检查是否包含中文"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def is_mostly_english(text: str) -> bool:
    """检查是否主要是英文"""
    if not text:
        return False
    letters = sum(1 for c in text if c.isalpha())
    if letters == 0:
        return False
    english = sum(1 for c in text if c.isascii() and c.isalpha())
    return english / letters > 0.8

def translate_text_batch(texts: List[str], api_key: str) -> List[str]:
    """批量翻译文本"""
    if not texts or not api_key:
        return [''] * len(texts)
    
    # 构建批量翻译请求
    batch_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(texts[:MAX_BATCH_SIZE]) if t and is_mostly_english(t)])
    
    if not batch_text:
        return [''] * len(texts)
    
    prompt = f"""Translate the following English news titles to Chinese. Keep proper nouns (names, companies) in English. Return ONLY the translations, one per line, in the same order:

{batch_text}"""

    try:
        req = urllib.request.Request(
            DASHSCOPE_API_URL,
            data=json.dumps({
                "model": "qwen-turbo",
                "input": {"messages": [{"role": "user", "content": prompt}]},
                "parameters": {"temperature": 0.3}
            }).encode(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            translated = result['output']['choices'][0]['message']['content'].strip()
            
            # 解析翻译结果
            translations = []
            for line in translated.split('\n'):
                line = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                if line:
                    translations.append(line)
            
            return translations
    except Exception as e:
        print(f"⚠️ 翻译失败：{e}")
        return [''] * len(texts)

def translate_articles(articles: List[Dict], api_key: str) -> List[Dict]:
    """翻译文章标题和摘要"""
    if not api_key:
        print("⚠️ 未配置 API Key，跳过翻译")
        for article in articles:
            article['title_zh'] = article['title']
            article['summary_zh'] = article['summary']
        return articles
    
    print(f"🔄 开始翻译 {len(articles)} 篇文章...")
    translated_count = 0
    
    # 批量翻译标题
    for i in range(0, len(articles), MAX_BATCH_SIZE):
        batch = articles[i:i+MAX_BATCH_SIZE]
        titles = [a['title'] for a in batch if a['title'] and is_mostly_english(a['title']) and not contains_chinese(a['title'])]
        
        if titles:
            translations = translate_text_batch(titles, api_key)
            for j, article in enumerate(batch):
                if article['title'] in titles and is_mostly_english(article['title']) and not contains_chinese(article['title']):
                    idx = titles.index(article['title'])
                    article['title_zh'] = translations[idx] if idx < len(translations) and translations[idx] else article['title']
                else:
                    article['title_zh'] = article['title']
        
        time.sleep(0.5)  # 避免 API 限流
    
    # 翻译摘要（简化版，只翻译前 50 篇）
    for article in articles[:50]:
        if article.get('summary') and is_mostly_english(article['summary']) and not contains_chinese(article['summary']):
            try:
                summary_trans = translate_text_batch([article['summary'][:500]], api_key)
                article['summary_zh'] = summary_trans[0] if summary_trans and summary_trans[0] else article['summary']
            except:
                article['summary_zh'] = article['summary']
        else:
            article['summary_zh'] = article['summary']
    
    print(f"✅ 翻译完成")
    return articles

def fetch_news() -> List[Dict]:
    """抓取新闻"""
    sources_file = Path('src/sources.json')
    if not sources_file.exists():
        print("❌ sources.json not found")
        return []
    
    with open(sources_file, 'r') as f:
        sources = json.load(f)['sources']
    
    articles = []
    print(f"📰 开始抓取 {len(sources)} 个新闻源...")
    
    for source in sources:
        try:
            feed = feedparser.parse(source['rss'])
            for entry in feed.entries[:10]:  # 每个源最多 10 篇
                article = {
                    'id': hashlib.md5(f"{source['id']}-{entry.title}".encode()).hexdigest()[:12],
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.get('published', datetime.now(timezone.utc).isoformat()),
                    'source': source['name'],
                    'summary': entry.get('summary', '')[:200],
                    'original_lang': source.get('language', 'en'),
                    'categories': source.get('categories', []),
                    'category': source['categories'][0] if source.get('categories') else 'world',
                    'country': source.get('country', 'US'),
                    'language': source.get('language', 'en')
                }
                articles.append(article)
        except Exception as e:
            print(f"⚠️ {source['name']} 抓取失败：{e}")
        
        time.sleep(0.3)
    
    print(f"✅ 抓取完成：{len(articles)} 篇文章")
    return articles

def main():
    """主函数"""
    api_key = get_api_key()
    
    # 抓取新闻
    articles = fetch_news()
    if not articles:
        return
    
    # 翻译
    articles = translate_articles(articles, api_key)
    
    # 生成数据
    data = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'total': len(articles),
        'sources_count': len(set(a['source'] for a in articles)),
        'articles': articles
    }
    
    # 保存
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    
    with open(data_dir / 'news.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 保存到 data/news.json")

if __name__ == '__main__':
    main()
