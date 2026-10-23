#!/usr/bin/env python3
"""build_signals.py — Nanhai signals layer (P0 contract + P1 rule signals).

Reads data/nanhai.json (+ data/analysis.json), applies five rule classes
(rent.level / rent.supply / rent.policy / risk / crypto), and writes a signals
envelope to data/signals.json and docs/data/signals.json.

Design constraints (see CONTRACT.md):
  * stdlib only, no LLM, no third-party deps;
  * additive only — never mutates nanhai.json/analysis.json/page assets;
  * idempotent — generated_at/as_of derive from the source dataset, not wall clock;
  * every signal is schema-validated against src/contracts/signals-1.0.0.schema.json
    before anything is written; on failure it errors out and writes nothing;
  * actions are human-in-the-loop suggestions only (requires_human=true);
    no automated pricing / ordering / enforcement.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "nanhai.json"
ANALYSIS_PATH = ROOT / "data" / "analysis.json"
SCHEMA_PATH = ROOT / "src" / "contracts" / "signals-1.0.0.schema.json"
OUT_PATHS = [ROOT / "data" / "signals.json", ROOT / "docs" / "data" / "signals.json"]

SCHEMA_VERSION = "1.0.0"
GENERATOR = {"method": "rule", "name": "build_signals", "version": "1.0.0", "model": None}
CONFIDENCE_CAP = 0.75
MAX_SIGNALS = 10
MIN_SIGNALS = 1

DISTRICT = "佛山市南海区"

# 南海区 7 个镇街（找不到则回落到区级）
TOWNS = [
    ("桂城", "guicheng", "桂城街道"),
    ("大沥", "dali", "大沥镇"),
    ("里水", "lishui", "里水镇"),
    ("狮山", "shishan", "狮山镇"),
    ("西樵", "xiqiao", "西樵镇"),
    ("丹灶", "danzao", "丹灶镇"),
    ("九江", "jiujiang", "九江镇"),
]

RENT_SUPPLY_RE = re.compile(r"公租房|保障房|房源采购|招标|中标|配租")
RENT_POLICY_RE = re.compile(r"租赁补贴|租金指导价|公租房|保障性租赁住房|租金标准")
RISK_RE = re.compile(r"事故|火灾|台风|暴雨|预警|防汛|安全|交通管制")
# "strong" risk terms boost relevance over generic 安全 (e.g. 网络安全/食品安全).
RISK_STRONG_RE = re.compile(r"事故|火灾|台风|暴雨|预警|防汛|森林防火|消防|生产安全|交通管制|应急")

# Rule 5: crypto — surface Nanhai news that touches crypto/blockchain/digital
# currency, linking it to the gate (crypto auto-trading) audience as ALERT ONLY.
CRYPTO_RE = re.compile(
    r"加密|加密货币|区块链|数字货币|数字人民币|虚拟货币|稳定币|Web3|web3|交易所|"
    r"挖矿|矿业|链上|NFT|央行数字|CBDC|币圈|加密资产|数字资产|代币"
)
# Tightening/risk framing => negative for crypto trading; tailwind framing => positive.
CRYPTO_NEG_RE = re.compile(
    r"监管|整治|打击|禁止|取缔|风险|诈骗|骗局|洗钱|非法|处罚|查处|冻结|清退|"
    r"限制|警示|辟谣|投诉|崩盘|跑路"
)
CRYPTO_POS_RE = re.compile(
    r"数字人民币|CBDC|试点|推广|应用|支持|鼓励|创新|开放|合法|合规|牌照|落地|合作|上线"
)
CRYPTO_MAX = 3

# PII: collapse "<姓名>等N户/人" to "某等N户/人"; never emit personal names.
PII_NAME_COUNT_RE = re.compile(r"([\u4e00-\u9fa5]{2,4})等(\d+\s*[户人名])")
PII_HONORIFIC_RE = re.compile(r"[\u4e00-\u9fa5]{2,4}(先生|女士|小姐)")


def parse_dt(value):
    """Parse a date or RFC3339 timestamp into an aware UTC datetime."""
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fmt_dt(dt):
    return dt.astimezone(timezone.utc).isoformat()


def redact(text):
    if not text:
        return ""
    text = PII_NAME_COUNT_RE.sub(r"某等\2", text)
    text = PII_HONORIFIC_RE.sub("某", text)
    return text


def clip(text, limit=120):
    text = re.sub(r"\s+", " ", redact(text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def blob(article):
    parts = [article.get("title", ""), article.get("summary", "")]
    parts.extend(article.get("rent_snippets") or [])
    return " ".join(p for p in parts if p)


def detect_region(text):
    towns = []
    codes = []
    for cname, code, full in TOWNS:
        if cname in text:
            towns.append(full)
            codes.append(code)
    if towns:
        return {"district": DISTRICT, "towns": towns, "match_level": "town"}, codes
    return {"district": DISTRICT, "towns": [], "match_level": "district"}, codes


def geo_token(codes):
    return codes[0] if codes else "nanhai"


def source_reliability(source):
    if re.search(r"政府|镇|街道|局|委员会|中心|办公室|党委|管委会|住建|自然资源|市场监管|交易|税务|财政|公共资源", source or ""):
        return 0.9
    return 0.8


def recency_factor(age_days):
    if age_days <= 90:
        return 1.0
    if age_days <= 365:
        return 0.8
    if age_days <= 730:
        return 0.5
    return 0.3


def compute_confidence(source, evidence_count, age_days, extraction_quality):
    value = (
        0.40 * source_reliability(source)
        + 0.25 * min(1.0, 0.6 + 0.2 * evidence_count)
        + 0.20 * recency_factor(age_days)
        + 0.15 * extraction_quality
    )
    return round(min(value, CONFIDENCE_CAP), 2)


STALE_DAYS = {"rent_level": 365, "rent_supply": 180, "rent_policy": 365, "risk": 90, "crypto": 180}
VALIDITY_DAYS = {"rent_level": 365, "rent_supply": 180, "rent_policy": 365, "risk": 90, "crypto": 180}


def compute_status(scope, age_days, valid_until, as_of):
    if age_days > STALE_DAYS[scope]:
        return "stale"
    if as_of > valid_until:
        return "expired"
    return "active"


def make_signal(scope, title, region, industries, indicator, change, impact, confidence,
                evidence, audience, actions, published_dt, as_of, geo, slug):
    valid_from = published_dt
    valid_until = published_dt + timedelta(days=VALIDITY_DAYS[scope])
    age_days = max(0, (as_of - published_dt).days)
    status = compute_status(scope, age_days, valid_until, as_of)
    signal_id = "sig_{}_{}_{}_{}".format(
        scope, geo, slug, published_dt.strftime("%Y%m%d")
    )
    return {
        "signal_id": signal_id,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "title": title,
        "scope": scope,
        "region": region,
        "industries": industries,
        "indicator": indicator,
        "change": change,
        "impact": impact,
        "confidence": confidence,
        "evidence": evidence,
        "audience": audience,
        "actions": actions,
        "valid_from": fmt_dt(valid_from),
        "valid_until": fmt_dt(valid_until),
        "last_confirmed_at": fmt_dt(published_dt),
        "generated_at": fmt_dt(as_of),
        "generator": dict(GENERATOR),
        "review": {"status": "auto"},
    }


def evidence_entry(doc_id, title, url, published_dt, quote):
    return {
        "doc_id": doc_id,
        "title": title,
        "url": url,
        "published_at": fmt_dt(published_dt),
        "quote": clip(quote),
    }


def action(audience, type_, urgency, step, params):
    return {
        "audience": audience,
        "type": type_,
        "urgency": urgency,
        "suggested_step": step,
        "parameters": params,
        "requires_human": True,
    }


# ---------------------------------------------------------------------------
# Rule 1: rent.level — numeric rent level from analysis price_series / snippets
# ---------------------------------------------------------------------------

RENT_VALUE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*元\s*/?\s*(?:平方米|㎡|m2|㎡·月)")


def rule_rent_level(nanhai, analysis, as_of):
    signals = []
    by_link = {a.get("link"): a for a in nanhai.get("articles", [])}
    series = analysis.get("price_series") or []

    picked = None
    for item in series:
        if item.get("value") is None:
            continue
        art = by_link.get(item.get("link"))
        if not art:
            continue
        picked = (item, art)
        break

    if picked is None:
        for art in nanhai.get("articles", []):
            for snippet in art.get("rent_snippets") or []:
                match = RENT_VALUE_RE.search(snippet)
                if match:
                    picked = ({"value": float(match.group(1)), "unit": "元/㎡·月",
                               "period": art.get("published", ""), "context": snippet,
                               "title": art.get("title", ""), "link": art.get("link", "")}, art)
                    break
            if picked:
                break

    if picked is None:
        return signals

    item, art = picked
    published_dt = parse_dt(art.get("published") or item.get("period"))
    if not published_dt:
        return signals
    text = blob(art) + " " + str(item.get("context", ""))
    region, codes = detect_region(text)
    quote = item.get("context") or blob(art)
    age_days = max(0, (as_of - published_dt).days)
    conf = compute_confidence(art.get("source", ""), 1, age_days, 1.0)
    unit = item.get("unit") or "元/㎡·月"
    if "元" not in unit:
        unit = "元/" + unit
    signals.append(make_signal(
        scope="rent_level",
        title=(item.get("title") or art.get("title") or "南海住房租金水平"),
        region=region,
        industries=["housing_rental"],
        indicator={
            "code": "rent.market_avg",
            "name": "住房平均租金水平",
            "value": item.get("value"),
            "unit": unit,
            "period": item.get("period") or art.get("published"),
            "dimension": "level",
        },
        change={
            "abs": None, "pct": None, "yoy": None, "mom": None,
            "method": "level_observation",
            "direction": "flat",
            "baseline": None,
        },
        impact={
            "direction": "neutral",
            "by_audience": {"souse": "neutral", "gate": "neutral"},
            "horizon": "medium",
            "mechanism": "区域住房平均租金基准，用于校准挂牌价/补贴测算的参照系",
            "affected": ["souse", "gate"],
        },
        confidence=conf,
        evidence=[evidence_entry(art.get("id", item.get("link", "")), art.get("title", item.get("title", "")),
                                art.get("link", item.get("link", "")), published_dt, quote)],
        audience=["souse"],
        actions=[action("souse", "review", "medium",
                        "人工复核该租金基准是否仍适用于当前挂牌/补贴测算，勿以旧价直接定价",
                        {"indicator": "rent.market_avg", "period": item.get("period")})],
        published_dt=published_dt,
        as_of=as_of,
        geo=geo_token(codes),
        slug=art.get("id", "rentlevel"),
    ))
    return signals


# ---------------------------------------------------------------------------
# Rules 2-4: keyword-driven supply / policy / risk
# ---------------------------------------------------------------------------

def norm_key(title):
    return re.sub(r"[（(].*?[)）]", "", title or "").strip()


def _select(candidates, limit):
    chosen = []
    seen = set()
    for art in candidates:
        key = norm_key(art.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        chosen.append(art)
        if len(chosen) >= limit:
            break
    return chosen


SCOPE_META = {
    "rent_supply": {
        "industries": ["public_housing", "housing_rental"],
        "audience": ["souse"],
        "indicator": ("housing.public_rental_supply", "公租房/保障房房源供给", "supply"),
        "impact_direction": "positive",
        "by_audience": {"souse": "positive"},
        "horizon": "medium",
        "mechanism": "公租房房源采购/配租推进增加可租房源，缓解供给约束，利于定价与配额管理",
        "affected": ["souse"],
        "action": ("observe", "low",
                   "关注房源采购/配租进展，评估区域供给变化对定价与配额的边际影响",
                   {"indicator": "housing.public_rental_supply"}),
    },
    "rent_policy": {
        "industries": ["public_housing", "social_security"],
        "audience": ["souse"],
        "indicator": ("housing.rent_policy", "住房租赁/补贴政策", "policy"),
        "impact_direction": "neutral",
        "by_audience": {"souse": "neutral", "gate": "neutral"},
        "horizon": "medium",
        "mechanism": "租赁补贴/租金标准政策调整，改变补贴对象与定价约束，需同步核对定价口径",
        "affected": ["souse", "gate"],
        "action": ("verify", "medium",
                   "核对补贴名单/政策口径，确认是否需要更新定价参数与配额",
                   {"indicator": "housing.rent_policy"}),
    },
    "risk": {
        "industries": ["safety"],
        "audience": ["gate", "souse"],
        "indicator": ("risk.safety_event", "安全/灾害风险", "risk"),
        "impact_direction": "negative",
        "by_audience": {"gate": "negative", "souse": "negative"},
        "horizon": "short",
        "mechanism": "安全/灾害类事件可能影响区域运营与投放节奏，需人工核实并纳入值班关注",
        "affected": ["gate", "souse"],
        "action": ("alert", "medium",
                   "人工核实风险事件并与值班口径对齐；仅提示，不自动触发任何动作",
                   {"indicator": "risk.safety_event"}),
    },
}


def pick_quote(article):
    for snippet in article.get("rent_snippets") or []:
        if snippet and not snippet.strip().lower().startswith("http"):
            return snippet
    summary = article.get("summary") or ""
    if summary and not summary.strip().lower().startswith("http"):
        return summary
    return article.get("title", "")


def rule_keyword(scope, candidates, as_of, extraction_quality=0.7):
    signals = []
    meta = SCOPE_META[scope]
    for art in candidates:
        published_dt = parse_dt(art.get("published"))
        if not published_dt:
            continue
        text = blob(art)
        region, codes = detect_region(text)
        age_days = max(0, (as_of - published_dt).days)
        conf = compute_confidence(art.get("source", ""), 1, age_days, extraction_quality)
        code, name, dimension = meta["indicator"]
        quote = pick_quote(art)
        signals.append(make_signal(
            scope=scope,
            title=art.get("title", "")[:120],
            region=region,
            industries=list(meta["industries"]),
            indicator={
                "code": code,
                "name": name,
                "value": None,
                "unit": None,
                "period": art.get("published", "")[:7],
                "dimension": dimension,
            },
            change={
                "abs": None, "pct": None, "yoy": None, "mom": None,
                "method": "keyword_rule",
                "direction": "unknown",
                "baseline": None,
            },
            impact={
                "direction": meta["impact_direction"],
                "by_audience": dict(meta["by_audience"]),
                "horizon": meta["horizon"],
                "mechanism": meta["mechanism"],
                "affected": list(meta["affected"]),
            },
            confidence=conf,
            evidence=[evidence_entry(art.get("id", art.get("link", "")), art.get("title", ""),
                                    art.get("link", ""), published_dt, quote)],
            audience=list(meta["audience"]),
            actions=[action(meta["audience"][0], *meta["action"])],
            published_dt=published_dt,
            as_of=as_of,
            geo=geo_token(codes),
            slug=art.get("id", scope),
        ))
    return signals


# ---------------------------------------------------------------------------
# Rule 5: crypto — link Nanhai news to gate (crypto auto-trading), alert only
# ---------------------------------------------------------------------------

def crypto_blob(article):
    """Title + summary + tags, the fields the crypto rule is allowed to match."""
    parts = [article.get("title", ""), article.get("summary", "")]
    parts.extend(article.get("tags") or [])
    return " ".join(p for p in parts if p)


def crypto_direction(text):
    """Effect on gate: tightening/risk -> negative, tailwind -> positive, else neutral."""
    if CRYPTO_NEG_RE.search(text):
        return "negative"
    if CRYPTO_POS_RE.search(text):
        return "positive"
    return "neutral"


def rule_crypto(candidates, as_of, extraction_quality=0.7):
    signals = []
    for art in candidates:
        published_dt = parse_dt(art.get("published"))
        if not published_dt:
            continue
        text = crypto_blob(art)
        region, codes = detect_region(blob(art))
        direction = crypto_direction(text)
        age_days = max(0, (as_of - published_dt).days)
        conf = compute_confidence(art.get("source", ""), 1, age_days, extraction_quality)
        quote = pick_quote(art)
        signals.append(make_signal(
            scope="crypto",
            title=art.get("title", "")[:120],
            region=region,
            industries=["crypto"],
            indicator={
                "code": "crypto.nanhai_news_link",
                "name": "南海政务动态中的加密/区块链关联",
                "value": None,
                "unit": None,
                "period": art.get("published", "")[:7],
                "dimension": "linkage",
            },
            change={
                "abs": None, "pct": None, "yoy": None, "mom": None,
                "method": "keyword_rule",
                "direction": "unknown",
                "baseline": None,
            },
            impact={
                "direction": direction,
                "by_audience": {"gate": direction},
                "horizon": "short",
                "mechanism": ("南海政务动态出现加密/区块链/数字货币相关表述，"
                              "构成与 gate 加密币交易的信息面关联点；仅作提示，不含任何交易指令"),
                "affected": ["gate"],
            },
            confidence=conf,
            evidence=[evidence_entry(art.get("id", art.get("link", "")), art.get("title", ""),
                                    art.get("link", ""), published_dt, quote)],
            audience=["gate"],
            actions=[action("gate", "alert_only", "low",
                            "人工查看该南海新闻与加密币交易的相关性；仅作提醒，不自动下单/调仓",
                            {"indicator": "crypto.nanhai_news_link", "require_human_review": True})],
            published_dt=published_dt,
            as_of=as_of,
            geo=geo_token(codes),
            slug=art.get("id", "crypto"),
        ))
    return signals


def build_signals(nanhai, analysis, as_of):
    articles = nanhai.get("articles", [])
    signals = []

    signals.extend(rule_rent_level(nanhai, analysis, as_of))

    supply_candidate = sorted(
        [a for a in articles if RENT_SUPPLY_RE.search(blob(a))],
        key=lambda a: (a.get("published", ""), -a.get("priority", 9)),
        reverse=True,
    )
    supply = _select(supply_candidate, 2)
    used = {a.get("id") for a in supply}
    signals.extend(rule_keyword("rent_supply", supply, as_of))

    policy_candidate = [a for a in articles
                        if RENT_POLICY_RE.search(blob(a)) and a.get("id") not in used]
    policy_candidate.sort(key=lambda a: a.get("published", ""), reverse=True)
    policy_candidate.sort(key=lambda a: 0 if re.search(r"租金水平|指导价|实施意见|实施细则", a.get("title", "")) else 1)
    policy = _select(policy_candidate, 2)
    signals.extend(rule_keyword("rent_policy", policy, as_of))

    risk_candidate = sorted(
        [a for a in articles if RISK_RE.search(blob(a))],
        key=lambda a: (len(RISK_STRONG_RE.findall(blob(a))) > 0,
                       len(RISK_STRONG_RE.findall(blob(a))),
                       a.get("published", "")),
        reverse=True,
    )
    risk = _select(risk_candidate, 2)
    signals.extend(rule_keyword("risk", risk, as_of))

    crypto_candidate = sorted(
        [a for a in articles if CRYPTO_RE.search(crypto_blob(a))],
        key=lambda a: a.get("published", ""),
        reverse=True,
    )
    crypto = _select(crypto_candidate, CRYPTO_MAX)
    signals.extend(rule_crypto(crypto, as_of))

    signals.sort(key=lambda s: (s["scope"], s["signal_id"]))
    return signals


# ---------------------------------------------------------------------------
# Minimal draft-07 schema validator (stdlib only)
# ---------------------------------------------------------------------------

TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value, type_name):
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    expected = TYPE_MAP.get(type_name)
    return expected is not None and isinstance(value, expected)


def validate(instance, schema, root, path, errors):
    if "$ref" in schema:
        ref = schema["$ref"]
        target = root
        for part in ref.lstrip("#/").split("/"):
            target = target[part]
        validate(instance, target, root, path, errors)
        return

    if "type" in schema:
        types = schema["type"]
        types = types if isinstance(types, list) else [types]
        if not any(_type_ok(instance, t) for t in types):
            errors.append(f"{path}: 类型应为 {types}，实际 {type(instance).__name__}")
            return

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: 应为常量 {schema['const']!r}，实际 {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: 值 {instance!r} 不在枚举 {schema['enum']}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: 长度 {len(instance)} < minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: 不匹配 pattern {schema['pattern']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} > maximum {schema['maximum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: 元素数 {len(instance)} < minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: 元素数 {len(instance)} > maxItems {schema['maxItems']}")
        if "items" in schema:
            for i, item in enumerate(instance):
                validate(item, schema["items"], root, f"{path}[{i}]", errors)

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: 缺少必填字段 '{key}'")
        props = schema.get("properties", {})
        for key, value in instance.items():
            if key in props:
                validate(value, props[key], root, f"{path}.{key}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: 存在未定义字段 '{key}'")
            elif isinstance(schema.get("additionalProperties"), dict):
                validate(value, schema["additionalProperties"], root, f"{path}.{key}", errors)


def validate_envelope(envelope, schema):
    errors = []
    validate(envelope, schema, schema, "$", errors)

    if envelope.get("count") != len(envelope.get("signals", [])):
        errors.append(f"$.count={envelope.get('count')} != len(signals)={len(envelope.get('signals', []))}")

    for idx, sig in enumerate(envelope.get("signals", [])):
        vf, vu = parse_dt(sig.get("valid_from")), parse_dt(sig.get("valid_until"))
        if vf and vu and not vu > vf:
            errors.append(f"$.signals[{idx}].valid_until ({sig.get('valid_until')}) 必须晚于 valid_from ({sig.get('valid_from')})")
        if not sig.get("evidence"):
            errors.append(f"$.signals[{idx}].evidence 不能为空")
        if not sig.get("actions"):
            errors.append(f"$.signals[{idx}].actions 不能为空")
        for act in sig.get("actions", []):
            if act.get("requires_human") is not True:
                errors.append(f"$.signals[{idx}].actions: requires_human 必须为 true")
    return errors


# ---------------------------------------------------------------------------

def build_envelope(nanhai, analysis):
    as_of = parse_dt(nanhai.get("updated")) or datetime.now(timezone.utc)
    signals = build_signals(nanhai, analysis, as_of)
    dataset_version = "nanhai-{}-{}".format(
        as_of.strftime("%Y-%m-%d"), nanhai.get("total", len(nanhai.get("articles", [])))
    )
    warnings = []
    if not signals:
        warnings.append("未抽取到任何规则信号（输入数据可能为空）")
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "generated_at": fmt_dt(as_of),
        "as_of": fmt_dt(as_of),
        "region": DISTRICT,
        "count": len(signals),
        "signals": signals,
        "warnings": warnings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build Nanhai signals layer (rule-based, stdlib only)")
    parser.add_argument("--dry-run", action="store_true", help="只打印将生成的信号，不写文件")
    args = parser.parse_args(argv)

    if not DATA_PATH.exists():
        print(f"错误：找不到输入 {DATA_PATH}", file=sys.stderr)
        return 1
    nanhai = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8")) if ANALYSIS_PATH.exists() else {}

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    envelope = build_envelope(nanhai, analysis)

    errors = validate_envelope(envelope, schema)
    if errors:
        print("schema 校验失败，未写入任何文件：", file=sys.stderr)
        for err in errors:
            print("  - " + err, file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"[dry-run] as_of={envelope['as_of']} dataset_version={envelope['dataset_version']}")
        print(f"[dry-run] 将生成 {envelope['count']} 条信号（schema {envelope['schema_version']}，校验通过）")
        for sig in envelope["signals"]:
            print("  {} | {} | {} | conf {} | aud {} | until {} | {}".format(
                sig["signal_id"], sig["scope"], sig["status"], sig["confidence"],
                ",".join(sig["audience"]), sig["valid_until"][:10], sig["title"][:40]))
        for warning in envelope["warnings"]:
            print("  [warn] " + warning)
        return 0

    text = json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    for path in OUT_PATHS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(f"写入 {len(OUT_PATHS)} 个文件：count={envelope['count']} schema={envelope['schema_version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
