# 信息底座 · feed.json（广佛珠三角）

> 2026-11-19 建。本站从「全球 24h 国际新闻」转向**广佛/珠三角民生资讯 + 10 城天气**，
> 对外只暴露一份结构化 JSON：`https://news.unknow.one/data/feed.json`。
> 视频流（/root/vbox）以后只读这一份，不再自己抓 Open-Meteo 和新闻。

## 一、数据流

```
cron 每小时 :35（/root/nanhai/nanhai-cron.sh）
  ├─ fetch_gba.py        6 个频道 → data/gba_news.json（+ dayoo.json 兼容层）
  ├─ fetch_weather.py    Open-Meteo 一次请求 → data/weather.json（10 城）
  ├─ export_brief.py     旧口径早安 3 条 → data/brief.json（保留，视频侧还在用）
  └─ export_feed.py      合并 → data/feed.json + docs/data/feed.json → wrangler 部署
```

Worker 是纯静态资源（`wrangler.toml` 的 `[assets] directory = ./docs`），
所以 `docs/data/*.json` 推上去就等于线上文件，没有额外路由。

## 二、feed.json 结构（schema 2.1.0）

```jsonc
{
  "schema_version": "2.1.0",
  "generated_at": "2026-11-19T06:14:00+00:00",
  "weather": {
    "as_of": "…",                       // 天气抓取时间
    "source": "open-meteo",
    "cities": [                         // 10 城，顺序同 gba_common.CITIES
      {"key":"gz","name":"广州",
       // 扁平镜像（旧消费方）
       "date":"2026-11-19","code":3,"text":"阴天","t_min":16,"t_max":22,"rain_prob":8,
       "humidity":48,"current_temp":18.2,"apparent":17.1,
       "wind_dir":"北风","wind_level":"3","wind_kph":14.0,"uv":3.1,
       "tomorrow":{"date":"2026-11-20","code":61,"text":"小雨","t_min":15,"t_max":20,"rain_prob":60},
       // 完整结构（2.1.0 新增，视频侧按日期取；days = 今天/明天/后天）
       "current":{"code":3,"text":"阴","t":18.2,"feels":17.1,"humidity":48,
                  "wind_kph":14.0,"wind_dir":"北风","wind_level":"3",
                  "gust_kph":27.0,"gust_level":"4"},
       "days":[{"date":"2026-11-19","code":3,"text":"阴天","t_min":16,"t_max":22,
                "rain_prob":8,"rain_am":8,"rain_pm":0,"rain_hours":0,"rain_mm":0.0,
                "cloud":88,"humidity_day":50,"uv":3.1,"sunrise":"06:42","sunset":"17:41"}]}
    ]
  },
  "news": {                             // 早安口播子集（export_brief 同一套口径）
    "window_h": 30, "pool": 103, "count": 5,
    "items": [{"id":"…","title":"…","source":"广州日报","time":"11月19日",
               "published":"…","url":"…","score":14.8}]
  },
  "news_all": {"count": 103, "items": [ … 全量，最新在前，带 city/source_id ]},
  "health": {"sources": [{"id":"dayoo_gz","status":"ok","raw":55,"kept":28,"dup":0,"error":""}]}
}
```

字段口径：

| 字段 | 说明 |
|---|---|
| `city` | `gz/fs/dg/sz/zs/zh/hz/qy/zq/jm`（gd = 广东全省稿） |
| `time` | 画面/口播用的日期标签（「11月19日」），列表页没有时刻就不编时间 |
| `text` | WMO 码 + 温湿雨风后的口语化结论（沿用 /root/vbox 已验证口径） |
| `status` | `ok` 有新增 / `dup` 全是重复 / `empty` 为空 / `error` 抓取失败 |
| `days[]` | 今天/明天/后天；视频只认这三天，更远日期回退直连 Open-Meteo |
| `score` | 早安子集打分（export_brief 内一套规则，两处共用不再漂移） |

## 三、源清单（2026-11-19 实测）

| id | 站点 | 频道 | 实测 |
|---|---|---|---|
| dayoo_gz | 大洋网·广州日报 | /guangzhou/ | 55 条，30h 内 28 |
| dayoo_gd | 大洋网·广州日报 | /guangdong/ | 55 条，30h 内 20 |
| dayoo_gz24 | 大洋网 | 广州24小时（150956.shtml） | 多为首页重复（dup） |
| dayoo_gz_hot | 大洋网 | 热闻（150955.shtml） | 多为首页重复（dup） |
| zhtb | 珠海特区报数字报 | pub-zhtb.hizh.cn | 39 条，30h 内 36，带精确时刻 |
| zsnews | 中山网 | /news/index/lists/id/1241.html | 20 条，30h 内 19 |

已知不可抓（留 TODO）：

- 佛山 fsonline.com.cn：首页 JS 渲染，链接无日期
- 东莞 news.sun0769.com/dg/headnews/：页面陈旧（最新 2026-04）
- 深圳 news.sznews.com：首页陈旧（大部分 2022 链接）
- 广东省内 RSS：羊城晚报/南方网/深圳网/中山网 `/rss/` 全部是 HTML 壳，无真实 feed
- 江门 jmnews.com.cn：DNS 不通；gzdaily.dayoo.com：DNS 不通

加源只改一处：`src/fetch_gba.py` 的 `SOURCES` 注册表 + 对应 parser
（`dayoo_list` / `zhtb_epaper` / `zsnews_list`，新站点写一个新 parser 函数即可）。

## 四、健康检查

`/root/dpxon-facts/health_check.py`（dpxon-health.timer，每 30 分钟）：

- feed.json 超过 4 小时未更新 → 告警
- 天气 < 8 城 → 告警
- news_all < 10 条 → 告警
- 另外照旧查 nanhai.json 新鲜度、signals 条数、仓库冲突、facts 停更

异常推 ntfy `pve-alert`，正常不吵。

## 四·五、视频流接入（2026-11-19）

`/root/vbox/bin/fetch_briefing.py` 已改为 **feed 优先**：

- `fetch_weather(day)` → 先 `feed_weather(day)`（本地副本优先 → HTTP），feed 覆盖今天/明天/后天；
  更远日期（提前多日预渲染）自动回退直连 Open-Meteo，行为不变
- `fetch_news()` → 先 `feed_news()`（读 `news.items`，只做字段对齐 + 政治复检 + D-1 优先）
- feed 整个不可用 → 回退旧路径（brief.json + 直连 Open-Meteo），出片不中断
- 实测：`--date 2026-11-19` 走 feed（天气源/要闻源均显示 feed.json）；`--date 2026-11-25`
  天气回退直连、新闻仍用 feed；`make check` / `make preview` 均通过，天气卡与新闻卡数值完整

cron 侧 `export_feed.py --limit 8`：给视频侧留 8 条候选（实际最多用 2 条）。

## 五、回滚

```bash
# 单步回滚：换回旧单源（fetch_dayoo）
sed -i 's|timeout 200 python3 src/fetch_gba.py|timeout 120 python3 src/fetch_dayoo.py|' /root/nanhai/nanhai-cron.sh
# 代码回滚
git -C /root/nanhai/global-news-24h revert a82046c2
```

feed.json 是派生文件，删掉不影响其它产物（brief.json / nanhai.json 各走各的）。
