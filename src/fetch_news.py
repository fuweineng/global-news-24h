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
NEWS_FILE = Path('data/news.json')

# ── 翻译规模控制 ─────────────────────────────────────
RETRANSLATE_LIMIT = 80       # 每轮最多补译多少条历史文章（额度有限，分轮自愈）
TRANSLATE_MAX_CHARS = 60000  # 单轮送进翻译 API 的字符上限，防止额度被瞬间打穿
COVERAGE_TARGET = 0.90       # 中文标题覆盖率告警阈值
TRANSLATE_RETRY_DELAYS = (0.5, 1.5, 4.0)  # 失败重试的指数退避
MYMEMORY_QUOTA_MARK = 'MYMEMORY WARNING'

# 本轮运行态：额度/预算耗尽后不再发起请求，避免 CI 被重试拖死
TRANSLATE_STATE = {
    'quota_exhausted': False,
    'budget_exhausted': False,
    'chars': 0,
    'translated': 0,
    'failed': 0,
}

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
    """调用 MyMemory 翻译单段文字。

    返回 (translated, ok)。失败时 translated 为 None —— 绝不拿英文原文冒充译文，
    否则缓存里会留下"看起来已翻译"的英文，下一轮判据永远认为它已完成。
    """
    text = clean_text(text)
    if not text or len(text.strip()) < 3:
        return text, True

    # 中文源短路：原文已是中文就不再调 API（按内容判断，不按源名硬编码）
    if src_lang == 'zh' or is_chinese(text):
        return text, True

    if TRANSLATE_STATE['quota_exhausted'] or TRANSLATE_STATE['budget_exhausted']:
        return None, False

    if TRANSLATE_STATE['chars'] + len(text) > TRANSLATE_MAX_CHARS:
        TRANSLATE_STATE['budget_exhausted'] = True
        print(f"⚠️ 本轮翻译字符预算 {TRANSLATE_MAX_CHARS} 已用尽，剩余条目留待下一轮")
        return None, False

    last_error = ''
    for attempt, delay in enumerate((0.0,) + TRANSLATE_RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            url = f"{MYMEMORY_API}?q={urllib.parse.quote(text[:500])}&langpair={src_lang}|zh"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())

            translated = clean_text(result.get('responseData', {}).get('translatedText', ''))
            status = result.get('responseStatus')

            # 免费额度耗尽：重试没有意义，直接熔断本轮（否则每条都要空转 3 次退避）
            if status == 403 or MYMEMORY_QUOTA_MARK in translated.upper():
                TRANSLATE_STATE['quota_exhausted'] = True
                print(f"⚠️ 翻译额度耗尽，本轮停止翻译：{text[:40]}")
                return None, False

            if status not in (200, '200') or not translated:
                last_error = f"status={status} {str(result.get('responseDetails', ''))[:80]}"
                continue

            TRANSLATE_STATE['chars'] += len(text)
            TRANSLATE_STATE['translated'] += 1
            return translated, True
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"

    TRANSLATE_STATE['failed'] += 1
    print(f"⚠️ 翻译失败（已重试 {len(TRANSLATE_RETRY_DELAYS)} 次）：{text[:40]} —— {last_error[:120]}")
    return None, False

def translate_article(article):
    """就地补齐单篇文章的 zh_title / zh_summary；失败时保留原值，不伪造中文。"""
    title = clean_text(article.get('title', ''))
    summary = clean_text(article.get('summary', ''))
    lang = article.get('original_lang', 'en')

    # 1. 中文标题：非中文（或为空）才翻；中文源直接用原文
    if not is_chinese(article.get('zh_title')):
        if lang == 'zh':
            neutral_title = title
        else:
            neutral_title = rewrite_english_for_neutrality(neutralize_title(title), is_title=True)
        zh_title, ok = translate_text(neutral_title, lang)
        if ok and zh_title:
            article['zh_title'] = polish_chinese(zh_title, is_title=True)
        time.sleep(0.15)

    # 2. 中文摘要：同理，中文源不调翻译 API
    if summary and not is_chinese(article.get('zh_summary')):
        neutral_summary = clip_to_sentence(summary)
        if lang != 'zh':
            neutral_summary = rewrite_english_for_neutrality(neutral_summary, is_title=False)
        zh_summary, ok = translate_text(neutral_summary, lang)
        if ok and zh_summary:
            article['zh_summary'] = polish_chinese(zh_summary, is_title=False)
        time.sleep(0.15)

    article['zh_title'] = article.get('zh_title') or ''
    article['zh_summary'] = article.get('zh_summary') or ''
    article['one_line'] = article['zh_title'] or title  # 向后兼容
    return article

