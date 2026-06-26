#!/usr/bin/env python3
"""全球新闻抓取 - MyMemory 翻译 + 中文化改写 + 中性表达 + 智能去重"""

import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import html
import time
import urllib.request
import urllib.parse
import re

MYMEMORY_API = "https://api.mymemory.translated.net/get"
CACHE_FILE = Path('data/news_cache.json')

# ── 标感词/头缀 过滤 ─────────────────────────────────
SENSATIONAL_PREFIXES = [
    r'^BREAKING\s*:?\s*', r'^BREAKING NEWS\s*:?\s*',
    r'^EXCLUSIVE\s*:?\s*', r'^URGENT\s*:?\s*',
    r'^JUST IN\s*:?\s*', r'^UPDATE\s*:?\s*',
    r'^FLASH\s*:?\s*', r'^DEVELOPING\s*:?\s*',
    r'^WATCH\s*:?\s*', r'^LIVE\s*:?\s*',
    r'^VIDEO\s*:?\s*',
]
SENSATIONAL_PATTERN = re.compile('|'.join(SENSATIONAL_PREFIXES), re.IGNORECASE)

# 语气原则：做“中文新闻标题”，不是逐词翻译，也不做营销标题。
# 目标：事实优先、表达克制、避免标题党/导购腔/直译腔。
EN_TITLE_REWRITES = [
    # The Verge / Tech 媒体常见标题口语化表达
    (re.compile(r'^(?P<topic>.+?)\s+just got extremely real$', re.I),
     r'Effects of \g<topic> are becoming more visible'),
    (re.compile(r'^(?P<company>.+?)\s+wants to monopolize your attention$', re.I),
     r'\g<company> adds features aimed at increasing viewing time'),
    (re.compile(r'^score a discounted\s+(?P<item>.+?)\s+before the prices jump$', re.I),
     r'Discounted \g<item> available before planned price increases'),
    (re.compile(r'^the\s+\d+\s+best\s+(?P<item>.+?)\s+deals available during\s+(?P<event>.+)$', re.I),
     r'\g<item> discounts available during \g<event>'),
    (re.compile(r'^(?P<org>.+?)\s+has good news and bad news$', re.I),
     r'\g<org> shares mixed updates'),
]

EN_PHRASE_REWRITES = [
    (re.compile(r'\bRAMag?eddon\b', re.I), 'memory price pressure'),
    (re.compile(r'\bbest deals?\b', re.I), 'discounts'),
    (re.compile(r'\bprice(?:s)? jump\b', re.I), 'planned price increases'),
    (re.compile(r'\bwreak havoc\b', re.I), 'affect'),
    (re.compile(r'\bsticker shock\b', re.I), 'price pressure'),
    (re.compile(r'\bbig-ticket model\b', re.I), 'major model'),
]

ZH_REPLACEMENTS = [
    # 常见机翻/标题党残留
    ('RAMageddon', '内存价格压力'),
    ('RAMaggeddon', '内存价格压力'),
    ('刚刚变得非常真实', '影响进一步显现'),
    ('变得非常真实', '影响进一步显现'),
    ('垄断你的注意力', '提升用户停留时间'),
    ('想垄断你的注意力', '希望提升用户停留时间'),
    ('不干胶冲击', '价格冲击'),
    ('迪斯科舞厅', '折扣'),
    ('造成严重破坏', '带来影响'),
    ('造成严重破坏。', '带来影响。'),
    ('最好的交易', '促销信息'),
    ('最佳交易', '促销信息'),
    ('最佳优惠', '促销信息'),
    ('优惠可用', '有促销'),
    ('可用的', '的'),
    ('大票模型', '重要模型'),
    ('大型机型', '大型模型'),
    ('转轴', 'Reels'),
    ('框架', 'Framework'),
    ('首席执行官', 'CEO'),
    ('共享混合更新', '发布多项更新'),
    ('分享混合更新', '发布多项更新'),
    ('旨在增加观看时间', '用于提升观看时长'),
    ('在计划价格上涨之前提供折扣的', '计划涨价前仍有折扣的'),
    ('提供机器人吸尘器折扣', '有机器人吸尘器促销'),
    ('内存价格压力压力', '内存价格压力'),
]

TITLE_STYLE_REPLACEMENTS = [
    ('最佳', ''),
    ('重磅', ''),
    ('震撼', ''),
    ('炸裂', ''),
    ('史诗级', ''),
    ('疯狂', ''),
]

