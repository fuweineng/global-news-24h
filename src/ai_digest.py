#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 多期聚合解读 —— 把一段时间内的南海政务新闻合并成一份综合解读。

按 published 把 data/nanhai.json 的新闻按期分桶（日 / 周 / 月 / 年，各取最近一期，
即「今天 / 本周 / 本月 / 今年」），对每个非空期调用一次通义千问
（DashScope OpenAI 兼容端点，默认 qwen-plus），产出综合综述 / 分行业要点 /
行动建议 / 关注信号，写入 data/ai_digest.json（并同步 docs/data/ai_digest.json）。

输出结构:
    {
      "updated": ..., "model": ..., "generated_at": ..., "disclaimer": ...,
      "hashes": {"day": ..., "week": ..., "month": ..., "year": ...},
      "periods": {
        "day":   {"range": ..., "count": n, "overview": ..., "sectors": [...],
                  "actions": [...], "signals": [...], "evidence": [...]},
        "week":  {...}, "month": {...}, "year": {...}
      }
    }

- 纯标准库（urllib），不依赖第三方库。
- API Key 只从环境变量 DASHSCOPE_API_KEY 读取，绝不硬编码；无 key 优雅跳过（exit 0，不写）。
- 每期输入指纹缓存：同数据不重复调 API。
- 某期调用失败：保留旧值、不覆盖该期；全部失败 exit 1。
- 某期无新闻：标注空期（count=0），不调 API、不编造。
- --dry-run：不调 API，打印每期的条数 / 时间范围 / 将请求的 prompt 头部。

用法:
    DASHSCOPE_API_KEY=sk-xxx python3 src/ai_digest.py
    python3 src/ai_digest.py --dry-run
    python3 src/ai_digest.py --now 2026-10-16 --model qwen-plus --force
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'
DOCS_DATA_DIR = ROOT / 'docs' / 'data'
IN_FILE = DATA_DIR / 'nanhai.json'
OUT_FILE = DATA_DIR / 'ai_digest.json'
DOCS_OUT_FILE = DOCS_DATA_DIR / 'ai_digest.json'

ENDPOINT = __import__('os').environ.get('AI_BASE_URL') or 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
DEFAULT_MODEL = __import__('os').environ.get('AI_MODEL') or 'qwen-plus'
TIMEOUT = 90          # 单次请求超时（秒）
RETRIES = 2           # 失败后额外重试次数（总尝试 = RETRIES + 1）
PROMPT_VERSION = 'v2-multi-period'
PERIOD_KEYS = ('day', 'week', 'month', 'year')
MAX_SUMMARY = 160     # 每条摘要送入模型的最大字符数
DRY_RUN_PROMPT_HEAD = 220

DISCLAIMER = '本解读由 AI 依据公开政务新闻自动聚合生成，仅供参考，不代表政府立场'

SYSTEM_PROMPT = (
    '你是一名严谨的中文数据分析助手。你只依据用户提供的新闻材料作答，'
    '绝不臆造、绝不编造数据或来源；若材料中没有实质信号，就少给甚至不给结论。'
    '你善于把多条新闻综合成一份有结构的综述，而不是逐条复述。'
)

# 用 str.replace 填充占位符，避免 JSON 花括号与 format 冲突。
USER_TEMPLATE = """你是**佛山市南海区的独立观察者**（不代表政府）。下面是【{period_label}：{range}】的南海政务新闻（含各行业：政策 / 住房租赁 / 产业 / 民生 / 交通 / 教育 / 医疗 / 社保 / 安全等）。

请把它们**综合成一份解读**（**不要逐条复述 / 转发**），只依据给定新闻、不臆造数据，中文。严格**只输出一个 JSON 对象**（不要 markdown 代码块、不要解释文字），字段如下：
- "overview": 本期综述（200-400 字，串起主要动态与行业面）
- "sectors": 分行业要点数组，每项 {{"name": 行业名, "point": 该行业 1-2 句要点}}
- "actions": 可执行行动建议数组（3-5 条字符串，面向经营者 / 居民）
- "signals": 值得关注的信号数组（2-4 条字符串）
- "evidence": 引用的新闻数组，每项 {{"title": 新闻标题, "link": 新闻链接}}（3-8 条）

【新闻材料（共 {count} 条）】
{news}
"""


