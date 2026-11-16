#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""早安要闻导出：把 news.json 压成「每天 3 条、能念得出口」的中文要闻。

为什么有这个东西（2026-11-16 用户拍板「要闻接 news.unknow.one」）：
  站点自己的定位是「全球 24h 国际新闻聚合」，300 条里中文只占 68%，
  大头是美股 / 外交 / 娱乐 / 颁奖，直接拿去念会变成机翻腔，而且政治色彩太重。
  所以在**站点侧**多导出一层 `brief.json`，下游（/root/video 早安片）只读这一份。

选题口径（2026-11-16 第二次拍板，比第一版具体）：
  「可能讲一下风俗文化的，旅游娱乐的，例如开业之类的比较好。
    说什么地方消费品有多少，跟民生没什么关系。」
  → 优先：民俗节庆 / 非遗 / 庙会灯会花市 / 演出展览市集 / 景区赏花旅游 / 新场馆新店开业。
  → 丢弃：公报数字（消费总额、同比增速、规模以上…）、政务通稿（座谈/调研/推进会/专题赛）、
    明星八卦、体育比分、涉政涉刑涉灾。宁可少一条，也不念「某地消费品有多少」。

纪律（沿用 signals 层）：只增不改，派生视图；不改 news.json，不动现有页面。

用法：
  python3 src/export_brief.py                # 默认 3 条、回看 30 小时
  python3 src/export_brief.py --limit 5 --window 48
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "news.json"
OUTS = [ROOT / "data" / "brief.json", ROOT / "docs" / "data" / "brief.json"]
SCHEMA_VERSION = "1.1.0"

# ── 内容红线：命中即丢（不是扣分，是整条不进池）────────────────────────────
POL = (
    "习近平", "特朗普", "普京", "拜登", "外交", "会见", "会谈", "峰会", "领导人", "总理", "首相",
    "总统", "选举", "国会", "白宫", "制裁", "关税", "战争", "军队", "军演", "火箭军", "台独",
    "两岸", "涉台", "涉疆", "涉藏", "六四", "政变", "议会", "执政", "在野", "党魁", "巡视",
    "纪检", "落马", "双开", "抗议", "示威", "部长", "五角大楼", "外交部", "国防部",
    "参议院", "众议院", "北约", "导弹", "军舰", "停火", "和谈", "执政党", "反对党", "投票",
    "国务院", "人大", "政协", "省委", "市委", "常委会", "书记", "市长", "省长",
    "APEC", "亚太经合",
)
CRIME = (
    "身亡", "遇难", "死亡", "枪击", "持刀", "被刺", "刺伤", "逮捕", "恐袭", "恐怖", "爆炸",
    "事故", "坠", "溺", "火警", "起火", "车祸", "判刑", "受贿", "自首", "追逃", "命案",
    "猥亵", "性侵", "拐卖", "坠亡", "跳楼", "失联", "中毒", "疫情", "地震", "遇袭", "诈骗",
)
# 政务通稿：字都认识，但念出来等于没说（「召开座谈会」「专题赛…以赛促…」）
ADMIN = ("座谈", "调研", "部署", "推进会", "专题赛", "以赛促", "征求意见", "印发", "通知",
         "公告", "批复", "办法", "条例", "细则", "任命", "免职", "挂牌仪式", "动员会", "培训班")
# 明星八卦 / 体育比分：账号不做；演出、展览、开业不在其中
GOSSIP = ("绯闻", "恋情", "离婚", "结婚", "红毯", "颁奖礼", "剧透", "收视率", "票房榜",
          "明星", "带货", "塌房", "道歉")
# 天气预报类：视频里天气段已经讲咗，要闻唔再重复（用户口径：轻量、唔讲两次）
WXNEWS = ("冷空气", "降温", "台风", "回南天", "暴雨预警", "高温预警", "寒潮", "气温将", "降雨过程")
# 特写 / 人物 / 故事：有文采但冇「今日发生咗咩事」，早安片唔讲（用户 2026-11-16）
STORY = ("故事", "特写", "讲述", "回忆", "访谈", "人物志", "纪实", "系列报道", "手记", "观察",
         "深度", "专栏", "侧记", "背后", "记一位", "这些年", "他们的",
         "日常", "图集", "组图", "掠影", "镜头", "瞬间", "影像", "一日",
         "特别报道", "专题报道", "策划", "融媒", "报道组")
