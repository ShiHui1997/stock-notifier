"""
波段猎手 · 云端推送版 v3
GitHub Actions 每日定时运行，通过 PushPlus 推送到微信
v3 改进：交易记录改为独立页面链接（PushPlus 过滤 form/script，内嵌表单不可用）
"""
import urllib.request
import urllib.parse
import json
import re
import os
import sys
import io
from datetime import datetime, timezone, timedelta
TZ_BEIJING = timezone(timedelta(hours=8))

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ========== 环境变量 ==========
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "5061c14a3f6e4a82abb0fc9f11879aff")
TRADE_TOKEN = os.environ.get("TRADE_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "ShiHui1997/stock-notifier")
PERIOD = os.environ.get("PERIOD", "早盘")

# ========== 配置加载 ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def load_json(filename):
    path = os.path.join(SCRIPT_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filename, data):
    path = os.path.join(SCRIPT_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_config():
    return load_json("holdings_config.json")

# ========== 交易处理 ==========
def process_pending_trades():
    """处理用户提交的交易记录，更新成本和持仓"""
    try:
        pending = load_json("pending_trades.json")
    except Exception:
        return []

    trades = pending.get("trades", [])
    if not trades:
        return []

    config = load_config()
    applied = []

    for trade in trades:
        name = trade.get("name", "")
        t_type = trade.get("type", "")
        price = float(trade.get("price", 0))
        shares = int(trade.get("shares", 0))

        if name not in config["holdings"]:
            print(f"[交易处理] 未知股票: {name}，跳过")
            applied.append({**trade, "status": "skipped", "reason": "未知股票"})
            continue

        h = config["holdings"][name]
        old_cost = h.get("cost", 0)
        old_shares = h.get("shares", 0)

        if t_type == "buy":
            total_cost = old_cost * old_shares + price * shares
            new_shares = old_shares + shares
            h["cost"] = round(total_cost / new_shares, 3) if new_shares > 0 else old_cost
            h["shares"] = new_shares
            print(f"[交易处理] 买入 {name} {price}x{shares} 成本 {old_cost:.2f}->{h['cost']:.2f} 仓位 {old_shares}->{new_shares}")
        elif t_type == "sell":
            if shares > old_shares:
                print(f"[交易处理] 卖出量{shares}超过持仓{old_shares}，调整为清仓")
                shares = old_shares
            h["shares"] = max(0, old_shares - shares)
            print(f"[交易处理] 卖出 {name} {price}x{shares} 仓位 {old_shares}->{h['shares']}")
        else:
            applied.append({**trade, "status": "skipped", "reason": f"未知类型:{t_type}"})
            continue

        applied.append({
            **trade,
            "status": "applied",
            "old_cost": old_cost,
            "new_cost": h["cost"],
            "old_shares": old_shares,
            "new_shares": h["shares"]
        })

    # 保存更新后的配置
    save_json("holdings_config.json", config)
    # 清空已处理的交易
    save_json("pending_trades.json", {"_说明": "用户通过交易页面提交的交易记录。分析脚本会自动处理并清空。", "trades": []})

    return applied


def generate_trade_log(trades):
    """生成交易处理日志，附加到推送消息"""
    if not trades:
        return ""
    lines = ["", "━━━ 📝 已处理的交易 ━━━"]
    for t in trades:
        if t.get("status") == "applied":
            act = "买入" if t["type"] == "buy" else "卖出"
            lines.append(f"  {act} {t['name']} {t['price']}元 x {t['shares']}股")
            if t["type"] == "buy":
                lines.append(f"  → 成本 {t['old_cost']:.2f} -> {t['new_cost']:.2f}")
            lines.append(f"  -> 仓位 {t['old_shares']} -> {t['new_shares']}股")
        elif t.get("status") == "skipped":
            lines.append(f"  ⚠️ {t.get('name','')} 跳过: {t.get('reason','')}")
    return "\n".join(lines)


# ========== 数据获取 ==========
def fetch_stock(code):
    url = f"http://hq.sinajs.cn/list={code}"
    headers = {"Referer": "https://finance.sina.com.cn"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("gbk")
        match = re.search(r'"(.+)"', data)
        if match:
            fields = match.group(1).split(",")
            if len(fields) >= 32:
                return {
                    "name": fields[0],
                    "open": float(fields[1]) if fields[1] else 0,
                    "prev_close": float(fields[2]) if fields[2] else 0,
                    "price": float(fields[3]) if fields[3] else 0,
                    "high": float(fields[4]) if fields[4] else 0,
                    "low": float(fields[5]) if fields[5] else 0,
                }
    except Exception as e:
        return {"error": str(e)}
    return {"error": "parse failed"}


# ========== 分析 ==========
def analyze(name, cfg, data):
    if "error" in data:
        return {"name": name, "status": "error"}

    price = data["price"]
    cost = cfg["cost"]
    mode = cfg.get("mode", "swing_only")
    pct = (price - cost) / cost * 100

    result = {
        "name": name, "price": price, "cost": cost,
        "change_pct": round(pct, 2), "mode": mode,
    }

    if mode == "swing_only":
        buy_z = cfg.get("swing_buy_zones", [])
        sell_z = cfg.get("swing_sell_zones", [])
        batch = cfg.get("swing_batch_shares", 200)

        if any(price >= z for z in sell_z):
            zone = [z for z in sell_z if price >= z][0]
            result["signal"] = "SWING_SELL"
            result["emoji"] = "📈"
            result["label"] = f"做T卖出@{zone}"
            result["action"] = f"卖{batch}股"
        elif any(price <= z for z in buy_z):
            zone = [z for z in buy_z if price <= z][-1]
            result["signal"] = "SWING_BUY"
            result["emoji"] = "📉"
            result["label"] = f"做T买入@{zone}"
            result["action"] = f"买{batch}股"
        else:
            result["signal"] = "HOLD"
            result["emoji"] = "⏸"
            result["label"] = "持有等波段"
            result["action"] = "不动"
    else:
        result["signal"] = "HOLD"
        result["emoji"] = "⏸"
        result["label"] = "持有等待"
        result["action"] = "不动"

    return result


# ========== 新闻分析模块 ==========
# 新闻关键词与影响因素配置
NEWS_CONFIG = {
    "齐心集团": {
        "keywords": ["齐心集团", "002301"],
        "sector": "办公集采/B2B电商",
        "impact_factors": ["信创政策", "政企集采", "办公耗材", "B2B电商"]
    },
    "中油资本": {
        "keywords": ["中油资本", "000617"],
        "sector": "石油金融",
        "impact_factors": ["国际油价", "中石油集团", "成品油", "金融监管"]
    },
    "紫金矿业": {
        "keywords": ["紫金矿业", "601899"],
        "sector": "有色金属/黄金",
        "impact_factors": ["金价", "黄金", "铜价", "有色金属", "美联储"]
    }
}

MACRO_CODES = {
    "sh000001": ("上证指数", "📊"),
    "sz399006": ("创业板指", "🚀"),
    "hf_GC":   ("COMEX黄金", "🥇"),
    "hf_CL":   ("WTI原油", "🛢️"),
    "hf_HG":   ("COMEX铜", "🔨"),
}

def fetch_commodity(code):
    """大宗商品期货价格（Sina hf_ 接口）"""
    url = f"http://hq.sinajs.cn/list={code}"
    headers = {"Referer": "https://finance.sina.com.cn"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("gbk")
        m = re.search(r'"(.+)"', data)
        if m:
            fields = m.group(1).split(",")
            if len(fields) >= 4 and fields[1] and fields[3]:
                price = float(fields[1])
                prev  = float(fields[3])
                pct   = (price - prev) / prev * 100
                return {"price": price, "pct": round(pct, 2)}
    except Exception as e:
        print(f"[大宗] {code} 失败: {e}")
    return None


def fetch_macro_overview():
    """获取大盘指数 + 大宗商品数据"""
    results = {}
    for code, (name, icon) in MACRO_CODES.items():
        if code.startswith("hf_"):
            d = fetch_commodity(code)
            if d:
                results[code] = {"name": name, "icon": icon,
                                  "price": d["price"], "pct": d["pct"], "is_comm": True}
        else:
            d = fetch_stock(code)
            if "error" not in d and d["price"] and d["prev_close"]:
                pct = (d["price"] - d["prev_close"]) / d["prev_close"] * 100
                results[code] = {"name": name, "icon": icon,
                                  "price": d["price"], "pct": round(pct, 2), "is_comm": False}
    return results


def fetch_announcements(stock_code, limit=3):
    """巨潮资讯 — 个股公告（JSON接口）"""
    url = ("http://www.cninfo.com.cn/new/fulltextSearch/full"
            f"?searchkey={urllib.parse.quote(stock_code)}"
            "&sdate=&edate=&isfulltext=false"
            "&sortName=pubdate&sortType=desc"
            f"&pageNum=1&pageSize={limit}")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "http://www.cninfo.com.cn"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # 巨潮资讯返回体格式可能有 annals / data / list 等 key
        items = []
        for key in ("annals", "data", "list", "announcements"):
            if key in data and isinstance(data[key], list):
                items = data[key]
                break
        results = []
        for item in items[:limit]:
            title = item.get("title", item.get("docTitle", "")).strip()
            date  = item.get("pubdate", item.get("publishDate", ""))[:10]
            if title:
                results.append({"title": title, "date": date})
        return results
    except Exception as e:
        print(f"[公告] 巨潮资讯({stock_code}): {e}")
        return []


def fetch_news_sina(keyword, limit=5):
    """新浪财经新闻搜索 API"""
    try:
        kw  = urllib.parse.quote(keyword)
        url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k={kw}&num={limit}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
            "Referer": "https://finance.sina.com.cn"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        articles = []
        for item in data.get("result", {}).get("list", [])[:limit]:
            title = item.get("title", "").strip()
            title = re.sub(r"<[^>]+>", "", title)
            if title and len(title) > 6:
                articles.append({"title": title})
        return articles
    except Exception as e:
        print(f"[新闻] 新浪({keyword}): {e}")
        return []


def get_stock_news(name, limit=3):
    """获取单只股票的新闻+公告（多源去重）"""
    ncfg = NEWS_CONFIG.get(name, {})
    keywords = ncfg.get("keywords", [name])
    seen    = set()
    articles = []

    # 1. 公司公告（巨潮资讯，优先级最高）
    for kw in keywords:
        if len(articles) >= limit:
            break
        anns = fetch_announcements(kw, limit=2)
        for a in anns:
            t = f"【公告】{a['title']}"
            if t not in seen:
                seen.add(t)
                articles.append({"title": t})

    # 2. 新闻搜索（新浪）
    for kw in keywords:
        if len(articles) >= limit:
            break
        news = fetch_news_sina(kw, limit=5)
        for a in news:
            if a["title"] not in seen:
                seen.add(a["title"])
                articles.append(a)

    return articles[:limit]


def generate_news_section(config):
    """生成新闻分析板块（纯文本，插入推送内容）"""
    holdings  = config.get("holdings", {})
    watchlist = config.get("watchlist", {})
    lines     = []

    # 1. 大盘 + 大宗商品
    macro = fetch_macro_overview()
    if macro:
        lines.append("━━━ 📰 早间速览 ━━━")
        lines.append("【大盘与商品】")
        for code, d in macro.items():
            sign = "🔴" if d["pct"] < 0 else ("🟢" if d["pct"] > 0 else "⚪")
            if d.get("is_comm"):
                lines.append(f"  {d['icon']} {d['name']} ${d['price']:.2f} {sign}{d['pct']:+.2f}%")
            else:
                lines.append(f"  {d['icon']} {d['name']} {d['price']:.2f} {sign}{d['pct']:+.2f}%")
        lines.append("")

    # 2. 个股新闻
    stocks_to_check = list(holdings.keys())
    if "紫金矿业" in watchlist:
        stocks_to_check.append("紫金矿业")

    any_news = False
    for name in stocks_to_check:
        ncfg   = NEWS_CONFIG.get(name)
        if not ncfg:
            continue
        articles = get_stock_news(name, limit=3)
        if articles:
            any_news = True
            lines.append(f"【{name}·{ncfg['sector']}】")
            for i, a in enumerate(articles, 1):
                title = a["title"][:48] + "..." if len(a["title"]) > 48 else a["title"]
                lines.append(f"  {i}. {title}")
            lines.append(f"  ⚡ 关注: {', '.join(ncfg['impact_factors'])}")
            lines.append("")

    if not any_news and not macro:
        return ""   # 无数据，不显示该板块

    if not any_news and macro:
        lines.append("  个股新闻/公告暂未获取（非交易时段或接口延迟）")
        lines.append("")

    return "\n".join(lines)


# ========== 交易记录链接（替代内嵌表单） ==========
def generate_trade_link():
    """
    PushPlus 会过滤 <form> <script> <button onclick> 等交互元素，
    所以内嵌表单无法在微信中显示。
    改为生成一个可点击的链接，跳转到独立的交易记录页面（trade.html）。
    页面通过 GitHub Pages 或 jsDelivr CDN 提供。
    """
    token = TRADE_TOKEN

    # GitHub Pages 地址（已启用，稳定可靠）
    pages_url = "https://shihui1997.github.io/stock-notifier/trade.html"

    if token:
        link_url = f"{pages_url}?t={token}"
    else:
        link_url = pages_url

    return f"""
<div style="background:#1a2744;border-radius:10px;padding:16px;margin-top:10px;border-left:3px solid #3498db;text-align:center">
  <div style="color:#3498db;font-weight:bold;font-size:15px;margin-bottom:10px">📝 记录买卖交易</div>
  <a href="{link_url}" style="display:inline-block;padding:13px 30px;background:#3498db;color:#fff;text-decoration:none;border-radius:8px;font-size:16px;font-weight:bold">👆 点击这里记录交易</a>
  <p style="color:#777;font-size:12px;margin-top:8px">提交后下次分析自动更新成本和持仓</p>
</div>"""


# ========== 推送 ==========
def push_wechat(title, content, trade_html=""):
    # 分析报告部分 — 用 pre 标签保持格式
    report_html = content.replace("\n", "<br>")
    report_html = (
        '<pre style="font-family:Consolas,monospace;font-size:14px;'
        'line-height:1.7;background:#161b22;color:#e0e0e0;'
        'padding:16px;border-radius:8px;white-space:pre-wrap">'
        + report_html +
        '</pre>'
    )

    # 完整 HTML = 报告 + 交易链接
    full_html = report_html + (trade_html or "")

    payload = json.dumps({
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": full_html,
        "template": "html"
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://www.pushplus.plus/send",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read().decode())


# ========== 主流程 ==========
def run():
    config = load_config()
    holdings = config.get("holdings", {})
    watchlist = config.get("watchlist", {})

    # 1. 先处理待处理的交易
    applied_trades = process_pending_trades()
    if applied_trades:
        config = load_config()
        holdings = config.get("holdings", {})

    now = datetime.now(TZ_BEIJING)
    dow = ["一","二","三","四","五","六","日"][now.weekday()]
    lines = [f"📊 波段猎手 · 周{dow}{PERIOD}", f"{now.strftime('%m/%d %H:%M')}", ""]

    # 新闻速览（早盘推送时显示）
    if PERIOD == "早盘":
        news_section = generate_news_section(config)
        if news_section:
            lines.append(news_section)

    # 持仓分析
    lines.append("━━━ 持仓 ━━━")
    has_action = False
    for name, cfg in holdings.items():
        data = fetch_stock(cfg["code"])
        r = analyze(name, cfg, data)
        if r.get("status") == "error":
            lines.append(f"❌ {name}: 数据获取失败")
            continue

        chg = f"{r['change_pct']:+.1f}%"
        sign = "🔴" if r['change_pct'] < 0 else ("🟢" if r['change_pct'] > 0 else "⚪")
        lines.append(f"{r['emoji']} {name} {sign}{chg}")
        shares_info = f" ({r['cost']:.2f}x{cfg.get('shares','?')}股)" if cfg.get('shares') else ""
        lines.append(f"   现价{r['price']:.2f} | 成本{r['cost']:.2f} | 浮亏/盈{r['change_pct']:+.1f}%{shares_info}")
        lines.append(f"   【{r['label']}】-> {r['action']}")

        buy_z = cfg.get("swing_buy_zones", [])
        sell_z = cfg.get("swing_sell_zones", [])
        batch = cfg.get("swing_batch_shares", 200)
        lines.append(f"   📉 买入: {','.join(str(z) for z in buy_z)} (每批{batch}股)")
        lines.append(f"   📈 卖出: {','.join(str(z) for z in sell_z)} (每批{batch}股)")
        lines.append("")

        if r["signal"] in ("SWING_BUY", "SWING_SELL"):
            lines.append(f"🔴 {name}: {r['label']}！{r['action']}")
            has_action = True

    # 紫金矿业
    lines.append("━━━ 紫金矿业 ━━━")
    if "紫金矿业" in watchlist:
        data = fetch_stock(watchlist["紫金矿业"]["code"])
        if "error" not in data and data["price"]:
            p = data["price"]
            bz = watchlist["紫金矿业"].get("buy_zones", [28])
            chg = (p - data["prev_close"]) / data["prev_close"] * 100 if data["prev_close"] else 0
            sign = "🔴" if chg < 0 else "🟢"
            lines.append(f"⛏ 现价 {p:.2f} {sign}{chg:+.2f}%")
            if p <= bz[0]:
                lines.append(f"   ✅ 已进入第1批建仓区(<{bz[0]})")
            else:
                lines.append(f"   第1批建仓区 ¥{bz[0]}（差{p-bz[0]:.2f}）")
        else:
            lines.append("   数据获取失败")

    # AI标的
    lines.append("")
    lines.append("━━━ AI标的 ━━━")
    for name, cfg in watchlist.items():
        if "紫金" in name:
            continue
        data = fetch_stock(cfg["code"])
        if "error" not in data and data["price"]:
            p = data["price"]
            chg = (p - data["prev_close"]) / data["prev_close"] * 100 if data["prev_close"] else 0
            sign = "🔴" if chg < 0 else "🟢"
            lines.append(f"{sign} {name} ¥{p:.2f} {chg:+.2f}%")

    # 操作总结
    lines.append("")
    lines.append("━━━ 今日操作 ━━━")
    if has_action:
        pass  # 已在上面逐条标注了
    else:
        lines.append("🟢 今日无操作信号，持有等待")

    # 交易处理日志
    trade_log = generate_trade_log(applied_trades)
    if trade_log:
        lines.append(trade_log)

    content = "\n".join(lines)

    # 生成交易链接（替代内嵌表单）
    trade_html = generate_trade_link()

    # 推送到微信
    result = push_wechat(f"波段猎手 · 周{dow}{PERIOD}", content, trade_html)
    print(content)
    print(f"\n[PushPlus] code={result.get('code')} msg={result.get('msg')}")

    if applied_trades:
        print("\n[提示] 交易已处理，holdings_config.json 已更新。")

    return result


if __name__ == "__main__":
    run()
