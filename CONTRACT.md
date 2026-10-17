# Signals 层契约 (v1.0.0)

本项目分四层：`raw → normalized → signals → digests`。本文件冻结 **signals 层** 的对外契约，供下游 `gate`/`souse` 前置消费。schema 见 [`src/contracts/signals-1.0.0.schema.json`](src/contracts/signals-1.0.0.schema.json)（JSON Schema draft-07，纯标准库可校验）。

- 产物：`data/signals.json`（envelope），同步 `docs/data/signals.json`。
- 生成器：`src/build_signals.py`（纯规则，无 LLM）。
- 兼容性：新增字段属 **minor**，可后向兼容；删除/改语义属 **major**，需升 `schema_version`。
- 只增不改：signals 层是**派生视图**，不改动 `nanhai.json`/`analysis.json`/`ai_digest.json` 及现有页面。

## 1. Envelope

```jsonc
{
  "schema_version": "1.0.0",
  "dataset_version": "nanhai-2026-10-17-149",  // 派生自上游数据版本，非 schema 版本
  "generated_at": "2026-10-17T10:59:10+00:00",
  "as_of": "2026-10-17T10:59:10+00:00",        // 时效评估基准「now」
  "region": "佛山市南海区",
  "count": 7,                                   // == len(signals)
  "signals": [ /* Signal[] */ ],
  "warnings": []                                // 非致命抽取/校验提示
}
```

`as_of` 是**时效语义里的「现在」**。规则生成器为可复现（幂等），用上游 `nanhai.json.updated` 作为 `as_of`/`generated_at`，而非墙钟时间。

## 2. Signal 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `signal_id` | ✅ | 稳定 id：`sig_{scope}_{geo}_{slug}_{date}`，同输入同输出 |
| `schema_version` | ✅ | 恒为 `1.0.0` |
| `status` | ✅ | `draft\|active\|stale\|expired\|superseded\|rejected` |
| `title` | ✅ | 人类可读标题 |
| `scope` | ✅ | `rent_level\|rent_change\|rent_supply\|rent_policy\|rent_demand\|industry\|macro\|risk\|sentiment\|weather\|traffic` |
| `region` | ✅ | `{district, towns[], match_level}`；`match_level ∈ district\|town\|street\|unknown` |
| `industries` | ✅ | 固定枚举，≥1；如 `housing_rental/public_housing/social_security/safety/...` |
| `indicator` | ✅ | `{code,name,value,unit,period,dimension}`；定性信号可 `value/unit/period=null` |
| `change` | ✅ | `{abs,pct,yoy,mom,method,direction,baseline}`；`direction ∈ up\|down\|flat\|unknown` |
| `impact` | ✅ | `{direction,by_audience,horizon,mechanism,affected}`；`direction ∈ positive\|negative\|neutral\|mixed\|unknown` |
| `confidence` | ✅ | `0..1` |
| `evidence` | ✅ **非空** | `[{doc_id,title,url,published_at,quote}]`，`quote` 为脱敏原文摘录 |
| `audience` | ✅ | `souse\|gate\|public` 子集，≥1 |
| `actions` | ✅ **非空** | `[{audience,type,urgency,suggested_step,parameters,requires_human}]` |
| `valid_from` / `valid_until` | ✅ | RFC3339，`valid_until > valid_from` |
| `last_confirmed_at` | ✅ | 最新证据的观测时间 |
| `generated_at` | ✅ | 本条生成时间 |
| `generator` | ✅ | `{method:rule\|llm\|hybrid, name, version, model}`；纯规则 `model=null` |
| `review` | ✅ | `{status: auto\|pending\|approved\|rejected}` |

`evidence` 与 `actions` **必填非空**：无证据不成信号；无人工动作建议的下游消费不算闭环。

## 3. 方向语义（最容易混，务必区分）

- `change.direction` = **指标/事实本身**的涨跌：`up / down / flat / unknown`。例：租金 22 元 → 24 元 = `up`。
- `impact.direction` = **对下游对象的好坏**：`positive / negative / neutral / mixed / unknown`。例：租金上涨对房东(`souse` 供给侧)偏 `positive`，对租客偏 `negative`。

**二者不可混**。「指标涨」不等于「事情好」。允许 `change.direction=up` + `impact.direction=negative`（或反之）。`impact.by_audience` 可按 `souse/gate/public` 分别给出方向。

## 4. 时效（validity）规则

- `valid_from` = 证据发布日期（`published_at`）；`valid_until` 按 scope 给窗口：
  - `rent_level` / `rent_policy`：`valid_from + 365d`（价格/政策年度性）。
  - `rent_supply`：`valid_from + 180d`（采购/配租窗口）。
  - `risk`：`valid_from + 90d`（灾情/会议短时效；实时预警场景应缩短到 24–72h）。
- `status` 判定（相对 `as_of`），**stale 优先于 expired**：
  1. 证据年龄 > scope 时效窗（`rent_level/rent_policy` 365d、`rent_supply` 180d、`risk` 90d）→ `stale`；
  2. 否则若 `as_of > valid_until` → `expired`；
  3. 否则 `active`。
- 首批数据偏旧（如 2024-02 的 22 元/㎡·月，相对 as_of 已 >12 个月）会被标 `stale`，这是**有意为之**：宁标旧，不假装新鲜。

## 5. 置信度（confidence）规则

纯规则加权，**并强制 `min(0.75)` 方法学上限**，避免假精度：

```
confidence = 0.40*source_reliability
           + 0.25*evidence_factor      # min(1, 0.6 + 0.2*evidence_count)
           + 0.20*recency_factor       # <=90d:1.0, <=365d:0.8, <=730d:0.5, else 0.3
           + 0.15*extraction_quality   # 抽到带单位数值:1.0, 仅关键词:0.7
confidence = min(confidence, 0.75)
```

`source_reliability`：官方（政府/局/镇街/委员会/中心等，0.9）vs 搜索来源（0.8）。规则信号的置信度**不应**高于 0.75；高于该值须走人工审核（`review.status` 非 `auto`）。

## 6. 反模式（硬约束）

1. **不假精度**：规则信号置信度封顶 0.75；单点数值不得推 `yoy/mom` 倍数；无依据不给小数位。
2. **不把 AI 当事实**：`generator.method=llm` 的信号必须带 `evidence`，且 `review.status≠auto` 才可 `active`；规则信号引用原文而非模型转述。
3. **PII 脱敏**：公报名单里的姓名等个人信息一律脱敏（`quote` 不得含姓名），只保留可追溯的文档引用与链接。
4. **不自动动作**：`actions` 只产出**待办/提示**，`requires_human=true`；规则生成器**绝不**产出自动改价、下单、放款、处罚等可执行变更。
5. **不改上游**：signals 是只读派生层，不得回写或篡改 raw/normalized/digests 产物。

## 7. 校验

`src/build_signals.py` 在写盘前，用标准库按本 schema 做**结构校验**（必填/类型/枚举/`minItems`/数值区间/pattern，以及 `valid_until > valid_from` 的显式检查）。不通过则报错退出、**不写**任何文件。