SPORT = ("联赛", "锦标赛", "世界杯", "进球", "比分", "夺冠")
# 股市行情：一早讲涨跌，跟街坊生活没有落点
STOCK = ("A股", "A 股", "沪指", "深成指", "创业板", "个股", "飘绿", "收跌", "涨停", "跌停",
         "午评", "早盘", "收盘", "北向资金", "恒指", "纳指")
# 投行研报/预测：不是「昨日发生的事」，早安片不讲
FINREPORT = ("高盛", "摩根", "瑞银", "花旗", "野村", "中金", "研报", "评级", "目标价", "料将", "展望")

# ── 公报数字：降权到「只够兜底」────────────────────────────────────────────
# 规划/未来时：还没发生的事，念出来像公文（「将推…廊道」「拟建…」）
FUTURE = ("将推", "拟建", "拟于", "规划", "计划投资", "有望", "预计明年", "征求意见")
STATS = ("总额达", "同比增", "同比增长", "增速", "占比", "规模以上", "个百分点", "运行情况",
         "前三季度", "上半年", "一季度", "月度", "社会消费品零售", "投资增速", "工业增加值")

# ── 正面加权词（用户要的口径）──────────────────────────────────────────────
CULTURE = ("庙会", "灯会", "花市", "迎春花市", "非遗", "民俗", "年例", "巡游", "龙舟", "醒狮",
           "舞狮", "粤剧", "粤曲", "老字号", "传统技艺", "祠堂", "庙", "节庆", "嘉年华",
           "文化节", "艺术节", "书展", "非遗展", "展览", "美术馆", "博物馆", "图书馆",
           "剧院", "演出", "音乐会", "音乐节", "戏曲", "话剧", "观影", "市集", "夜市",
           "美食节", "美食", "小吃", "咖啡", "烘焙", "茶文化", "手作", "文创")
TRAVEL = ("景区", "景点", "公园", "花海", "赏花", "花期", "露营", "民宿", "自驾", "旅游",
          "游客", "门票", "绿道", "步道", "登山", "海岛", "古镇", "乡村游", "研学",
          "航线", "首航", "邮轮", "主题乐园", "动物园", "植物园", "湿地")
# 事件动词：早安片要的是「有事发生」，不是「准备推什么」；没有事件动词的文化稿念出来是口号
EVENT = ("开幕", "开业", "开园", "开馆", "开展", "举办", "举行", "亮相", "登场", "推出",
         "开市", "迎客", "开放", "上演", "首演", "上映", "开街", "回归", "焕新", "启幕",
         "开展", "迎来")
OPENING = ("开业", "开馆", "开园", "开幕", "新店", "首店", "首发", "启用", "试运营",
           "投入运营", "落成", "焕新", "重开", "全新亮相", "对外开放", "免费开放")
LIFE = ("物价", "菜价", "油价", "电价", "水价", "燃气", "补贴", "社保", "医保", "养老", "就业",
        "工资", "公积金", "学位", "开学", "教育", "学费", "门诊", "疫苗", "流感", "台风",
        "冷空气", "降雨", "高温", "地铁", "公交", "高铁", "通行", "交通", "快递", "外卖",
        "食品安全", "宠物", "租房", "消费券", "菜市场", "电费", "燃气费", "停车")

CAT_BONUS = {"society": 3.0, "life": 3.0, "culture": 4.0, "travel": 4.0,
             "health": 2.0, "education": 2.0, "technology": 1.0,
             "finance": 0.0, "business": 0.0, "science": 1.0}
# 2026-11-16 用户拍板：「太离地的新闻情愿空缺也不要报 尽量报珠三角或者大湾区这些地域新闻」。
# 硬门槛：标题/摘要里没有任何珠三角、大湾区字眼、也不是本地源来的稿 → 整条不进池。
# 宁可当天只有 1 条甚至 0 条（视频侧会自动跳过要闻段），也不念「药科大学建校九十周年」这种离地稿。
GBA = ("珠三角", "大湾区", "粤港澳", "广东", "广州", "深圳", "佛山", "东莞", "珠海", "中山",
       "惠州", "江门", "肇庆", "香港", "澳门", "粤")
LOCAL = ("广州", "广东", "粤港澳", "大湾区", "佛山", "南海", "深圳", "珠海", "东莞", "中山")


def has(text: str, words) -> int:
    return sum(1 for w in words if w in text)


