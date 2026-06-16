"""
波段猎手 · 每日盯盘分析脚本 v2
用法: python stock_analyzer.py [--wechat]
  --wechat   输出微信助手适配的紧凑格式
配置: 修改 stock_config.json 即可更新成本/目标，无需改代码
"""
import urllib.request
import json
import re
import sys
import io
import os
from datetime import datetime

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ========== 配置加载 ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "stock_config.json")

def load_config():
    """从 stock_config.json 加载持仓和关注标的配置"""
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ 配置文件不存在: {CONFIG_PATH}")
        return None, None
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("holdings", {}), cfg.get("watchlist", {})

# ========== 数据获取 ==========
def fetch_stock_data(code):
    """从新浪财经获取实时行情"""
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
                    "volume": float(fields[8]) if fields[8] else 0,
                    "amount": float(fields[9]) if fields[9] else 0,
                }
    except Exception as e:
        return {"error": str(e)}
    return {"error": "parse failed"}

# ========== 分析逻辑 ==========
def analyze_holding(name, config, data):
    """分析持仓标的，返回完整分析结果"""
    if "error" in data:
        return {"name": name, "status": "error", "msg": data["error"]}

    cost = config["cost"]
    price = data["price"]
    change_pct = (price - cost) / cost * 100
    target_price = round(cost * (1 + config["target_pct"]), 2)
    stop_price = round(cost * (1 + config["stop_pct"]), 2)
    to_target = round((target_price - price) / price * 100, 1)
    to_stop = round((price - stop_price) / price * 100, 1)

    result = {
        "name": name,
        "code": config["code"],
        "price": price,
        "open": data["open"],
        "high": data["high"],
        "low": data["low"],
        "cost": cost,
        "change_pct": round(change_pct, 2),
        "target_price": target_price,
        "stop_price": stop_price,
        "to_target_pct": to_target,
        "to_stop_pct": to_stop,
        "half_sell_pct": config.get("half_sell_pct", 0.5),
        "mode": config.get("mode", "standard"),
    }

    # 波段模式：信号判定不同
    mode = config.get("mode", "standard")

    if mode == "swing":
        swing_buy = config.get("swing_buy_zones", [])
        swing_sell = config.get("swing_sell_zones", [])
        swing_batch = config.get("swing_batch_shares", 200)

        # 先检查是否到了止盈目标（原始仓位仍用标准规则）
        if price >= target_price:
            result["signal"] = "SELL"
            result["signal_emoji"] = "🔔"
            result["signal_label"] = "止盈卖出"
            result["action"] = f"卖{int(config.get('half_sell_pct',0.5)*100)}%"
        elif price <= stop_price:
            result["signal"] = "STOP"
            result["signal_emoji"] = "🛑"
            result["signal_label"] = "止损清仓"
            result["action"] = "全清"
        elif any(price >= z for z in swing_sell):
            # 到了波段卖出区 → 卖出做T的份额
            sell_zone = [z for z in swing_sell if price >= z][0]
            result["signal"] = "SWING_SELL"
            result["signal_emoji"] = "🔄"
            result["signal_label"] = f"波段卖出@{sell_zone}"
            result["action"] = f"卖{swing_batch}股做T"
        elif any(price <= z for z in swing_buy):
            # 到了波段买入区 → 买入做T
            buy_zone = [z for z in swing_buy if price <= z][-1]
            result["signal"] = "SWING_BUY"
            result["signal_emoji"] = "🔄"
            result["signal_label"] = f"波段买入@{buy_zone}"
            result["action"] = f"买{swing_batch}股做T"
        else:
            result["signal"] = "HOLD"
            result["signal_emoji"] = "⏸"
            result["signal_label"] = "持有等波段"
            result["action"] = "不动"

    elif mode == "swing_only":
        # 纯做T模式：不止损，只看波段买卖区间
        swing_buy = config.get("swing_buy_zones", [])
        swing_sell = config.get("swing_sell_zones", [])
        swing_batch = config.get("swing_batch_shares", 200)

        if any(price >= z for z in swing_sell):
            sell_zone = [z for z in swing_sell if price >= z][0]
            result["signal"] = "SWING_SELL"
            result["signal_emoji"] = "📈"
            result["signal_label"] = f"做T卖出@{sell_zone}"
            result["action"] = f"卖{swing_batch}股"
        elif any(price <= z for z in swing_buy):
            buy_zone = [z for z in swing_buy if price <= z][-1]
            result["signal"] = "SWING_BUY"
            result["signal_emoji"] = "📉"
            result["signal_label"] = f"做T买入@{buy_zone}"
            result["action"] = f"买{swing_batch}股"
        else:
            result["signal"] = "HOLD"
            result["signal_emoji"] = "⏸"
            result["signal_label"] = "持有等波段"
            result["action"] = "不动"

    else:
        # 标准模式
        if price >= target_price:
            result["signal"] = "SELL"
            result["signal_emoji"] = "🔔"
            result["signal_label"] = "止盈卖出"
            result["action"] = f"卖{int(config.get('half_sell_pct',0.5)*100)}%"
        elif price <= stop_price:
            result["signal"] = "STOP"
            result["signal_emoji"] = "🛑"
            result["signal_label"] = "止损清仓"
            result["action"] = "全清"
        elif price >= cost and change_pct > 0:
            result["signal"] = "WATCH"
            result["signal_emoji"] = "👀"
            result["signal_label"] = "回本观察"
            result["action"] = "考虑减仓"
        elif to_stop < 3:
            result["signal"] = "WARN"
            result["signal_emoji"] = "⚠️"
            result["signal_label"] = "逼近止损"
            result["action"] = "准备割"
        else:
            result["signal"] = "HOLD"
            result["signal_emoji"] = "⏸"
            result["signal_label"] = "持有等待"
            result["action"] = "不动"

    return result

