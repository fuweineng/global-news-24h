#!/usr/bin/env python3
"""全球新闻抓取 - 优先路透社 + 客观一句话摘要"""

import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import time
import re
import os
import urllib.request

DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

def get_api_key():
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

def is_english(text):
    if not text: return False
    return sum(1 for c in text if c.isascii() and c.isalpha()) / max(len(text), 1) > 0.8

def summarize_batch(articles, api_key):
    """生成客观一句话摘要"""
    if not api_key or not articles:
        for a in articles: a['one_line'] = a['title']
        return articles
    
    print(f"🤖 生成摘要 {len(articles)} 篇...")
    for i in range(0, len(articles), 5):
        batch = articles[i:i+5]
        input_text = "\n".join([f"{j+1}. {a['title']}" for j, a in enumerate(batch)])
        
        prompt = f"""你是客观新闻编辑。将以下新闻改写成一句话客观摘要。
要求：
- 每篇一行，保持顺序
- 去掉主观形容词，只陈述事实
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
            for a in batch: a['one_line'] = a['title']
        time.sleep(0.3)
    print("✅ 摘要完成")
    return articles

def fetch_news():
    sources_file = Path('src/sources.json')
    if not sources_file.exists():
        print("❌ sources.json not found")
        return []
    
    with open(sources_file, 'r') as f:
        sources = json.load(f)['sources']
    
    # 按优先级排序：路透社优先
    sources.sort(key=lambda s: s.get('priority', 99))
    
    articles = []
    seen_titles = set()
    print(f"📰 抓取 {len(sources)} 个源（路透社优先）...")
    
    for source in sources:
        try:
            feed = feedparser.parse(source['rss'])
            # 路透社抓取 15 篇，其他 8 篇
            limit = 15 if source.get('priority') == 1 else 8
            for entry in feed.entries[:limit]:
                # 去重
                if entry.title in seen_titles: continue
                seen_titles.add(entry.title)
                
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
                    'priority': source.get('priority', 2)
                }
                articles.append(article)
        except Exception as e:
            print(f"⚠️ {source['name']} 失败：{e}")
        time.sleep(0.2)
    
    # 按优先级和时间排序
    articles.sort(key=lambda a: (a.get('priority', 2), a['published']), reverse=False)
    print(f"✅ 抓取 {len(articles)} 篇（去重后）")
    return articles

def main():
    api_key = get_api_key()
    articles = fetch_news()
    if not articles: return
    
    articles = summarize_batch(articles, api_key)
    
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