def translate_articles(articles):
    """翻译一批文章为中文 + 中立化"""
    if not articles:
        return articles

    print(f"🤖 翻译 {len(articles)} 篇...")
    for i, article in enumerate(articles):
        translate_article(article)
        if TRANSLATE_STATE['quota_exhausted'] or TRANSLATE_STATE['budget_exhausted']:
            print(f"  ⏹ 已处理 {i + 1}/{len(articles)}，本轮翻译提前结束（下一轮继续）")
            break
        if (i + 1) % 15 == 0:
            print(f"  翻译进度 {i+1}/{len(articles)}")

    print(f"✅ 翻译完成（成功 {TRANSLATE_STATE['translated']} 次，失败 {TRANSLATE_STATE['failed']} 次）")
    return articles

def report_coverage(articles):
    """统计中文标题覆盖率；低于阈值只告警、不让 CI 失败（数据问题不该堵住发布）。"""
    total = len(articles)
    zh = sum(1 for a in articles if is_chinese(a.get('zh_title')))
    rate = (zh / total) if total else 0.0
    print(f"📊 中文标题覆盖率：{zh}/{total} = {rate:.1%}")
    if total and rate < COVERAGE_TARGET:
        print(f"⚠️ 中文覆盖率 {rate:.0%} 低于 {COVERAGE_TARGET:.0%}"
              f"（翻译额度/网络受限，下一轮继续自愈；前端已用 ·EN 标记降级）")
    return rate

def fetch_news():
    sources_file = Path('src/sources.json')
    if not sources_file.exists():
        print("❌ sources.json not found")
        return [], []

    with open(sources_file, 'r') as f:
        sources = json.load(f)['sources']

    sources.sort(key=lambda s: s.get('priority', 99))

    cache = load_cache()
    cached_articles = cache.get('articles', [])
    cached_ids = {a['id'] for a in cached_articles}

    new_articles = []
    seen_normalized = set()
    print(f"📰 抓取 {len(sources)} 个源（缓存已有 {len(cached_articles)} 篇）...")

    for source in sources:
        try:
            feed = feedparser.parse(source['rss'])
            if not feed.entries:
                print(f"⚠️ {source['name']} 无条目：{source['rss']}")
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
                new_articles.append(article)
        except Exception as e:
            print(f"⚠️ {source['name']} 失败：{e}")
        time.sleep(0.2)

    print(f"✅ 本轮新抓 {len(new_articles)} 篇（缓存 {len(cached_articles)} 篇）")
    return new_articles, cached_articles

def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    # data/news_cache.json 不随仓库提交（CI 每次 checkout 都是空缓存），
    # 用已发布的 data/news.json 兜底；否则每轮都要从零重译 200+ 条，翻译额度必然被打穿。
    if NEWS_FILE.exists():
        with open(NEWS_FILE, 'r') as f:
            data = json.load(f)
        if isinstance(data.get('articles'), list):
            return {'articles': data['articles'], 'updated': data.get('updated')}
    return {'articles': [], 'updated': None}

def save_cache(data):
    CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    new_articles, cached_articles = fetch_news()
    if not new_articles and not cached_articles:
        print("ℹ️ 无新新闻")
        return

    # 1) 本轮新抓的文章：标题 + 摘要全量翻译
    translate_articles(new_articles)

    # 2) 历史文章补译：判据是「zh_title 不是中文」而不是「zh_title 为空」。
    #    旧逻辑失败时把英文原文写进 zh_title，非空 → 永远不再重译。
    pending = [a for a in cached_articles if not is_chinese(a.get('zh_title'))]
    if pending:
        pending.sort(key=lambda a: a.get('published') or '', reverse=True)
        batch = pending[:RETRANSLATE_LIMIT]
        print(f"🔁 历史文章待补译 {len(pending)} 篇，本轮处理 {len(batch)} 篇")
        for article in batch:
            if TRANSLATE_STATE['quota_exhausted'] or TRANSLATE_STATE['budget_exhausted']:
                print("  ⏹ 翻译额度受限，剩余补译留待下一轮")
                break
            translate_article(article)

    # 3) 合并：同 id 用本轮新抓的覆盖，历史文章保留
    merged = {a['id']: a for a in cached_articles}
    for a in new_articles:
        merged[a['id']] = a
    articles = list(merged.values())
    articles.sort(key=lambda a: (a.get('priority', 2), a.get('published') or ''))
    articles = articles[:500]

    updated_at = datetime.now(timezone.utc).isoformat()
    save_cache({'articles': articles, 'updated': updated_at})

    coverage = report_coverage(articles)

    data = {
        'updated': updated_at,
        'total': len(articles),
        'zh_coverage': round(coverage, 4),
        'articles': articles
    }

    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    with open(data_dir / 'news.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ 保存到 data/news.json ({len(articles)} 篇)")

if __name__ == '__main__':
    main()