# ========== 输出格式化 ==========
def format_wechat(holdings_signals, watch_results, cash_status, holdings_cfg=None):
    """微信适配的紧凑输出格式"""
    lines = []
    now = datetime.now()
    day_of_week = ["一","二","三","四","五","六","日"][now.weekday()]

    lines.append(f"📊 波段猎手 · 周{day_of_week}早报")
    lines.append(f"{now.strftime('%m/%d %H:%M')}")
    lines.append("")

    # 持仓分析
    lines.append("━━━ 持仓 ━━━")
    for s in holdings_signals:
        if s.get("status") == "error":
            lines.append(f"❌ {s['name']}: 数据获取失败")
            continue

        chg = f"{s['change_pct']:+.1f}%"
        chg_sign = "🔴" if s['change_pct'] < 0 else ("🟢" if s['change_pct'] > 0 else "⚪")

        lines.append(f"{s['signal_emoji']} {s['name']} {chg_sign}{chg}")
        
        if s.get("mode") == "swing_only":
            # 纯做T模式：不显示止损，显示硬扛
            lines.append(f"   现价{s['price']:.2f} | 成本{s['cost']:.2f} | 浮亏/盈{(s['price']-s['cost'])/s['cost']*100:+.1f}%")
            lines.append(f"   【{s['signal_label']}】→ {s['action']}")
        else:
            lines.append(f"   现价{s['price']:.2f} | 成本{s['cost']:.2f} | 止盈{s['target_price']:.2f} | 止损{s['stop_price']:.2f}")
            lines.append(f"   距止盈{s['to_target_pct']:.1f}% | 距止损{s['to_stop_pct']:.1f}%")
            lines.append(f"   【{s['signal_label']}】→ {s['action']}")

        # 波段模式额外显示买卖区间
        if s.get("mode") in ("swing", "swing_only"):
            if holdings_cfg and s["name"] in holdings_cfg:
                buy_zones = holdings_cfg[s["name"]].get("swing_buy_zones", [])
                sell_zones = holdings_cfg[s["name"]].get("swing_sell_zones", [])
                batch = holdings_cfg[s["name"]].get("swing_batch_shares", 200)
                lines.append(f"   📉 买入区: {','.join(str(z) for z in buy_zones)} (每批{batch}股)")
                lines.append(f"   📈 卖出区: {','.join(str(z) for z in sell_zones)} (每批{batch}股)")
        lines.append("")

    # 紫金矿业
    lines.append("━━━ 紫金矿业 ━━━")
    found = False
    for w in watch_results:
        if "紫金" in w["name"]:
            found = True
            if w.get("price") and w["price"] != "N/A":
                chg_str = f"{w.get('change',0):+.2f}%"
                chg_sign = "🔴" if w.get('change',0) < 0 else ("🟢" if w.get('change',0) > 0 else "⚪")
                lines.append(f"⛏ 现价 {w['price']:.2f} {chg_sign}{chg_str}")
                # 检查建仓区间
                buy_zones = w.get("buy_zones", [28, 26, 24])
                if w["price"] <= buy_zones[0]:
                    lines.append(f"   ✅ 已进入第1批建仓区(<{buy_zones[0]})")
                else:
                    lines.append(f"   第1批建仓区 ¥{buy_zones[0]}（差{(w['price']-buy_zones[0]):.2f}）")
            else:
                lines.append(f"   数据获取失败")
            break
    if not found:
        lines.append("   未配置")

    # AI标的池简要
    lines.append("")
    lines.append("━━━ AI标的 ━━━")
    for w in watch_results:
        if "紫金" in w["name"]:
            continue
        if w.get("price") and w["price"] != "N/A":
            chg_str = f"{w.get('change',0):+.2f}%"
            chg_sign = "🔴" if w.get('change',0) < 0 else "🟢"
            lines.append(f"{chg_sign} {w['name']} ¥{w['price']:.2f} {chg_str}")
        else:
            lines.append(f"⚪ {w['name']} 数据异常")

    # 操作提醒
    lines.append("")
    lines.append("━━━ 今日操作 ━━━")
    has_action = False
    for s in holdings_signals:
        if s.get("signal") in ("SELL", "STOP"):
            lines.append(f"🔴 {s['name']}: {s['signal_label']}！{s['action']}")
            has_action = True
        elif s.get("signal") in ("SWING_BUY", "SWING_SELL"):
            lines.append(f"🔄 {s['name']}: {s['signal_label']}！{s['action']}")
            has_action = True
        elif s.get("signal") == "WARN":
            lines.append(f"🟡 {s['name']}: 逼近止损，注意盯盘")
            has_action = True
    if not has_action:
        lines.append(f"🟢 今日无操作信号，持有等待")
    
    lines.append(f"💡 {cash_status}")

    return "\n".join(lines)