def clean_title(t: str) -> str:
    """去括号前缀/套话，留一句能念的标题。"""
    t = (t or "").strip()
    t = re.sub(r"^[（(][^）)]{0,20}[）)]", "", t)          # （乡村行·看振兴）（深圳APEC）
    t = re.sub(r"^题[:：]\s*", "", t)
    t = re.sub(r"^[丨\-—\s]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    # 中新网标题常写成「口号 正文」（「赓续药学薪火奔赴百年之约 中国药科大学迎来建校九十周年」），
    # 前半句是标语，念出来没有信息 —— 有后半段带事件动词时就只用后半段。
    if " " in t:
        head, tail = t.split(" ", 1)
        if len(head) >= 5 and len(tail) >= 6 and any(k in tail for k in EVENT):
            t = tail.strip()
    return t


def latin_ratio(t: str) -> float:
    if not t:
        return 1.0
    letters = len(re.findall(r"[A-Za-z]", t))
    return letters / max(1, len(t))


def bigrams(t: str) -> set[str]:
    zh = re.sub(r"[^\u4e00-\u9fff]", "", t)
    return {zh[i:i + 2] for i in range(len(zh) - 1)}


def pick(articles: list[dict], now: dt.datetime, window_h: float, limit: int) -> list[dict]:
    stats_pool: list[dict] = []      # 公报数字：只在「一条文化/生活稿都挑不到」时兜底
    scored: list[dict] = []
    for a in articles:
        zh = (a.get("zh_title") or "").strip()
        raw = (a.get("title") or "").strip()
        if not zh and not raw:
            continue
        title = zh or raw
        if latin_ratio(title) > 0.35:           # 机翻残缺 / 英文残留
            continue
        # dayoo.json 用 published_at / title，news.json 用 published / zh_title，这里统一
        if not a.get("published") and a.get("published_at"):
            a["published"] = a["published_at"]
        try:
            when = dt.datetime.fromisoformat(a["published"])
        except Exception:
            continue
        age_h = (now - when).total_seconds() / 3600
        if age_h < 0 or age_h > window_h:
            continue
        # 时效硬门槛（2026-11-16 用户：没有时效的不算新闻）：窗口 30h 兜住跨夜，
        # 但超过 24h 的稿只在本地源不够时才作兜底，不给主位。
        stale = age_h > 24
        blob = title + " " + (a.get("zh_summary") or "") + " " + (a.get("summary") or "")[:160]
        if has(blob, POL) or has(title, POL):
            continue
        if has(title, WXNEWS):
            continue
        if title.rstrip("。！").endswith("报道") and not has(title, EVENT):
            continue
        if (has(title, CRIME) or has(title, ADMIN) or has(title, GOSSIP)
                or has(title, SPORT) or has(title, STOCK) or has(title, FINREPORT)
                or has(title, STORY)):
            continue
        # 只用中文原生稿：实测机器翻译会出「据《华尔日报》报道」「全世界都是长条形的美国」这种句子
        if (a.get("original_lang") or "zh") != "zh":
            continue
        ct = clean_title(title)
        if len(ct) < 6:
            continue
        # 地域门槛（2026-11-16）：本地源直通，其它源必须提到珠三角/大湾区地名
        _gba = a.get("region") == "gba" or any(k in blob for k in GBA)
        if not _gba:
            continue

        category = (a.get("category") or "").strip()
        score = 3.0                                        # 原生中文基数
        score += min(9.0, 3.0 * has(blob, CULTURE))
        score += min(9.0, 3.0 * has(blob, TRAVEL))
        score += min(9.0, 3.0 * has(blob, OPENING))
        score += min(6.0, 3.0 * has(blob, EVENT))            # 「有事发生」的稿子优先
        score += min(4.5, 1.5 * has(blob, LIFE))
        score += CAT_BONUS.get(category, 0.0)
        score += max(0.0, 3.0 - age_h / 10.0)               # 越新越好
        if stale:
            score -= 4.0                                   # 过 24h 只作兜底
        if "中新网" in (a.get("source") or ""):
            # 用户 2026-11-16：「中新网感觉不好，总是讲故事，没有时效的不算新闻」
            # 不当主位；本地源够数时自然排在后面。
            score -= 4.0
        if a.get("region") == "gba":
            score += 6.0                                    # 本地源（大洋网广州/广东频道）最高优先
        elif any(k in ct for k in LOCAL):
            score += 3.0                                    # 本地优先：观众是广州街坊
        # 上口性：标题里没有事件动词、也没有具体数字的，视频侧的口播门禁会整条丢掉
        # （「赓续药学薪火奔赴百年之约」这种），所以站点侧先筛一次，保证 3 条都念得出来。
        if not (has(ct, EVENT) or re.search(r"[\d０-９]", ct)):
            continue
        is_stats = has(ct, STATS) > 0
        if is_stats:
            score -= 8.0                                    # 「某地消费品有多少」不是民生，只作兜底
        if has(ct, FUTURE) and not has(ct, EVENT):
            continue
        # 「昨日要闻」只能讲已经发生的事：预告稿（将于…启幕/即将开幕）念出来时态是反的
        if "将于" in ct or "即将" in ct or "有望" in ct:
            continue                                         # 纯规划稿（「将推…廊道」「拟建…」）直接丢
        score -= 2.0 * has(ct, FUTURE)
        item = {
            "id": a.get("id", ""), "title": ct, "full_title": title,
            "brief": (a.get("zh_summary") or "").strip(),
            "source": a.get("source", ""), "time": a.get("time", ""),
            "published": a.get("published", ""), "url": a.get("link", ""),
            "category": category, "score": round(score, 1),
        }
        (stats_pool if is_stats else scored).append(item)

    scored.sort(key=lambda x: -x["score"])
    picked: list[dict] = []

    def _dup(it: dict) -> bool:
        bg = bigrams(it["title"])
        return any(len(bg & bigrams(p["title"])) / max(1, len(bg | bigrams(p["title"]))) > 0.55
                   for p in picked)

    # 第一轮：类别不重复、来源不重复 —— 三条各不相同，听得出来是「三条要闻」
    for it in scored:
        if len(picked) >= limit:
            break
        if _dup(it):
            continue
        if any(p["category"] == it["category"] for p in picked):
            continue
        if any(p["source"] == it["source"] for p in picked):
            continue
        picked.append(it)
    # 第二轮：类别/来源限制放宽，仍去重
    for it in scored:
        if len(picked) >= limit:
            break
        if it in picked or _dup(it):
            continue
        picked.append(it)
    # 第三轮：真的没有文化/生活稿，才允许公报数字兜底（按分数排）
    if len(picked) < limit:
        for it in sorted(stats_pool, key=lambda x: -x["score"]):
            if len(picked) >= limit:
                break
            if it in picked or _dup(it):
                continue
            picked.append(it)
    return picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--window", type=float, default=30.0, help="回看小时数")
    ap.add_argument("--src", default=str(SRC))
    a = ap.parse_args()

    src = Path(a.src)
    if not src.exists():
        print(f"!! 没有 {src}")
        return 1
    data = json.loads(src.read_text("utf-8"))
    articles = data.get("articles") or []
    # 2026-11-16：并入大洋网（广州日报）本地稿——广东省内 RSS 全死，只能抓频道列表页
    dayoo = ROOT / "data" / "dayoo.json"
    if dayoo.exists():
        try:
            extra = (json.loads(dayoo.read_text("utf-8")) or {}).get("articles") or []
            articles = articles + extra
            print(f"[brief] 并入大洋网本地稿 {len(extra)} 条")
        except Exception as e:
            print(f"!! 大洋网稿件读取失败：{str(e)[:60]}")
    try:
        now = dt.datetime.fromisoformat(str(data.get("updated")))
    except Exception:
        now = dt.datetime.now(dt.timezone.utc)

    items = pick(articles, now, a.window, a.limit)
    warnings = []
    if len(items) < a.limit:
        warnings.append(f"窗口内只挑到 {len(items)} 条（要求 {a.limit}）")

    out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "as_of": str(data.get("updated") or ""),
        "window_h": a.window,
        "pool": len(articles),
        "count": len(items),
        "items": items,
        "warnings": warnings,
    }
    body = json.dumps(out, ensure_ascii=False, indent=1)
    for p in OUTS:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    print(f"[brief] 池 {len(articles)} 条 → 选 {len(items)} 条（{a.window:g}h 窗口）")
    for it in items:
        print(f"  [{it['score']:5.1f}] {it['time']} {it['source'][:8]:8} {it['title'][:38]}")
    if warnings:
        print("  ! " + "；".join(warnings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
