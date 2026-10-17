#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""南海政务新闻抓取 —— 南海区政府网站栏目 + 广东省政务搜索（房租 / 租金）

输出 data/nanhai.json，供 docs/nanhai.html 页面展示，以及 souse 等项目做数据分析。
只依赖 Python 标准库（CI 无需额外安装依赖）。

用法:
    python src/fetch_nanhai.py                # 抓取栏目 + 搜索，并为新条目补详情
    python src/fetch_nanhai.py --no-detail    # 只抓列表页，速度快
    python src/fetch_nanhai.py --dry-run      # 不写文件，只打印统计
"""

import argparse
import copy
import hashlib
import html as html_mod
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / 'src'
DATA_DIR = ROOT / 'data'
CONFIG_FILE = SRC_DIR / 'nanhai_sources.json'
OUT_FILE = DATA_DIR / 'nanhai.json'

TAG_RE = re.compile(r'<[^>]+>')
SCRIPT_RE = re.compile(r'<(script|style)\b.*?</\1>', re.I | re.S)
EM_RE = re.compile(r'</?em\b[^>]*>', re.I)
WS_RE = re.compile(r'[ \t\u00a0\u3000]+')
CJK_SPACE_RE = re.compile(r'(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])')
DATE_RE = re.compile(r'([0-9]{4}-[0-9]{2}-[0-9]{2})')

_last_request = 0.0


# ── 基础工具 ─────────────────────────────────────────
def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def strip_tags(text):
    """去掉 HTML 标签与实体，压缩空白。搜索结果里的 <em> 高亮标签直接剔除（不留下空格）。"""
    if not text:
        return ''
    text = SCRIPT_RE.sub(' ', str(text))
    text = EM_RE.sub('', text)
    text = TAG_RE.sub(' ', text)
    text = html_mod.unescape(text)
    text = text.replace('\u200b', '')
    text = WS_RE.sub(' ', text)
    text = re.sub(r'\s*\n\s*', '\n', text)
    text = CJK_SPACE_RE.sub('', text)
    return text.strip()


def clip(text, limit=180):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '…'


def polite(delay):
    """对政府站点保持低频率访问。"""
    global _last_request
    wait = delay - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.time()


def build_opener(user_agent):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [
        ('User-Agent', user_agent),
        ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
        ('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8'),
        ('Connection', 'keep-alive'),
    ]
    return opener


def http_get(opener, url, timeout=20):
    try:
        with opener.open(url, timeout=timeout) as resp:
            raw = resp.read()
        return raw.decode('utf-8', errors='ignore')
    except Exception as exc:
        print(f'  ⚠️ 请求失败 {url} — {exc}')
        return None


def http_post_json(opener, url, payload, timeout=20, headers=None):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json, text/plain, */*')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
        return json.loads(raw.decode('utf-8', errors='ignore'))
    except Exception as exc:
        print(f'  ⚠️ 搜索接口失败 — {exc}')
        return None


# ── 列表页解析 ───────────────────────────────────────
def parse_section_list(html, section, base_url, list_url):
    """解析栏目列表页：只取带日期(span.time)的 li 项。"""
    cut = html.find('id="pageDiv"')
    body = html[:cut] if cut > 0 else html

    items, seen = [], set()
    for block in re.findall(r'<li[^>]*>(.*?)</li>', body, re.S):
        anchor = re.search(r'<a\b([^>]*)>(.*?)</a>', block, re.S)
        if not anchor:
            continue
        attrs, inner = anchor.group(1), anchor.group(2)

        href_match = re.search(r'href="([^"]+)"', attrs)
        if not href_match:
            continue
        href = html_mod.unescape(href_match.group(1)).strip()
        if not href or href.startswith(('#', 'javascript:')):
            continue

        date_span = re.search(r'class="time"[^>]*>\s*([^<]*)', block)
        date_match = DATE_RE.search(date_span.group(1)) if date_span else None
        if not date_match:
            continue

        title = strip_tags(inner)
        if not title:
            title_match = re.search(r'title="([^"]*)"', attrs)
            title = html_mod.unescape(title_match.group(1)).strip() if title_match else ''
        if not title:
            continue

        if href.startswith('http'):
            link = href
        elif href.startswith('/'):
            link = base_url + href
        else:
            link = urllib.parse.urljoin(list_url, href)

        if link in seen:
            continue
        seen.add(link)

        items.append({
            'title': title,
            'link': link,
            'published': date_match.group(1),
            'source': '南海区人民政府 · ' + section['name'],
            'category': section['category'],
            'section': section['id'],
            'priority': section.get('priority', 3),
        })
    return items


# ── 详情页解析 ───────────────────────────────────────
def parse_detail(html, base_link=''):
    """解析正文页，返回 (摘要, 关键词, 正文文本, 附件列表)。"""
    keywords = ''
    kw_match = re.search(r'<div class="article-keyword"[^>]*>(.*?)</div>', html, re.S)
    if kw_match:
        keywords = strip_tags(kw_match.group(1))
        keywords = re.sub(r'^关键词[：:]\s*', '', keywords)

    text = ''
    marker = html.find('id="zoomcon"')
    if marker != -1:
        end = html.find('<div class="article-relTit"', marker)
        if end == -1:
            end = marker + 40000
        text = strip_tags(html[marker:end])

    summary = clip(re.sub(r'\s+', ' ', text).strip(), 200)
    return summary, keywords, text, extract_attachments(html, base_link)


ATTACHMENT_RE = re.compile(
    r'<a\b[^>]*href="([^"]+\.(?:pdf|doc|docx|xls|xlsx|zip))"[^>]*>(.*?)</a>', re.I | re.S)


def extract_attachments(html, base_link):
    """提取正文页的附件（租金标准等政策数据通常是 PDF 表格）。"""
    attachments, seen = [], set()
    for raw, label in ATTACHMENT_RE.findall(html):
        url = html_mod.unescape(raw).strip()
        if url.startswith('/'):
            url = 'http://www.nanhai.gov.cn' + url
        elif not url.startswith('http') and base_link:
            url = urllib.parse.urljoin(base_link, url)
        if not url.startswith('http') or url in seen:
            continue
        seen.add(url)
        name = strip_tags(label) or urllib.parse.unquote(url.rsplit('/', 1)[-1])
        if not name.lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip')):
            name = f'{name}.pdf' if len(name) < 60 else name
        attachments.append({'name': clip(name, 80), 'url': url})
        if len(attachments) >= 8:
            break
    return attachments


RENT_SENTENCE_RE = re.compile(r'租金|房租|租赁|公租房|指导价|元\s*/\s*平方米|平方米\s*[·•]?\s*月|押金')


def extract_rent_snippets(text, limit=4, max_len=140):
    """从正文里摘出与租金相关的句子，方便 AI 直接读取价格信息。"""
    if not text:
        return []
    out = []
    for sentence in re.split(r'(?<=[。；！!?？])|\n', text):
        sentence = sentence.strip()
        if not 4 <= len(sentence) <= max_len:
            continue
        if RENT_SENTENCE_RE.search(sentence) and sentence not in out:
            out.append(sentence)
        if len(out) >= limit:
            break
    return out


# ── 标签 ────────────────────────────────────────────
def detect_tags(text, tag_rules):
    tags = []
    for tag, words in tag_rules.items():
        for word in words:
            if word in text:
                tags.append(tag)
                break
    return tags


def normalize_key(title):
    return re.sub(r'[^0-9a-z\u4e00-\u9fff]', '', (title or '').lower())


def make_id(title):
    return 'nh' + hashlib.md5(normalize_key(title).encode('utf-8')).hexdigest()[:10]


# ── 广东省政务搜索（房租 / 租金）──────────────────────
def search_csrf_token(opener, cfg, timeout):
    page = http_get(opener, cfg['page_url'], timeout)
    if not page:
        return ''
    match = re.search(r"_CSRF\s*=\s*'([^']+)'", page)
    return match.group(1) if match else ''


def fetch_search(opener, cfg, section_cfg, timeout):
    """调用 search.gd.gov.cn 的搜索接口，返回南海区范围内的房租/租金条目。"""
    search = cfg['search']
    token = search_csrf_token(opener, search, timeout)
    if not token:
        print('  ⚠️ 未取得搜索接口令牌，跳过后台搜索')

    items, seen = [], set()
    for keyword in search['keywords']:
        for page in range(1, int(search.get('pages', 1)) + 1):
            polite(cfg['request']['delay'])
            payload = {
                'keywords': keyword,
                'site_id': search['site_id'],
                'range': search.get('range', 'site'),
                'position': search.get('position', 'title'),
                'page': page,
                'pageSize': search.get('page_size', 20),
                'sort': search.get('sort', 'smart'),
            }
            data = http_post_json(
                opener, search['endpoint'], payload, timeout,
                {
                    'X-CSRF-TOKEN': token,
                    'X-Requested-With': 'XMLHttpRequest',
                    'Referer': search['referer'],
                    'Origin': 'https://search.gd.gov.cn',
                },
            )
            if not data or data.get('errcode') != 0:
                break

            result = (data.get('data') or {}).get('news') or {}
            for row in result.get('list') or []:
                title = strip_tags(row.get('title') or '')
                link = (row.get('url') or row.get('post_url') or row.get('full_url') or '').strip()
                if not title or not link:
                    continue
                if link in seen:
                    continue
                seen.add(link)

                published = (row.get('pub_time') or '')[:10]
                if not DATE_RE.match(published):
                    published = ''

                items.append({
                    'title': title,
                    'link': link,
                    'published': published,
                    'source': strip_tags(row.get('publisher') or row.get('source') or '') or section_cfg['name'],
                    'category': search.get('category', '政策公告'),
                    'section': 'search',
                    'priority': 1,
                    'summary': clip(strip_tags(row.get('content') or row.get('abstract') or ''), 180),
                    'query': keyword,
                })
            print(f'  · 搜索「{keyword}」第 {page} 页 → 累计 {len(items)} 条')

            if len(result.get('list') or []) < int(search.get('page_size', 20)):
                break
    return items


# ── 合并与输出 ───────────────────────────────────────
def merge_articles(existing, incoming, tag_rules, rent_hint):
    """按标题去重合并；字段互补，保留更完整的一条。"""
    merged = {}

    def absorb(article):
        key = normalize_key(article['title'])
        if not key:
            return
        tags = detect_tags(article['title'] + ' ' + (article.get('summary') or ''), tag_rules)
        article['tags'] = sorted(set(article.get('tags') or []) | set(tags),
                                key=lambda t: list(tag_rules).index(t) if t in tag_rules else 99)
        article['is_rent'] = '租金' in article['tags'] or bool(rent_hint.search(
            article['title'] + ' ' + (article.get('summary') or '')))
        if article['is_rent'] and '租金' not in article['tags']:
            article['tags'].insert(0, '租金')

        current = merged.get(key)
        if current is None:
            article['sources'] = [article['source']]
            article['id'] = make_id(article['title'])
            merged[key] = article
            return

        # 合并：来源、标签、摘要、租金片段
        if article['source'] not in current['sources']:
            current['sources'].append(article['source'])
        current['tags'] = [t for t in list(tag_rules) if t in set(current['tags']) | set(article['tags'])]
        current['is_rent'] = current['is_rent'] or article['is_rent']
        if len(article.get('summary') or '') > len(current.get('summary') or ''):
            current['summary'] = article['summary']
        for snippet in article.get('rent_snippets') or []:
            if snippet not in current.setdefault('rent_snippets', []):
                current['rent_snippets'].append(snippet)
        if len(current.get('rent_snippets') or []) > 6:
            current['rent_snippets'] = current['rent_snippets'][:6]
        if not current.get('published') and article.get('published'):
            current['published'] = article['published']
        elif article.get('published') and current.get('published') and article['published'] < current['published']:
            current['published'] = article['published']
        if article.get('attachments'):
            current['attachments'] = article['attachments']
        if article.get('keywords'):
            current['keywords'] = article['keywords']
        # 优先保留政府网站正式链接与更具体的栏目
        if 'nanhai.gov.cn' in (article.get('link') or '') and 'nanhai.gov.cn' not in current.get('link', ''):
            current['link'] = article['link']
        if current.get('category') == '政策公告' and article.get('category') != '政策公告':
            current['category'] = article['category']

    for article in existing:
        absorb(article)
    for article in incoming:
        absorb(article)

    ordered = list(merged.values())
    ordered.sort(key=lambda a: (a.get('published') or '', a.get('title') or ''), reverse=True)
    return ordered


def build_stats(articles, tag_rules):
    by_category, by_tag = {}, {}
    for article in articles:
        by_category[article['category']] = by_category.get(article['category'], 0) + 1
        for tag in article.get('tags') or []:
            by_tag[tag] = by_tag.get(tag, 0) + 1
    return {
        'by_category': dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        'by_tag': dict(sorted(by_tag.items(), key=lambda kv: -kv[1])),
        'rent': sum(1 for a in articles if a.get('is_rent')),
    }


def main():
    parser = argparse.ArgumentParser(description='南海政务新闻抓取')
    parser.add_argument('--no-detail', action='store_true', help='不抓取正文详情')
    parser.add_argument('--detail-limit', type=int, default=None, help='本次最多抓取的详情页数量')
    parser.add_argument('--dry-run', action='store_true', help='只打印统计，不写入文件')
    args = parser.parse_args()

    cfg = load_config()
    delay = float(cfg['request']['delay'])
    timeout = float(cfg['request']['timeout'])
    opener = build_opener(cfg['request']['user_agent'])
    tag_rules = cfg['tags']
    rent_hint = re.compile(cfg['rent_hint'])

    existing = []
    prev_updated = None
    if OUT_FILE.exists():
        try:
            with open(OUT_FILE, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            existing = payload.get('articles', [])
            prev_updated = payload.get('updated')
        except Exception:
            existing = []
    existing_keys = {normalize_key(a.get('title', '')) for a in existing}
    print(f'📚 已有 {len(existing)} 条南海政务记录')

    # 1) 栏目列表
    incoming = []
    for section in cfg['sections']:
        list_url = cfg['base_url'] + section['url']
        print(f'📰 抓取栏目: {section["name"]}')
        page = http_get(opener, list_url, timeout)
        polite(delay)
        if not page:
            continue
        items = parse_section_list(page, section, cfg['base_url'], list_url)
        print(f'  → {len(items)} 条')
        incoming.extend(items)

    # 2) 搜索（房租 / 租金）
    if cfg['search'].get('enabled'):
        print('🔍 搜索南海区「房租 / 租金」相关条目')
        incoming.extend(fetch_search(opener, cfg, {
            'name': cfg['name'], 'category': cfg['search'].get('category', '政策公告')
        }, timeout))

    # 3) 补正文：先抓新条目（优先租金相关），再用剩余额度回填历史租金条目
    fresh_map = {}
    for item in incoming:
        key = normalize_key(item['title'])
        if not key or key in existing_keys or key in fresh_map:
            continue
        fresh_map[key] = item
    fresh = list(fresh_map.values())

    fetched_detail = 0
    if not args.no_detail:
        limit = args.detail_limit if args.detail_limit is not None else int(cfg['request']['max_detail_per_run'])
        queue = sorted(fresh, key=lambda a: 0 if rent_hint.search(a['title']) else 1)[:limit]
        used_keys = {normalize_key(a['title']) for a in queue}
        for item in existing:   # 历史租金条目回填（只回填政府网站正文页，且未检查过）
            if len(queue) >= limit:
                break
            key = normalize_key(item.get('title', ''))
            if key in used_keys or not item.get('is_rent') or item.get('detail_checked'):
                continue
            if 'nanhai.gov.cn' not in (item.get('link') or ''):
                continue
            queue.append(item)
            used_keys.add(key)

        for article in queue:
            print(f'  🔎 详情: {article["title"][:28]}')
            attempts = int(article.get('detail_attempts', 0)) + 1
            article['detail_attempts'] = attempts
            page = http_get(opener, article['link'], timeout)
            polite(delay)
            if not page:
                if attempts >= 3:
                    article['detail_checked'] = True   # 连续失败 3 次后不再重试
                continue
            summary, keywords, text, attachments = parse_detail(page, article.get('link', ''))
            if summary and not article.get('summary'):
                article['summary'] = summary
            if keywords:
                article['keywords'] = keywords
            article['rent_snippets'] = extract_rent_snippets(text)
            if attachments:
                article['attachments'] = attachments
            article['detail_checked'] = True
            fetched_detail += 1

    articles = merge_articles(existing, incoming, tag_rules, rent_hint)
    articles = articles[: int(cfg['max_articles'])]
    stats = build_stats(articles, tag_rules)

    # 内容没变化时保留原更新时间，避免产生“只改时间戳”的无意义提交
    # 注意：合并过程中会就地修改 existing 里的字典，所以要先深拷贝快照再比较
    snapshot = copy.deepcopy(existing)
    unchanged = bool(snapshot) and (
        json.dumps(articles, ensure_ascii=False, sort_keys=True)
        == json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    )

    data = {
        'updated': prev_updated if (unchanged and prev_updated) else datetime.now(timezone.utc).isoformat(),
        'region': cfg['region'],
        'source_name': cfg['name'],
        'total': len(articles),
        'rent_total': stats['rent'],
        'stats': stats,
        'articles': articles,
    }

    print(f'✅ 抓取 {len(incoming)} 条（新增详情 {fetched_detail} 页），合并后 {len(articles)} 条，其中租金相关 {stats["rent"]} 条')
    if unchanged:
        print('ℹ️ 数据无变化，保留原 updated 时间')

    if args.dry_run:
        print('ℹ️ dry-run：未写入文件')
        print(json.dumps(stats['by_tag'], ensure_ascii=False))
        return

    DATA_DIR.mkdir(exist_ok=True)
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'💾 已保存 {OUT_FILE.relative_to(ROOT)}')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