def format_full(holdings_signals, watch_results, cash_status):
    """完整控制台输出格式"""
    lines = []
    now = datetime.now()
    lines.append("=" * 50)
    lines.append(f"  波段猎手 · 每日盯盘 v2")
    lines.append(f"  {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)

    lines.append("\n--- 持仓分析 ---")
    for s in holdings_signals:
        if s.get("status") == "error":
            lines.append(f"  ❌ {s['name']}: {s['msg']}")
            continue
        lines.append(f"\n  {s['signal_emoji']} [{s['name']}] {s['code']}")
        lines.append(f"  现价:{s['price']:.2f} | 成本:{s['cost']:.2f} | 涨跌:{s['change_pct']:+.2f}%")
        lines.append(f"  今开:{s['open']:.2f} | 最高:{s['high']:.2f} | 最低:{s['low']:.2f}")
        lines.append(f"  止盈:{s['target_price']:.2f}({s['to_target_pct']}%) | 止损:{s['stop_price']:.2f}({s['to_stop_pct']}%)")
        lines.append(f"  >>> 信号:{s['signal_label']} → {s['action']}")

    lines.append("\n--- 关注标的 ---")
    for w in watch_results:
        if w.get("price") and w["price"] != "N/A":
            chg = f"{w.get('change',0):+.2f}%"
            lines.append(f"  {w['name']} ({w.get('code','')}): {w['price']:.2f} {chg}")
            if w.get("buy_zones"):
                lines.append(f"    建仓区: <{w['buy_zones'][0]}")
        else:
            lines.append(f"  {w['name']}: 数据获取失败")

    lines.append(f"\n--- 综合 ---")
    lines.append(f"  {cash_status}")
    lines.append("=" * 50)

    return "\n".join(lines)

# ========== 主流程 ==========
def main():
    holdings_cfg, watchlist_cfg = load_config()
    if holdings_cfg is None:
        return None, None

    wechat_mode = "--wechat" in sys.argv

    # 分析持仓
    holdings_signals = []
    for name, config in holdings_cfg.items():
        data = fetch_stock_data(config["code"])
        result = analyze_holding(name, config, data)
        holdings_signals.append(result)

    # 分析关注标的
    watch_results = []
    for name, config in watchlist_cfg.items():
        data = fetch_stock_data(config["code"])
        if "error" in data:
            watch_results.append({
                "name": name, "code": config["code"],
                "price": "N/A", "note": config.get("note", ""),
                "buy_zones": config.get("buy_zones", [])
            })
            continue
        watch_results.append({
            "name": name,
            "code": config["code"],
            "price": data["price"],
            "change": round((data["price"] - data["prev_close"]) / data["prev_close"] * 100, 2) if data["prev_close"] else 0,
            "note": config.get("note", ""),
            "buy_zones": config.get("buy_zones", []),
        })

    # 仓位状态
    has_cash = False  # 当前满仓
    cash_status = "⚡仓位已满，无现金操作。等反弹到成本线优先减仓释放流动性。"

    # 输出
    if wechat_mode:
        output = format_wechat(holdings_signals, watch_results, cash_status, holdings_cfg)
    else:
        output = format_full(holdings_signals, watch_results, cash_status)

    print(output)
    return holdings_signals, watch_results

if __name__ == "__main__":
    main()
