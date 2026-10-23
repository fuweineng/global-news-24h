#!/usr/bin/env python3
"""审计新闻数据的中立化覆盖率与中立度残留。

读取 data/news.json（主）、data/nanhai.json、data/signals.json 与
docs/index.html 的页脚声明，输出 data/audit.json。

只依赖 Python 标准库。退出码恒为 0：审计失败不等于脚本失败。
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
NEWS_PATH = DATA_DIR / "news.json"
NANHAI_PATH = DATA_DIR / "nanhai.json"
SIGNALS_PATH = DATA_DIR / "signals.json"
AUDIT_PATH = DATA_DIR / "audit.json"
DOCS_INDEX_PATH = BASE_DIR / "docs" / "index.html"

SCHEMA_VERSION = "1.0.0"

FALLBACK_CLAIMED = [
    "Reuters",
    "BBC",
    "Bloomberg",
    "AP",
    "Al Jazeera",
    "NHK",
    "SCMP",
]

KNOWN_DEAD_SOURCES = [
    "Reuters",
    "AP News",
    "Bloomberg",
    "ESPN",
    "NHK World",
    "Nikkei Asia",
    "Scientific American",
]

EMOTION_PATTERN = re.compile(
    r"震惊|惊呆|崩了|炸了|疯了|太可怕|不敢信|必看|炸裂|毁掉|摧毁|谁在乎|没人管|竟然|居然"
)
IRONY_PATTERN = re.compile(
    r"当然|呵呵|哦，|谁在乎|关我何事|又能怎样|还不是"
)

STATUS_RANK = {"pass": 0, "warn": 1, "fail": 2}


def read_json(path: Path):
    """返回 (data, error)。缺失或损坏时 data 为 None，error 说明原因。"""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh), None
    except FileNotFoundError:
        return None, "缺少 %s" % path.relative_to(BASE_DIR).as_posix()
    except (OSError, ValueError) as exc:
        return None, "%s 读取/解析失败: %s" % (
            path.relative_to(BASE_DIR).as_posix(),
            exc,
        )


def clean(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def normalize_source(name: str) -> str:
    """归一化来源名，使 AP / AP News、NHK / NHK World 视为同一家。"""
    text = clean(name).lower()
    text = re.sub(r"\bthe\s+", "", text)
    text = text.replace(" news", "").replace(" world", "")
    return re.sub(r"[^a-z0-9]", "", text)


def make_check(check_id, label, status, threshold, observed, metric, detail):
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "threshold": threshold,
        "observed": observed,
        "metric": metric,
        "detail": detail,
    }


def rate_status(rate: float, pass_at: float, warn_at: float) -> str:
    if rate >= pass_at:
        return "pass"
    if rate >= warn_at:
        return "warn"
    return "fail"


def load_articles(news):
    """从 news.json 数据中取出合法 article 列表。"""
    if not isinstance(news, dict):
        return None
    articles = news.get("articles")
    if not isinstance(articles, list):
        return None
    return [item for item in articles if isinstance(item, dict)]


def is_processed(article, source_key, target_key) -> bool:
    return clean(article.get(target_key)) != clean(article.get(source_key))


def build_coverage_check(check_id, label, articles, source_key, target_key, missing_detail):
    if not articles:
        return make_check(
            check_id,
            label,
            "warn",
            ">= 0.90",
            0,
            {"processed": 0, "total": 0},
            missing_detail,
        )

    total = len(articles)
    processed = sum(1 for a in articles if is_processed(a, source_key, target_key))
    unprocessed = total - processed
    rate = round(processed / total, 4)
    status = rate_status(rate, 0.90, 0.50)
    kind = "标题" if source_key == "title" else "摘要"
    detail = "%d/%d 条%s与英文原文完全相同，未走中立化" % (
        unprocessed,
        total,
        kind,
    )
    return make_check(
        check_id,
        label,
        status,
        ">= 0.90",
        rate,
        {"processed": processed, "total": total},
        detail,
    )


def build_by_source_check(articles, global_rate, missing_detail):
    check_id = "coverage.by_source"
    label = "按来源覆盖率"
    threshold = "0% 源占比 < 0.50"

    if articles is None or not articles:
        return (
            make_check(
                check_id,
                label,
                "warn",
                threshold,
                0,
                {"zero_rate_sources": 0, "sources_total": 0},
                missing_detail,
            ),
            [],
        )

    totals = Counter(a.get("source") or "未知来源" for a in articles)
    processed_by_source = Counter(
        a.get("source") or "未知来源"
        for a in articles
        if is_processed(a, "title", "zh_title")
    )

    by_source = []
    for source, total in totals.items():
        processed = processed_by_source.get(source, 0)
        by_source.append(
            {
                "source": source,
                "total": total,
                "processed": processed,
                "rate": round(processed / total, 4),
            }
        )
    by_source.sort(key=lambda row: (-row["total"], row["source"]))

    zero_sources = [row["source"] for row in by_source if row["rate"] == 0]
    sources_total = len(by_source)
    zero_count = len(zero_sources)

    if zero_count == 0:
        status = "pass"
        detail = "全部 %d 个来源均有中立化产出" % sources_total
    elif zero_count * 2 < sources_total:
        status = "warn"
        detail = "%d 个源加工率为 0（共 %d 个源）：%s" % (
            zero_count,
            sources_total,
            "、".join(zero_sources),
        )
    else:
        status = "fail"
        detail = "%d 个源加工率为 0（共 %d 个源）：%s" % (
            zero_count,
            sources_total,
            "、".join(zero_sources),
        )

    return (
        make_check(
            check_id,
            label,
            status,
            threshold,
            global_rate,
            {"zero_rate_sources": zero_count, "sources_total": sources_total},
            detail,
        ),
        by_source,
    )


def build_neutrality_check(articles, missing_detail):
    check_id = "neutrality"
    label = "中立度残留"
    threshold = "<= 0.05"

    if articles is None or not articles:
        return (
            make_check(
                check_id,
                label,
                "warn",
                threshold,
                0,
                {"processed": 0, "hits": 0},
                missing_detail,
            ),
            [],
        )

    processed = [a for a in articles if is_processed(a, "title", "zh_title")]
    if not processed:
        return (
            make_check(
                check_id,
                label,
                "warn",
                threshold,
                0,
                {"processed": 0, "hits": 0},
                "没有已加工的标题，无法评估情绪/反讽残留",
            ),
            [],
        )

    hits = []
    hit_articles = set()
    rules = (("emotion", EMOTION_PATTERN), ("irony", IRONY_PATTERN))

    for article in processed:
        zh_title = clean(article.get("zh_title"))
        for rule_name, pattern in rules:
            match = pattern.search(zh_title)
            if not match:
                continue
            hit_articles.add(id(article))
            hits.append(
                {
                    "source": article.get("source") or "",
                    "title": article.get("title") or "",
                    "zh_title": article.get("zh_title") or "",
                    "rule": rule_name,
                    "matched": match.group(0),
                }
            )

    processed_count = len(processed)
    hit_count = len(hit_articles)
    rate = round(hit_count / processed_count, 4)
    if rate <= 0.05:
        status = "pass"
    elif rate <= 0.15:
        status = "warn"
    else:
        status = "fail"

    detail = "已加工 %d 条中 %d 条仍含情绪/反讽残留（%.1f%%）" % (
        processed_count,
        hit_count,
        rate * 100,
    )
    return (
        make_check(
            check_id,
            label,
            status,
            threshold,
            rate,
            {"processed": processed_count, "hits": hit_count},
            detail,
        ),
        hits,
    )


def parse_footer_claims():
    try:
        text = DOCS_INDEX_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return list(FALLBACK_CLAIMED)

    match = re.search(r"数据来源[:：]\s*([^<\n]*)", text)
    if not match:
        return list(FALLBACK_CLAIMED)

    claimed = []
    for part in match.group(1).split(" · "):
        name = part.strip()
        if not name or name == "更多":
            continue
        claimed.append(name)
    return claimed or list(FALLBACK_CLAIMED)


def build_footer_claims(articles):
    claimed = parse_footer_claims()

    counts = Counter()
    if articles:
        counts = Counter(a.get("source") or "" for a in articles)
        counts.pop("", None)

    actually_producing = [
        source
        for source, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    producing_norms = {normalize_source(source) for source in actually_producing}

    false_claims = [
        name for name in claimed if normalize_source(name) not in producing_norms
    ]
    return claimed, actually_producing, false_claims


def build_dead_sources(articles):
    producing_norms = set()
    if articles:
        producing_norms = {
            normalize_source(a.get("source") or "") for a in articles
        }
        producing_norms.discard("")
    return [
        name
        for name in KNOWN_DEAD_SOURCES
        if normalize_source(name) not in producing_norms
    ]


def worst_status(checks) -> str:
    result = "pass"
    for check in checks:
        if STATUS_RANK[check["status"]] > STATUS_RANK[result]:
            result = check["status"]
    return result


def generated_at() -> str:
    override = os.environ.get("AUDIT_GENERATED_AT")
    if override:
        return override
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    news, news_error = read_json(NEWS_PATH)
    # 这两个文件当前不直接参与四项检查，但按职责要求做一次容错读取，
    # 缺失/损坏不会影响审计输出，也不会让脚本失败。
    read_json(NANHAI_PATH)
    read_json(SIGNALS_PATH)

    articles = load_articles(news)
    news_detail = news_error or "data/news.json 中没有可审计的 articles"

    title_check = build_coverage_check(
        "coverage.title",
        "标题中立化覆盖率",
        articles,
        "title",
        "zh_title",
        news_detail,
    )
    summary_check = build_coverage_check(
        "coverage.summary",
        "摘要中立化覆盖率",
        articles,
        "summary",
        "zh_summary",
        news_detail,
    )

    global_title_rate = title_check["observed"]
    by_source_check, by_source = build_by_source_check(
        articles, global_title_rate, news_detail
    )
    neutrality_check, neutrality_hits = build_neutrality_check(
        articles, news_detail
    )

    checks = [title_check, summary_check, by_source_check, neutrality_check]
    passed = sum(1 for check in checks if check["status"] == "pass")

    claimed, actually_producing, false_claims = build_footer_claims(articles)
    dead_sources = build_dead_sources(articles)

    source_updated = None
    if isinstance(news, dict):
        source_updated = news.get("updated")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at(),
        "source_updated": source_updated,
        "summary": {
            "status": worst_status(checks),
            "checks_passed": passed,
            "checks_total": len(checks),
        },
        "checks": checks,
        "by_source": by_source,
        "neutrality_hits": neutrality_hits,
        "dead_sources": dead_sources,
        "footer_claims": {
            "claimed": claimed,
            "actually_producing": actually_producing,
            "false_claims": false_claims,
        },
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