# ── 日期解析（容错） ───────────────────────────────────
def parse_published(published):
    """解析 published，返回 (date, precision) 或 None。

    precision ∈ {'day', 'month', 'year'}；支持 2026-10-16 / 2026/10/16 /
    2026.10.16 / 2026-10 / 2026 等写法；无法解析返回 None（归入“未知”，不参与分桶）。
    """
    if not published:
        return None
    s = str(published).strip()
    m = re.match(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), 'day'
        except ValueError:
            return None
    m = re.match(r'(\d{4})[-/.](\d{1,2})(?!\d)', s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), 1), 'month'
        except ValueError:
            return None
    m = re.match(r'(\d{4})(?!\d)', s)
    if m:
        try:
            return date(int(m.group(1)), 1, 1), 'year'
        except ValueError:
            return None
    return None


# ── 分桶 ───────────────────────────────────────────────
def period_defs(now):
    """返回四档期定义（各取最近一期 = 今天 / 本周 / 本月 / 今年）。"""
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    month_start = now.replace(day=1)
    next_month = (month_start.replace(year=month_start.year + 1, month=1)
                  if month_start.month == 12
                  else month_start.replace(month=month_start.month + 1))
    month_end = next_month - timedelta(days=1)
    year_start = date(now.year, 1, 1)
    year_end = date(now.year, 12, 31)
    return {
        'day': {'label': '今日', 'start': now, 'end': now,
                'range': now.isoformat()},
        'week': {'label': '本周', 'start': week_start, 'end': week_end,
                 'range': f'{week_start.isoformat()} ~ {week_end.isoformat()}'},
        'month': {'label': '本月', 'start': month_start, 'end': month_end,
                  'range': f'{month_start.isoformat()} ~ {month_end.isoformat()}'},
        'year': {'label': '今年', 'start': year_start, 'end': year_end,
                 'range': f'{year_start.isoformat()} ~ {year_end.isoformat()}'},
    }


def bucket_articles(articles, defs):
    """按期分桶；按精度过滤（日/周需 day 精度，月需 >= month），并各期内部按日期倒序。"""
    buckets = {k: [] for k in defs}
    for a in articles:
        parsed = parse_published(a.get('published'))
        if not parsed:
            continue
        adate, prec = parsed
        for key, cfg in defs.items():
            if key in ('day', 'week') and prec != 'day':
                continue
            if key == 'month' and prec == 'year':
                continue
            if cfg['start'] <= adate <= cfg['end']:
                buckets[key].append(a)
    for key in buckets:
        buckets[key].sort(key=lambda a: a.get('published') or '', reverse=True)
    return buckets


# ── prompt 构造 ────────────────────────────────────────
def build_news_block(articles):
    lines = []
    for i, a in enumerate(articles, 1):
        tags = '/'.join(a.get('tags') or [])
        summary = (a.get('summary') or '').strip().replace('\n', ' ')
        if len(summary) > MAX_SUMMARY:
            summary = summary[:MAX_SUMMARY] + '…'
        line = (
            f"[{i}] 日期:{a.get('published') or '未知'} | 分类:{a.get('category') or ''} | 标签:{tags}\n"
            f"标题:{a.get('title') or ''}\n"
            f"摘要:{summary or '（无摘要）'}\n"
            f"链接:{a.get('link') or ''}"
        )
        lines.append(line)
    return '\n\n'.join(lines)


def build_prompt(config, articles):
    return (USER_TEMPLATE
            .replace('{period_label}', config['label'])
            .replace('{range}', config['range'])
            .replace('{count}', str(len(articles)))
            .replace('{news}', build_news_block(articles)))


def compute_hash(period_key, config, articles, model):
    h = hashlib.sha256()
    h.update(f'{PROMPT_VERSION}|{model}|{period_key}|{config["range"]}|'.encode('utf-8'))
    for a in articles:
        h.update((
            f"{a.get('id') or ''}|{a.get('title') or ''}|{a.get('published') or ''}|"
            f"{a.get('summary') or ''}|{','.join(a.get('tags') or [])}"
        ).encode('utf-8'))
        h.update(b'\n')
    return h.hexdigest()[:16]


# ── API 调用 ───────────────────────────────────────────
def call_api(api_key, model, prompt):
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.4,
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read().decode('utf-8', 'replace')
    obj = json.loads(raw)
    return obj['choices'][0]['message']['content']


