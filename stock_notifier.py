"""
波段猎手 · 云端推送版
GitHub Actions 每日定时运行，通过 PushPlus 推送到微信
无需本地电脑开机
"""
import urllib.request
import json
import re
import os
import sys
import io
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ========== 配置（直接写在这里，GitHub Actions 会用） ==========
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "5061c14a3f6e4a82abb0fc9f11879aff")

HOLDINGS = {
    "齐心集团": {
        "code": "sz002301",
        "cost": 7.80,
        "mode": "swing_only",
        "swing_buy_zones": [7.20, 7.00, 6.70],
        "swing_sell_zones": [8.30, 8.60, 8.90],
        "swing_batch_shares": 200,
    },
    "中油资本": {
        "code": "sz000617",
        "cost": 8.37,
        "shares": 1500,
        "mode": "swing_only",
        "swing_buy_zones": [7.00, 6.70, 6.30],
        "swing_sell_zones": [8.50, 9.20, 10.00],
        "swing_batch_shares": 300,
    },
}

WATCHLIST = {
    "紫金矿业": {"code": "sh601899", "buy_zones": [28.0, 26.0, 24.0]},
    "金山办公": {"code": "sh688111"},
    "科大讯飞": {"code": "sz002230"},
    "海光信息": {"code": "sh688041"},
    "中科曙光": {"code": "sh603019"},
}

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

# ========== 推送 ==========
def push_wechat(title, content):
    html = content.replace("\n", "<br>")
    html = f'<pre style="font-family:Consolas,monospace;font-size:14px;line-height:1.6;background:#1a1a2e;color:#e0e0e0;padding:16px;border-radius:8px">{html}</pre>'
    payload = json.dumps({
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": html,
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
    now = datetime.now()
    dow = ["一","二","三","四","五","六","日"][now.weekday()]
    period = os.environ.get("PERIOD", "早盘")
    lines = [f"📊 波段猎手 · 周{dow}{period}", f"{now.strftime('%m/%d %H:%M')}", ""]

    # 持仓
    lines.append("━━━ 持仓 ━━━")
    has_action = False
    for name, cfg in HOLDINGS.items():
        data = fetch_stock(cfg["code"])
        r = analyze(name, cfg, data)
        if r.get("status") == "error":
            lines.append(f"❌ {name}: 数据获取失败")
            continue

        chg = f"{r['change_pct']:+.1f}%"
        sign = "🔴" if r['change_pct'] < 0 else ("🟢" if r['change_pct'] > 0 else "⚪")
        lines.append(f"{r['emoji']} {name} {sign}{chg}")
        lines.append(f"   现价{r['price']:.2f} | 成本{r['cost']:.2f} | 浮亏/盈{r['change_pct']:+.1f}%")
        lines.append(f"   【{r['label']}】→ {r['action']}")

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
    if "紫金矿业" in WATCHLIST:
        data = fetch_stock(WATCHLIST["紫金矿业"]["code"])
        if "error" not in data and data["price"]:
            p = data["price"]
            bz = WATCHLIST["紫金矿业"].get("buy_zones", [28])
            chg = (p - data["prev_close"]) / data["prev_close"] * 100 if data["prev_close"] else 0
            sign = "🔴" if chg < 0 else "🟢"
            lines.append(f"⛏ 现价 {p:.2f} {sign}{chg:+.2f}%")
            if p <= bz[0]:
                lines.append(f"   ✅ 已进入第{1}批建仓区(<{bz[0]})")
            else:
                lines.append(f"   第1批建仓区 ¥{bz[0]}（差{p-bz[0]:.2f}）")
        else:
            lines.append("   数据获取失败")

    # AI标的
    lines.append("")
    lines.append("━━━ AI标的 ━━━")
    for name, cfg in WATCHLIST.items():
        if "紫金" in name:
            continue
        data = fetch_stock(cfg["code"])
        if "error" not in data and data["price"]:
            p = data["price"]
            chg = (p - data["prev_close"]) / data["prev_close"] * 100 if data["prev_close"] else 0
            sign = "🔴" if chg < 0 else "🟢"
            lines.append(f"{sign} {name} ¥{p:.2f} {chg:+.2f}%")

    # 操作
    lines.append("")
    lines.append("━━━ 今日操作 ━━━")
    if has_action:
        pass  # already added above
    else:
        lines.append("🟢 今日无操作信号，持有等待")

    content = "\n".join(lines)

    # 推送到微信
    result = push_wechat(f"波段猎手 · 周{dow}{period}", content)
    print(content)
    print(f"\n[PushPlus] code={result.get('code')} msg={result.get('msg')}")
    return result

if __name__ == "__main__":
    run()