PROPER_NOUN_FIXES = [
    ('Openai', 'OpenAI'),
    ('Gpt', 'GPT'),
    ('Tiktok', 'TikTok'),
    ('Youtube', 'YouTube'),
    ('Instagram', 'Instagram'),
    ('Xbox', 'Xbox'),
    ('Prime day', 'Prime Day'),
    ('Framework', 'Framework'),
]

def clean_text(text):
    """清理 RSS 里的 HTML、实体和多余空白。"""
    if not text:
        return ''
    text = html.unescape(str(text))
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def clip_to_sentence(text, max_chars=360):
    """尽量按句子截断，避免把半句话送去翻译造成怪句。"""
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars]
    # 找最后一个英文/中文句号；找不到再按词截断。
    m = max(clipped.rfind('. '), clipped.rfind('! '), clipped.rfind('? '),
            clipped.rfind('。'), clipped.rfind('！'), clipped.rfind('？'))
    if m > 80:
        return clipped[:m + 1].strip()
    return clipped.rsplit(' ', 1)[0].strip()

def rewrite_english_for_neutrality(text, is_title=False):
    """先把英文标题/摘要改得更中性，再交给机器翻译。"""
    text = clean_text(text)
    if not text:
        return ''

    if is_title:
        for pattern, repl in EN_TITLE_REWRITES:
            new_text = pattern.sub(repl, text)
            if new_text != text:
                text = new_text
                break

    for pattern, repl in EN_PHRASE_REWRITES:
        text = pattern.sub(repl, text)

    # 去掉标题里的口语感/催促感标点。
    text = re.sub(r'!+$', '', text).strip()
    return text

