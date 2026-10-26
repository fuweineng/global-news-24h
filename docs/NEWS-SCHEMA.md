# news.json 数据结构（v1）

`data/news.json` 是四层管线里的**归一化层**（raw → normalized → signals → digests），
`docs/data/news.json` 是同一份的对外副本。供前端 `js/app.js` 与下游服务（gate / souse）消费。

```jsonc
{
  "updated": "2026-10-26T03:21:09Z",   // 本轮生成时间（UTC）
  "total": 300,                         // articles 长度上限 MAX_TOTAL
  "zh_coverage": 0.947,                 // 中文标题覆盖率，低于 0.90 会告警
  "articles": [ Article ]
}
```

## Article 字段

| 字段 | 说明 |
|---|---|
| `id` | md5(source_id + 标题) 前 12 位，稳定去重用 |
| `title` | 原始标题（多为英文） |
| `link` | 原文链接 |
| `published` | ISO8601（UTC）；解析失败时退回 `published_raw` |
| `time` | 发布时间的 `HH:MM`，前端直显 |
| `source` | 源名称（见 `src/sources.json`） |
| `summary` | 原文摘要，**已裁到首句**（≤90 字，控制翻译成本） |
| `category` / `original_lang` / `priority` | 分类、原文语种、源优先级（1 越高） |
| `zh_title` | 中文标题（中文源直接用原文） |
| `zh_summary` | 中文摘要；翻译额度受限时为空字符串，**不是翻译失败占位** |
| `one_line` | 一句话要点 = `zh_summary` 首句（≤42 字），无摘要时退回 `zh_title` |
| `one_line_src` | `summary` / `title`，标明 `one_line` 是真要点还是退回标题 |
| `quality` | 0–100 质量分（见下），**软文会显著偏低**，下游可按它排序/过滤 |

## 质量分 `quality`

| 条件 | 加减分 |
|---|---|
| 标题含硬新闻词（发布/通报/选举/加息/裁员/事故…） | +20 |
| 标题含数字 | +10 |
| 命中公关稿特征（解决方案/战略合作/荣获/携手…） | −45 |
| 无中文摘要 | −10 |
| 源 `priority == 1` | +5 |

基线 50，结果夹在 0–100。**它不是真值判断**，只用于排序与粗筛。

## 已知限制

- `zh_summary` 覆盖率取决于 MyMemory 免费额度。`backfill_summaries()` 每轮补
  `SUMMARY_PER_RUN=40` 条（按发布时间新→旧），多轮自愈；未补上的条目 `one_line`
  会退回标题，此时 `one_line_src == "title"`，下游可据此降级展示。
- 公关稿识别是词表规则，宁可漏判也不重罚；命中条目仍保留在数组里，只降 `quality`。
