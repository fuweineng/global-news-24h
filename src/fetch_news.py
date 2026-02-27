#!/usr/bin/env python3
"""
Global News Fetcher - 客观一句话新闻
从 RSS 源抓取新闻，使用 Qwen 模型生成客观的一句话摘要
"""

import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import time
import re
import os
import urllib.request
from typing import List, Dict

DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

def get_api_key() -> str:
    """获取 API Key"""
    if os.environ.get('DASHSCOPE_API_KEY'):
        return os.environ.get('DASHSCOPE_API_KEY')
    auth_file = Path.home() / '.openclaw' / 'agents' / 'main' / 'agent' / 'auth-profiles.json'
    if auth_file.exists():
        try:
            with open(auth_file, 'r') as f:
                auth = json.load(f)
                if 'dashscope' in auth and auth['dashscope'].get('apiKey'):
                    return auth['dashscope']['apiKey']
        except: pass
    return ""

def contains_chinese(text: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def is_mostly_english(text: str) -> bool:
    if not text: return False
    letters = sum(1 for c in text if c.isalpha())
    if letters == 0: return False
    return sum(1 for c in text if c.isascii() and c.isalpha()) / letters > 0.8

def summarize_news_batch(articles: List[Dict], api_key: str) -> List[Dict]:
    """使用 Qwen 生成客观一句话摘要"""
    if not api_key or not articles:
        for a in articles:
            a['one_line'] = a['title']
        return articles
    
    print(f"🤖 生成一句话摘要 {len(articles)} 篇...")
    
    # 批量处理，每批 5 篇
    for i in range(0, len(articles), 5):
        batch = articles[i:i+5]
        input_text = "\n".join([f"{j+1}. {a['title']}" for j, a in enumerate(batch)])
        
        prompt = f"""你是客观新闻编辑。将以下新闻标题改写成客观的一句话新闻摘要。
要求：
- 每篇一行，保持原顺序
- 去掉主观形容词（如"shocking", "amazing"等）
- 只陈述事实，不加评价
- 中文输出，保留英文专有名词
- 每句 20-40 字

新闻：
{input_text}

摘要："""
        
        try:
            req = urllib.request.Request(
                DASHSCOPE_API_URL,
                data=json.dumps({
                    "model": "qwen-turbo",
                    "input": {"messages": [{"role": "user", "content": prompt}]},
                    "parameters": {"temperature": 0.1}
                }).encode(),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
                lines = result['output']['choices'][0]['message']['content'].strip().split('\n')
                
                for j, article in enumerate(batch):
                    if j < len(lines):
                        line = re.sub(r'^\d+[\.\)]\s*', '', lines[j]).strip()
                        article['one_line'] = line if line else article['title']
                    else:
                        article['one_line'] = article['title']
        except Exception as e:
            print(f"⚠️ 摘要失败：{e}")
            for a in batch:
                a['one_line'] = a['title']
        
        time.sleep(0.3)
    
    print("✅ 摘要完成")
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
    print(f"📰 抓取 {len(sources)} 个源...")
    
    for source in sources:
        try:
            feed = feedparser.parse(source['rss'])
            for entry in feed.entries[:10]:
                # 格式化时间：HH:MM
                pub_time = entry.get('published', '')
                try:
                    dt = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                    time_str = dt.strftime('%H:%M')
                except:
                    time_str = '--:--'
                
                article = {
                    'id': hashlib.md5(f"{source['id']}-{entry.title}".encode()).hexdigest()[:12],
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.get('published', datetime.now(timezone.utc).isoformat()),
                    'time': time_str,  # HH:MM 格式
                    'source': source['name'],
                    'summary': entry.get('summary', '')[:200],
                    'original_lang': source.get('language', 'en'),
                    'category': source['categories'][0] if source.get('categories') else 'world',
                    'country': source.get('country', 'US')
                }
                articles.append(article)
        except Exception as e:
            print(f"⚠️ {source['name']} 失败：{e}")
        time.sleep(0.2)
    
    print(f"✅ 抓取 {len(articles)} 篇")
    return articles

def main():
    api_key = get_api_key()
    articles = fetch_news()
    if not articles:
        return
    
    # 生成一句话摘要
    articles = summarize_news_batch(articles, api_key)
    
    data = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'total': len(articles),
        'sources_count': len(set(a['source'] for a in articles)),
        'articles': articles
    }
    
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    
    with open(data_dir / 'news.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 保存到 data/news.json")

if __name__ == '__main__':
    main()