def polish_chinese(text, is_title=False):
    """修正常见机翻问题，让输出更像自然中文新闻。"""
    text = clean_text(text)
    if not text:
        return ''

    for old, new in ZH_REPLACEMENTS:
        text = text.replace(old, new)

    if is_title:
        for old, new in TITLE_STYLE_REPLACEMENTS:
            text = text.replace(old, new)
        # 标题不需要句号，也尽量不使用感叹号。
        text = text.strip('。.!！ ')

    # 新闻语体里尽量避免“您”。
    text = text.replace('您', '用户')
    text = text.replace('你的', '用户的')

    # 品牌/产品名大小写修复。
    for old, new in PROPER_NOUN_FIXES:
        text = re.sub(old, new, text, flags=re.I)

    # 中英文之间补空格，提升可读性。
    text = re.sub(r'([\u4e00-\u9fff])([A-Za-z0-9][A-Za-z0-9.+-]*)', r'\1 \2', text)
    text = re.sub(r'([A-Za-z0-9][A-Za-z0-9.+-]*)([\u4e00-\u9fff])', r'\1 \2', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # 处理清理后留下的多余连接词/标点。
    text = re.sub(r'，\s*，+', '，', text)
    text = re.sub(r'\s+([，。；：、])', r'\1', text)
    text = re.sub(r'([（《])\s+', r'\1', text)
    text = re.sub(r'\s+([）》])', r'\1', text)
    return text

def is_chinese(text):
    """检测字符串是否以中文为主"""
    if not text:
        return False
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return cjk > len(text) * 0.3

def normalize_title(title):
    """标准化标题用于去重比较"""
    title = title.lower()
    title = re.sub(r'[^a-z0-9\u4e00-\u9fff\s]', '', title)
    title = ' '.join(title.split())
    return title

def neutralize_title(title):
    """移除标感词/头缀，返回中立标题"""
    title = clean_text(title)
    title = SENSATIONAL_PATTERN.sub('', title).strip()
    # 清理多余标点
    title = re.sub(r'\s{2,}', ' ', title)
    title = title.strip(' :;,!?-')
    return title

def translate_text(text, src_lang='en'):
    """调用 MyMemory 翻译单段文字"""
    text = clean_text(text)
    if not text or len(text.strip()) < 3:
        return text
    try:
        url = f"{MYMEMORY_API}?q={urllib.parse.quote(text[:500])}&langpair={src_lang}|zh"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            translation = result.get('responseData', {}).get('translatedText', '')
            return translation if translation else text
    except Exception:
        return text

def translate_articles(articles):
    """翻译全部文章为中文 + 中立化"""
    if not articles:
        return articles

    print(f"🤖 翻译 {len(articles)} 篇...")
    for i, article in enumerate(articles):
        title = clean_text(article.get('title', ''))
        summary = clean_text(article.get('summary', ''))

        # 1. 中立化英文标题（去掉标感词 + 改写口语/标题党表达）
        neutral_title = neutralize_title(title)
        neutral_title = rewrite_english_for_neutrality(neutral_title, is_title=True)

        # 2. 生成中文标题，并做中文化/中性化后处理
        if is_chinese(neutral_title):
            zh_title = neutral_title
        else:
            zh_title = translate_text(neutral_title, article.get('original_lang', 'en'))
            time.sleep(0.15)
        zh_title = polish_chinese(zh_title, is_title=True)

        # 3. 生成中文摘要：先清理 HTML，按句截断，再翻译/润色
        if summary:
            neutral_summary = rewrite_english_for_neutrality(clip_to_sentence(summary), is_title=False)
            zh_summary = translate_text(neutral_summary, article.get('original_lang', 'en'))
            time.sleep(0.15)
        else:
            zh_summary = ''
        zh_summary = polish_chinese(zh_summary, is_title=False)

        article['title'] = title
        article['summary'] = summary
        article['zh_title'] = zh_title
        article['zh_summary'] = zh_summary
        article['one_line'] = zh_title  # 向后兼容

        if (i + 1) % 15 == 0:
            print(f"  翻译进度 {i+1}/{len(articles)}")

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

    cache = load_cache()
    cached_ids = {a['id'] for a in cache.get('articles', [])}

    articles = []
    seen_normalized = set()
    print(f"📰 抓取 {len(sources)} 个源...")

    for source in sources:
        try:
            feed = feedparser.parse(source['rss'])
            for entry in feed.entries[:10]:
                article_id = hashlib.md5(f"{source['id']}-{entry.title}".encode()).hexdigest()[:12]

                if article_id in cached_ids:
                    continue

                raw_title = clean_text(entry.title)
                raw_summary = clean_text(entry.get('summary', ''))
                normalized = normalize_title(raw_title)
                if normalized in seen_normalized:
                    print(f"  ⚠️ 跳过重复：{raw_title[:40]}...")
                    continue
                seen_normalized.add(normalized)

                try:
                    dt = datetime.fromisoformat(entry.get('published', '').replace('Z', '+00:00'))
                    time_str = dt.strftime('%H:%M')
                except:
                    time_str = '--:--'

                article = {
                    'id': article_id,
                    'title': raw_title,
                    'link': entry.link,
                    'published': entry.get('published', datetime.now(timezone.utc).isoformat()),
                    'time': time_str,
                    'source': source['name'],
                    'summary': clip_to_sentence(raw_summary),
                    'category': source['categories'][0] if source.get('categories') else 'world',
                    'original_lang': source.get('language', 'en'),
                    'priority': source.get('priority', 2),
                    'zh_title': '',
                    'zh_summary': '',
                    'one_line': ''
                }
                articles.append(article)
        except Exception as e:
            print(f"⚠️ {source['name']} 失败：{e}")
        time.sleep(0.2)

    articles.sort(key=lambda a: (a.get('priority', 2), a['published']))

    cache['articles'] = articles[:500]
    cache['updated'] = datetime.now(timezone.utc).isoformat()
    save_cache(cache)

    print(f"✅ 抓取 {len(articles)} 篇（缓存 {len(cache['articles'])} 篇）")
    return articles

def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {'articles': [], 'updated': None}

def save_cache(data):
    CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    articles = fetch_news()
    if not articles:
        print("ℹ️ 无新新闻")
        return

    articles = translate_articles(articles)

    # 重新输出全部缓存文章（包括历史文章）以获取中文标题
    cache = load_cache()
    all_cached = cache.get('articles', [])

    # 对新文章补充翻译，历史文章若有缺失则补译
    updated = []
    new_ids = {a['id'] for a in articles}
    for a in all_cached:
        if a['id'] in new_ids:
            # 用新翻译覆盖
            merged = {**a, **next(x for x in articles if x['id'] == a['id'])}
        else:
            merged = a
            # 对旧文章也补翻译
            if not merged.get('zh_title'):
                merged['zh_title'] = merged.get('one_line', '') or merged.get('title', '')
            merged['zh_title'] = polish_chinese(merged.get('zh_title', ''), is_title=True)
            if not merged.get('zh_summary'):
                merged['zh_summary'] = ''
            else:
                merged['zh_summary'] = polish_chinese(merged.get('zh_summary', ''), is_title=False)
            if not merged.get('one_line'):
                merged['one_line'] = merged['zh_title']
            else:
                merged['one_line'] = polish_chinese(merged.get('one_line', ''), is_title=True)
        updated.append(merged)

    data = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'total': len(updated),
        'articles': updated
    }

    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    with open(data_dir / 'news.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ 保存到 data/news.json ({len(updated)} 篇)")

if __name__ == '__main__':
    main()