# ── 解析与归一化 ───────────────────────────────────────
def _str_list(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out = []
    for x in value:
        if isinstance(x, str):
            s = x.strip()
        elif isinstance(x, dict):
            s = str(x.get('text') or x.get('action') or x.get('point')
                    or x.get('signal') or '').strip()
        else:
            s = ''
        if s:
            out.append(s)
    return out


def _norm_sectors(value):
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append({'name': '', 'point': s})
            continue
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or item.get('industry') or item.get('行业')
                   or item.get('sector') or '').strip()
        point = str(item.get('point') or item.get('points') or item.get('要点')
                    or item.get('detail') or item.get('desc') or '').strip()
        if isinstance(item.get('points'), list):
            point = ' '.join(str(p).strip() for p in item['points'] if str(p).strip())
        if name or point:
            out.append({'name': name, 'point': point})
    return out


def _norm_evidence(ev):
    out = []
    if isinstance(ev, str):
        if ev.strip():
            out.append({'title': ev.strip(), 'link': ''})
    elif isinstance(ev, dict):
        title = str(ev.get('title') or ev.get('name') or ev.get('标题') or '').strip()
        link = str(ev.get('link') or ev.get('url') or ev.get('链接') or '').strip()
        if title or link:
            out.append({'title': title, 'link': link})
    elif isinstance(ev, list):
        for item in ev:
            out.extend(_norm_evidence(item))
    return out


