#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""南海政务分析 —— 对 data/nanhai.json 做离线图文分析（不依赖任何第三方库）

逐条标注 年/月、事实类型、情绪、价格；聚合出按月统计、情绪分布、事实类型分布、
价格序列与高频关键词，产出 data/analysis.json（并同步 docs/data/analysis.json）。

用法:
    python3 src/analyze_nanhai.py                 # 生成 data/analysis.json + docs/data/analysis.json
    python3 src/analyze_nanhai.py --dry-run       # 只打印统计，不写文件
    python3 src/analyze_nanhai.py --input x.json --output y.json
"""

import argparse
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'
DOCS_DATA_DIR = ROOT / 'docs' / 'data'
IN_FILE = DATA_DIR / 'nanhai.json'
OUT_FILE = DATA_DIR / 'analysis.json'
DOCS_OUT_FILE = DOCS_DATA_DIR / 'analysis.json'

# ── 事实类型规则（按得分最高判定，键顺序即同分优先级）────────
FACT_KEYWORDS = OrderedDict([
    ('通知公告', ['公告', '公示', '听证', '通告', '告示', '送达', '任免', '拟聘', '注销',
                 '征求意见', '公开征求', '批前公示', '记录表']),
    ('政策', ['政策', '办法', '规定', '条例', '实施细则', '实施意见', '实施方案', '规划',
             '细则', '若干措施', '批复', '决定', '标准', '解读', '一图读懂']),
    ('数据披露', ['统计数据', '数据', '公报', '快报', '运行情况', '经济运行', '同比', '环比',
                '亿元', '万元', '财政', '指数', '增速', '增幅', '披露', '水平信息', '名单']),
    ('项目动态', ['项目', '开工', '竣工', '签约', '落地', '投产', '动工', '启动', '建设',
                '招标', '中标', '采购', '招商', '揭牌', '建成', '配建', '认定书', '立项']),
    ('民生服务', ['民生', '服务', '公租房', '租金', '房租', '补贴', '社保', '医保', '养老',
                '招聘', '就业', '入学', '招生', '医疗', '住房保障', '低保', '救助',
                '办理', '便民', '申请', '配租', '卫生']),
])

# 分类对事实类型的加分（首页栏目本身带语义）
FACT_CATEGORY_BONUS = {
    '通知公告': ('通知公告', 3),
    '政策公告': ('政策', 2),
}

# ── 情绪词典（离线，可调）。政务文本默认中性，命中正/负词才改判 ──
POS_WORDS = [
    '增长', '提升', '新增', '成功', '完成', '启用', '建成', '开通', '获批', '入选',
    '荣获', '优化', '改善', '利好', '突破', '达成', '顺利', '推进', '支持', '减免',
    '补贴', '优惠', '惠民', '保障', '亲民', '便捷', '高效', '签约', '落地', '竣工',
    '提高', '扩大', '增长', '发展', '繁荣', '活力', '提升', '创收', '增收',
]
NEG_WORDS = [
    '事故', '处罚', '罚款', '违法', '违规', '死亡', '受伤', '坍塌', '火灾', '内涝',
    '风险', '下滑', '亏损', '污染', '投诉', '举报', '整改', '问责', '撤销', '取消',
    '废标', '终止', '逾期', '拖欠', '纠纷', '被坑', '陷阱', '诈骗', '骗子', '隐患',
    '预警', '应急', '暴雨', '台风', '寒潮', '大雾', '降温', '损失', '警告', '处分',
]

# ── 价格抽取：元/㎡、元/平方米、元/月 等（正文文本层）────────
PRICE_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*元\s*[/每]\s*(平方米|㎡|m²|m2|平|月)')
UNIT_ALIAS = {
    '平方米': '㎡', '㎡': '㎡', 'm²': '㎡', 'm2': '㎡', '平': '㎡', '月': '月',
}

# ── 关键词停用字（含这些字的 n-gram 直接丢弃）──────────────
STOP_CHARS = set('的了和在与及等是为将对以其并或可要不到上下这那有个我你他她它们'
                 '一二三四五六七八九十百千万亿年月日时分秒第批次号区区街镇村组项目'
                 '关于工作区内中国广东佛山南海进行以及有关相关目前已经通过进一步')


def parse_ym(published):
    m = re.match(r'(\d{4})-(\d{2})', published or '')
    if not m:
        return None, None
    year, month = int(m.group(1)), int(m.group(2))
    return year, (month if 1 <= month <= 12 else None)


def classify_fact(title, summary, category):
    title = title or ''
    summary = summary or ''
    best_type, best_score = '其他', 0
    for fact_type, words in FACT_KEYWORDS.items():
        score = 0
        for word in words:
            if word in title:
                score += 2
            elif word in summary:
                score += 1
        if score > best_score:
            best_type, best_score = fact_type, score
    if category in FACT_CATEGORY_BONUS:
        bonus_type, bonus = FACT_CATEGORY_BONUS[category]
        if bonus_type == best_type:
            best_score += bonus
        elif best_score == 0:
            best_type, best_score = bonus_type, bonus
    return best_type


def detect_sentiment(text):
    pos = sum(text.count(w) for w in POS_WORDS)
    neg = sum(text.count(w) for w in NEG_WORDS)
    if pos > neg:
        return '正'
    if neg > pos:
        return '负'
    return '中'


def extract_prices(article):
    text = ' '.join([
        article.get('title') or '',
        article.get('summary') or '',
        ' '.join(article.get('rent_snippets') or []),
    ])
    year, month = parse_ym(article.get('published'))
    period = f'{year}-{month:02d}' if year and month else (str(year) if year else '未知')
    out, seen = [], set()
    for match in PRICE_RE.finditer(text):
        value = match.group(1)
        unit = UNIT_ALIAS.get(match.group(2), match.group(2))
        tail = text[match.end():match.end() + 2]
        if tail.startswith('·月') or tail.startswith('•月'):
            unit = f'{unit}·月'
        key = (value, unit, match.start())
        if key in seen:
            continue
        seen.add(key)
        context = text[max(0, match.start() - 24):match.end() + 12].strip()
        out.append({
            'period': period,
            'value': float(value),
            'unit': unit,
            'context': context,
            'link': article.get('link') or '',
            'title': article.get('title') or '',
        })
    return out


def top_keywords(texts, limit=20, min_count=3, superset_ratio=0.55, max_n=8):
    """简单词频：统计 2-4 字 n-gram，过滤停用字与“片段词”。

    片段词判定：若某个 n-gram 近乎完整地出现在一个更长的高频 n-gram 中
    （片段计数 >= 0.9 × 更长词计数），则视为切词碎片丢弃，如“赁住”。
    """
    grams = Counter()
    for text in texts:
        for run in re.findall(r'[\u4e00-\u9fff]+', text or ''):
            for n in range(2, max_n + 1):
                for i in range(len(run) - n + 1):
                    gram = run[i:i + n]
                    if any(c in STOP_CHARS for c in gram):
                        continue
                    grams[gram] += 1

    max_superset = {}
    for gram, count in grams.items():
        n = len(gram)
        for i in range(n):
            for j in range(i + 2, n + 1):
                sub = gram[i:j]
                if sub != gram and count > max_superset.get(sub, 0):
                    max_superset[sub] = count

    picked = []
    for gram, count in grams.most_common():
        if count < min_count:
            break
        if max_superset.get(gram, 0) >= superset_ratio * count:
            continue
        picked.append((gram, count))
        if len(picked) >= limit:
            break
    return [{'word': w, 'count': c} for w, c in picked]


def analyze(payload):
    articles = payload.get('articles') or []
    annotated, by_ym, sentiment_by_ym = [], OrderedDict(), OrderedDict()
    fact_dist, sentiment_dist = Counter(), Counter()
    price_series = []

    for article in articles:
        year, month = parse_ym(article.get('published'))
        title = article.get('title') or ''
        summary = article.get('summary') or ''
        fact_type = classify_fact(title, summary, article.get('category'))
        sentiment = detect_sentiment(title + ' ' + summary + ' ' + ' '.join(article.get('rent_snippets') or []))
        prices = extract_prices(article)

        annotated.append({
            'id': article.get('id') or '',
            'title': title,
            'link': article.get('link') or '',
            'summary': summary,
            'published': article.get('published') or '',
            'category': article.get('category') or '',
            'tags': article.get('tags') or [],
            'year': year,
            'month': month,
            'fact_type': fact_type,
            'sentiment': sentiment,
            'prices': prices,
        })
        fact_dist[fact_type] += 1
        sentiment_dist[sentiment] += 1
        price_series.extend(prices)

        if year:
            ym = f'{year}-{month:02d}' if month else str(year)
            by_ym[ym] = by_ym.get(ym, 0) + 1
            bucket = sentiment_by_ym.setdefault(ym, {'正': 0, '中': 0, '负': 0})
            bucket[sentiment] += 1

    by_ym = OrderedDict(sorted(by_ym.items()))
    sentiment_by_ym = OrderedDict(sorted(sentiment_by_ym.items()))
    price_series.sort(key=lambda p: (p['period'], p['value']))

    texts = [(a.get('title') or '') + ' ' + (a.get('title') or '') + ' ' + (a.get('summary') or '')
             for a in articles]
    keywords = top_keywords(texts)

    return {
        'updated': payload.get('updated') or '',
        'region': payload.get('region') or '',
        'source_total': len(articles),
        'annotated_count': len(annotated),
        'articles': annotated,
        'by_ym': dict(by_ym),
        'sentiment_by_ym': {k: dict(v) for k, v in sentiment_by_ym.items()},
        'fact_type_dist': dict(fact_dist.most_common()),
        'sentiment_dist': dict(sentiment_dist),
        'price_series': price_series,
        'top_keywords': keywords,
    }


def main():
    parser = argparse.ArgumentParser(description='南海政务新闻分析')
    parser.add_argument('--input', default=str(IN_FILE), help='输入 nanhai.json 路径')
    parser.add_argument('--output', default=str(OUT_FILE), help='输出 analysis.json 路径')
    parser.add_argument('--no-sync', action='store_true', help='不同步到 docs/data/')
    parser.add_argument('--dry-run', action='store_true', help='只打印统计，不写文件')
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f'❌ 找不到输入文件: {in_path}')
        return 1
    with open(in_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    result = analyze(payload)
    print(f"📊 分析 {result['source_total']} 条 → 事实类型 {len(result['fact_type_dist'])} 类，"
          f"情绪 {result['sentiment_dist']}，价格 {len(result['price_series'])} 条，"
          f"年月跨度 {len(result['by_ym'])} 期")
    print('事实类型分布:', json.dumps(result['fact_type_dist'], ensure_ascii=False))
    print('情绪分布:', json.dumps(result['sentiment_dist'], ensure_ascii=False))
    print('by_ym 样例:', dict(list(result['by_ym'].items())[:6]))
    print('关键词 Top:', [k['word'] for k in result['top_keywords'][:10]])

    if args.dry_run:
        print('ℹ️ dry-run：未写入文件')
        return 0

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    out_path.write_text(text, encoding='utf-8')
    print(f'💾 已保存 {out_path}')

    if not args.no_sync:
        synced = False
        if out_path.resolve() == OUT_FILE.resolve():
            DOCS_OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
            DOCS_OUT_FILE.write_text(text, encoding='utf-8')
            synced = True
        if synced:
            print(f'💾 已同步 {DOCS_OUT_FILE}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
