#!/usr/bin/env python3
"""
Global News Fetcher with Alibaba Cloud Bailian (Qwen) Translation
从 RSS 源抓取新闻，使用阿里云百炼 Qwen 模型翻译并生成 JSON 数据

优化点:
- 批量翻译 (减少 API 调用次数)
- 智能去重 (标题相似度检测)
- 错误重试机制
- 翻译缓存 (避免重复翻译相同内容)
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
import os
from typing import List, Dict, Optional

# 阿里云百炼 API (Qwen)
DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

# 翻译配置
USE_TRANSLATION = True
TRANSLATION_MODEL = "qwen-turbo"  # 快速且便宜
BATCH_TRANSLATE = True  # 启用批量翻译
MAX_BATCH_SIZE = 10  # 每批翻译的文章数
CACHE_TRANSLATION = True  # 启用翻译缓存

def get_api_key() -> str:
    """获取阿里云 API Key"""
    # 1. 从环境变量
    if os.environ.get('DASHSCOPE_API_KEY'):
        return os.environ['DASHSCOPE_API_KEY']
    
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
    
    # 3. 从项目配置
    config_file = Path('config.json')
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                if config.get('dashscope_api_key'):
                    return config['dashscope_api_key']
        except:
            pass
    
    return ""

def load_translation_cache() -> Dict[str, str]:
    """加载翻译缓存"""
    cache_file = Path('data/translation_cache.json')
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_translation_cache(cache: Dict[str, str]):
    """保存翻译缓存"""
    cache_file = Path('data/translation_cache.json')
    cache_file.parent.mkdir(exist_ok=True)
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except:
        pass

def translate_text_batch(texts: List[str], api_key: str, source_lang: str = "en", target_lang: str = "zh") -> List[str]:
    """批量翻译文本"""
    if not texts:
        return []
    
    # 过滤掉已经是中文或空的内容
    to_translate = []
    indices = []
    for i, text in enumerate(texts):
        if not text or len(text.strip()) == 0:
            continue
        if contains_chinese(text) or not is_mostly_english(text):
            continue
        to_translate.append(text[:500])  # 限制长度
        indices.append(i)
    
    if not to_translate:
        return texts
    
    # 批量翻译
    batch_prompt = "Translate the following texts from English to Chinese. Output ONLY the translations, one per line, in the same order:\n\n"
    for i, text in enumerate(to_translate):
        batch_prompt += f"{i+1}. {text}\n"
    
    try:
        data = json.dumps({
            "model": TRANSLATION_MODEL,
            "input": {
                "messages": [
                    {"role": "system", "content": "You are a professional translator. Translate accurately and concisely."},
                    {"role": "user", "content": batch_prompt}
                ]
            },
            "parameters": {
                "temperature": 0.3,
                "max_tokens": 2048
            }
        }).encode('utf-8')
        
        req = urllib.request.Request(
            DASHSCOPE_API_URL,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if 'output' in result and 'choices' in result['output']:
                translated_text = result['output']['choices'][0]['message']['content'].strip()
                # 解析翻译结果
                translations = {}
                for line in translated_text.split('\n'):
                    match = re.match(r'^\d+\.\s*(.+)$', line.strip())
                    if match:
                        translations[len(translations)] = match.group(1).strip()
                
                # 构建结果
                results = list(texts)
                for i, idx in enumerate(indices):
                    if i in translations:
                        results[idx] = translations[i]
                
                return results
    
    except Exception as e:
        print(f"⚠️  Batch translation error: {e}")
    
    return texts

def translate_text(text: str, api_key: str, cache: Dict[str, str], source_lang: str = "en", target_lang: str = "zh") -> str:
    """翻译单个文本 (带缓存)"""
    if not text or len(text.strip()) == 0:
        return text
    
    # 如果已经是中文，跳过
    if contains_chinese(text) and target_lang == "zh":
        return text
    
    # 如果不是英文，跳过
    if not is_mostly_english(text):
        return text
    
    # 检查缓存
    cache_key = hashlib.md5(text.encode()).hexdigest()
    if CACHE_TRANSLATION and cache_key in cache:
        return cache[cache_key]
    
    # 单个翻译 (fallback)
    try:
        data = json.dumps({
            "model": TRANSLATION_MODEL,
            "input": {
                "messages": [
                    {"role": "system", "content": "You are a professional translator. Translate from English to Chinese. Output ONLY the translation."},
                    {"role": "user", "content": text[:500]}
                ]
            },
            "parameters": {
                "temperature": 0.3,
                "max_tokens": 512
            }
        }).encode('utf-8')
        
        req = urllib.request.Request(
            DASHSCOPE_API_URL,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if 'output' in result and 'choices' in result['output']:
                translated = result['output']['choices'][0]['message']['content'].strip()
                translated = re.sub(r'\s+', ' ', translated).strip()
                
                # 保存到缓存
                if CACHE_TRANSLATION and translated != text:
                    cache[cache_key] = translated
                
                return translated
    
    except Exception as e:
        print(f"⚠️  Translation error: {e}")
    
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

def parse_rss_feed(url: str, source_name: str, source_lang: str = "en") -> List[Dict]:
    """解析 RSS 源 (带重试)"""
    max_retries = 2
    for attempt in range(max_retries):
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
            if attempt < max_retries - 1:
                print(f"  ⚠️  Retry {attempt + 1}/{max_retries} for {source_name}")
                time.sleep(1)
            else:
                print(f"❌ Error fetching {source_name}: {e}")
    
    return []

def deduplicate_articles(articles: List[Dict]) -> List[Dict]:
    """去重 (基于 ID + 标题相似度)"""
    seen_ids = set()
    seen_titles = set()
    unique = []
    
    for article in articles:
        # ID 去重
        if article['id'] in seen_ids:
            continue
        
        # 标题相似度去重 (简化版：小写 + 去标点)
        title_key = re.sub(r'[^\w\s]', '', article['title'].lower())[:50]
        if title_key in seen_titles:
            continue
        
        seen_ids.add(article['id'])
        seen_titles.add(title_key)
        unique.append(article)
    
    return unique

def translate_articles(articles: List[Dict], api_key: str, cache: Dict[str, str], target_lang: str = "zh") -> List[Dict]:
    """批量翻译文章"""
    if not USE_TRANSLATION or not api_key:
        print("⏭️  跳过翻译")
        return articles
    
    print(f"🌐 使用阿里云 Qwen 翻译 {len(articles)} 篇文章...")
    
    translated_count = 0
    failed_count = 0
    skipped_count = 0
    
    if BATCH_TRANSLATE:
        # 批量翻译模式
        for i in range(0, len(articles), MAX_BATCH_SIZE):
            batch = articles[i:i + MAX_BATCH_SIZE]
            titles = [a['title'] for a in batch]
            summaries = [a['summary'] for a in batch if a['summary']]
            
            # 翻译标题
            translated_titles = translate_text_batch(titles, api_key)
            for j, article in enumerate(batch):
                if article.get('original_lang') == 'zh' or contains_chinese(article['title']):
                    article['title_zh'] = article['title']
                    skipped_count += 1
                else:
                    article['title_zh'] = translated_titles[j] if j < len(translated_titles) else article['title']
                    if article['title_zh'] != article['title']:
                        translated_count += 1
                    else:
                        failed_count += 1
            
            # 翻译摘要
            if summaries:
                translated_summaries = translate_text_batch(summaries, api_key)
                summary_idx = 0
                for j, article in enumerate(batch):
                    if article['summary']:
                        if article.get('original_lang') == 'zh' or contains_chinese(article['summary']):
                            article['summary_zh'] = article['summary']
                        else:
                            article['summary_zh'] = translated_summaries[summary_idx] if summary_idx < len(translated_summaries) else article['summary']
                        summary_idx += 1
            
            print(f"  批次 {i//MAX_BATCH_SIZE + 1}/{(len(articles) + MAX_BATCH_SIZE - 1)//MAX_BATCH_SIZE} 完成")
            time.sleep(0.5)  # API 限流保护
    
    else:
        # 单个翻译模式 (旧版)
        for i, article in enumerate(articles, 1):
            if article.get('original_lang') == 'zh' or contains_chinese(article['title']):
                article['title_zh'] = article['title']
                article['summary_zh'] = article['summary']
                skipped_count += 1
                continue
            
            print(f"  [{i}/{len(articles)}] {article['source']}: {article['title'][:40]}...")
            
            article['title_zh'] = translate_text(article['title'], api_key, cache)
            time.sleep(0.2)
            
            if article['summary']:
                article['summary_zh'] = translate_text(article['summary'], api_key, cache)
                time.sleep(0.2)
            else:
                article['summary_zh'] = ''
            
            if article['title_zh'] != article['title']:
                translated_count += 1
            else:
                failed_count += 1
    
    print(f"✅ 翻译完成：{translated_count} 篇成功，{failed_count} 篇失败，{skipped_count} 篇跳过 (已是中文)")
    return articles

def main():
    print("🌍 Global News Fetcher (阿里云百炼 Qwen 翻译)")
    print("=" * 50)
    
    # 检查 API Key
    api_key = get_api_key()
    if api_key:
        print(f"✅ 阿里云 API Key 已配置")
    else:
        print("⚠️  未配置阿里云 API Key")
        print("   获取方式：https://bailian.console.aliyun.com/")
    
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
        time.sleep(0.2)  # 避免请求过快
    
    print("=" * 50)
    
    # 去重
    unique_articles = deduplicate_articles(all_articles)
    print(f"📰 Total articles: {len(all_articles)}")
    print(f"✨ Unique articles: {len(unique_articles)}")
    
    # 加载翻译缓存
    cache = load_translation_cache() if CACHE_TRANSLATION else {}
    
    # 翻译文章
    unique_articles = translate_articles(unique_articles, api_key, cache, 'zh')
    
    # 保存翻译缓存
    if CACHE_TRANSLATION:
        save_translation_cache(cache)
    
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
        'articles': unique_articles[:150]  # 最多保留 150 篇
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