def _extract_json(text):
    t = (text or '').strip()
    if t.startswith('```'):
        t = re.sub(r'^```[a-zA-Z]*\s*', '', t)
        t = re.sub(r'\s*```$', '', t)
    try:
        return json.loads(t)
    except ValueError:
        pass
    m = re.search(r'\{.*\}', t, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None
    return None


def parse_period_content(content, articles):
    data = _extract_json(content)
    if data is None:
        raise ValueError('无法解析模型返回的 JSON')
    if isinstance(data, list):
        raise ValueError('模型返回结构不是对象')
    if isinstance(data, dict) and 'periods' in data:
        data = data.get('periods') or data

    overview = str(data.get('overview') or data.get('综述') or '').strip()
    sectors = _norm_sectors(data.get('sectors') or data.get('行业') or [])
    actions = _str_list(data.get('actions') or data.get('建议') or [])
    signals = _str_list(data.get('signals') or data.get('信号') or [])
    evidence = _norm_evidence(data.get('evidence') or data.get('依据') or [])

    if not (overview or sectors or actions or signals):
        raise ValueError('模型返回的解读为空')
    if not evidence:
        # 模型未给依据时，用本期新闻兜底（保证 evidence 有据可查）
        evidence = [
            {'title': a.get('title') or '', 'link': a.get('link') or ''}
            for a in articles[:8]
        ]
    return {
        'overview': overview,
        'sectors': sectors,
        'actions': actions,
        'signals': signals,
        'evidence': evidence,
    }


# ── 输出 ───────────────────────────────────────────────
def empty_period(config):
    return {
        'range': config['range'],
        'count': 0,
        'overview': '',
        'sectors': [],
        'actions': [],
        'signals': [],
        'evidence': [],
    }


def load_old(out_path):
    if not out_path.exists():
        return {}
    try:
        with open(out_path, 'r', encoding='utf-8') as f:
            old = json.load(f)
        return old if isinstance(old, dict) else {}
    except (ValueError, OSError) as e:
        print(f'ℹ️ 读取旧文件失败（将重新生成）: {e}')
        return {}


def write_outputs(result, out_path, sync):
    text = json.dumps(result, ensure_ascii=False, indent=2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding='utf-8')
    print(f'💾 已保存 {out_path}')
    if sync and out_path.resolve() == OUT_FILE.resolve():
        DOCS_OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        DOCS_OUT_FILE.write_text(text, encoding='utf-8')
        print(f'💾 已同步 {DOCS_OUT_FILE}')


def main():
    parser = argparse.ArgumentParser(description='南海政务 AI 多期聚合解读')
    parser.add_argument('--input', default=str(IN_FILE), help='输入 nanhai.json 路径')
    parser.add_argument('--output', default=str(OUT_FILE), help='输出 ai_digest.json 路径')
    parser.add_argument('--model', default=os.environ.get('AI_MODEL') or DEFAULT_MODEL, help='模型名')
    parser.add_argument('--no-sync', action='store_true', help='不同步到 docs/data/')
    parser.add_argument('--dry-run', action='store_true', help='不调 API，打印每期条数/范围/prompt 头')
    parser.add_argument('--force', action='store_true', help='忽略 hash 缓存，强制调 API')
    parser.add_argument('--now', default='', help='参考日期 YYYY-MM-DD（默认今天，便于测试）')
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f'❌ 找不到输入文件: {in_path}')
        return 1
    with open(in_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    articles = payload.get('articles') or []
    try:
        now = date.fromisoformat(args.now) if args.now else datetime.now().date()
    except ValueError:
        print(f'❌ --now 需为 YYYY-MM-DD：{args.now}')
        return 1

    defs = period_defs(now)
    buckets = bucket_articles(articles, defs)

    print(f'🗓 参考日期 {now.isoformat()}，共 {len(articles)} 条新闻，模型 {args.model}')
    for key in PERIOD_KEYS:
        cfg = defs[key]
        print(f'  · {key:<5} {cfg["range"]:<25} {len(buckets[key]):>3} 条')

    # ── dry-run ────────────────────────────────────────
    if args.dry_run:
        for key in PERIOD_KEYS:
            cfg = defs[key]
            arts = buckets[key]
            print(f'\n—— [{key}] {cfg["label"]} {cfg["range"]} · {len(arts)} 条 ——')
            if not arts:
                print('  （本期无更新，将不调用 API）')
                continue
            prompt = build_prompt(cfg, arts)
            head = prompt[:DRY_RUN_PROMPT_HEAD].replace('\n', ' ⏎ ')
            print(f'  prompt({len(prompt)} 字符) 头部: {head}…')
        print('\nℹ️ dry-run：未调用 API、未写文件')
        return 0

    # ── 无 key 优雅跳过 ────────────────────────────────
    api_key = (os.environ.get('AI_API_KEY') or os.environ.get('DASHSCOPE_API_KEY') or '').strip()
    if not api_key:
        print('⚠️ 未设置 DASHSCOPE_API_KEY，跳过 AI 解读（保留现有文件，不生成/不覆盖）')
        return 0

    out_path = Path(args.output)
    old = load_old(out_path)
    old_periods = old.get('periods') or {}
    old_hashes = old.get('hashes') or {}

    periods = {}
    hashes = {}
    attempted = 0
    produced = 0

    for key in PERIOD_KEYS:
        cfg = defs[key]
        arts = buckets[key]

        if not arts:
            periods[key] = empty_period(cfg)
            hashes[key] = ''
            print(f'· {key}: 本期无更新（跳过）')
            continue

        attempted += 1
        input_hash = compute_hash(key, cfg, arts, args.model)
        prev = old_periods.get(key) if isinstance(old_periods.get(key), dict) else None

        if (prev and prev.get('count') and old_hashes.get(key) == input_hash
                and not args.force):
            periods[key] = prev
            hashes[key] = input_hash
            produced += 1
            print(f'· {key}: 输入未变化，复用既有解读（{len(arts)} 条）')
            continue

        prompt = build_prompt(cfg, arts)
        parsed, last_err = None, None
        for attempt in range(1, RETRIES + 2):
            try:
                content = call_api(api_key, args.model, prompt)
                parsed = parse_period_content(content, arts)
                print(f'· {key}: ✅ 第 {attempt} 次调用成功（{len(arts)} 条）')
                break
            except urllib.error.HTTPError as e:
                body = ''
                try:
                    body = e.read().decode('utf-8', 'replace')[:300]
                except Exception:
                    pass
                last_err = f'HTTP {e.code}: {body or e.reason}'
            except Exception as e:  # noqa: BLE001 —— 网络/解析等统一重试
                last_err = f'{type(e).__name__}: {e}'
            print(f'· {key}: ⚠️ 第 {attempt} 次调用失败: {last_err}')

        if parsed:
            periods[key] = {'range': cfg['range'], 'count': len(arts), **parsed}
            hashes[key] = input_hash
            produced += 1
        elif prev and prev.get('count'):
            periods[key] = prev  # 失败保留旧值、不覆盖该期
            hashes[key] = old_hashes.get(key, '')
            produced += 1
            print(f'· {key}: 调用失败，保留旧解读')
        else:
            periods[key] = empty_period(cfg)
            hashes[key] = ''
            print(f'· {key}: ❌ 调用失败且无旧值，本期留空。原因: {last_err}')

    if attempted and produced == 0:
        print('❌ 全部非空期均失败，保留旧文件不覆盖')
        return 1

    result = {
        'updated': payload.get('updated') or '',
        'model': args.model,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'disclaimer': DISCLAIMER,
        'hashes': hashes,
        'periods': periods,
    }
    write_outputs(result, out_path, not args.no_sync)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
