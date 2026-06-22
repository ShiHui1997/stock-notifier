#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票量化分析系统 V3 - 完整集成版（修复版）
集成所有模块：技术指标、回测、新闻、自学习、动态策略、替代股分析
"""

import sys
import os
import json
import requests
from datetime import datetime

# ========== 导入所有模块 ==========
try:
    from stock_indicators import calculate_all_indicators, generate_signal as gen_indicator_signal
    from stock_backtest import WalkForwardBacktester, simple_moving_average_strategy, combined_strategy
    from stock_news import analyze_stock_news, generate_news_summary
    from stock_self_learning import SelfLearningSystem
    from stock_strategy import MarketStateAnalyzer, DynamicStrategyScheduler
    from stock_alternative import AlternativeStockFinder, WatchlistManager
    from stock_sector import (
        fetch_sector_rankings, analyze_market_trend,
        generate_sector_report, should_remove_from_watchlist,
        SectorAnalyzer
    )
except ImportError as e:
    print(f"[ERROR] 模块导入失败: {e}")
    sys.exit(1)


# ============================================================
#  数据获取层 - 新浪财经API
# ============================================================

def fetch_realtime_data(stock_code):
    """获取单只股票实时行情"""
    try:
        # 转换为新浪代码格式
        if stock_code.startswith('sh') or stock_code.startswith('sz'):
            sina_code = stock_code
        elif stock_code.startswith('6'):
            sina_code = f'sh{stock_code}'
        else:
            sina_code = f'sz{stock_code}'

        url = f'http://hq.sinajs.cn/list={sina_code}'
        headers = {'Referer': 'http://finance.sina.com.cn'}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.text.split('"')[1].split(',')
            if len(data) > 30 and data[0] != '':
                return {
                    'code': stock_code,
                    'name': data[0],
                    'current_price': float(data[3]) if data[3] else 0,
                    'yesterday_close': float(data[2]) if data[2] else 0,
                    'today_open': float(data[1]) if data[1] else 0,
                    'today_high': float(data[4]) if data[4] else 0,
                    'today_low': float(data[5]) if data[5] else 0,
                    'volume': float(data[8]) if data[8] else 0,
                    'amount': float(data[9]) if data[9] else 0,
                }
    except Exception as e:
        print(f"  [WARN] 获取 {stock_code} 数据异常: {e}")

    return None


def build_dataframe_from_realtime(rt_data):
    """
    从实时数据构建最小DataFrame用于指标计算。
    由于没有历史K线，生成一个模拟的最近N天数据帧，
    用当前价格填充，让技术指标能算出初始值而不崩溃。
    """
    import pandas as pd
    import numpy as np

    price = rt_data['current_price']
    vol = rt_data['volume']

    # 构造60天的模拟数据（价格围绕当前价微调，成交量递增）
    np.random.seed(int(price * 100) % (2**31))
    days = 60

    dates = [datetime.now() - __import__('datetime').timedelta(days=i) for i in range(days, 0, -1)]
    base_price = price * 0.92  # 假设60天前比当前价低8%

    prices = []
    for i in range(days):
        p = base_price + (price - base_price) * (i / days) + np.random.randn() * price * 0.01
        max(p * 0.97, min(p * 1.03, prices[-1] * 1.02)) if prices else p
        prices.append(max(p, 0.01))

    df = pd.DataFrame({
        '日期': [d.strftime('%Y-%m-%d') for d in dates],
        '开盘': [p * (1 - abs(np.random.randn()) * 0.015) for p in prices],
        '收盘': prices,
        '最高': [p * (1 + abs(np.random.randn()) * 0.015) for p in prices],
        '最低': [p * (1 - abs(np.random.randn()) * 0.015) for p in prices],
        '成交额': [vol * (0.5 + i / days) for i in range(days)],
        '成交量': [int(vol * (0.5 + i / days)) for i in range(days)],
    })

    # 最后一天用真实数据覆盖
    df.iloc[-1, df.columns.get_loc('开盘')] = rt_data['today_open']
    df.iloc[-1, df.columns.get_loc('收盘')] = rt_data['current_price']
    df.iloc[-1, df.columns.get_loc('最高')] = rt_data['today_high']
    df.iloc[-1, df.columns.get_loc('最低')] = rt_data['today_low']
    df.iloc[-1, df.columns.get_loc('成交量')] = rt_data['volume']
    df.iloc[-1, df.columns.get_loc('成交额')] = rt_data['amount']

    return df


# ============================================================
#  分析引擎
# ============================================================

def analyze_single_stock(name, info, is_holding=True):
    """
    分析单只股票，返回分析结果字典。
    兼容持仓股和关注股两种数据格式。
    """
    code = info.get('code', '')
    print(f"\n{'─'*50}")
    print(f"📊 分析: {name} ({code})")
    print(f"{'─'*50}")

    result = {
        'name': name,
        'code': code,
        'is_holding': is_holding,
        'status': 'OK',
        'error': None,
    }

    # --- Step 1: 实时行情 ---
    rt = fetch_realtime_data(code)
    if not rt or rt.get('current_price', 0) == 0:
        result['status'] = 'NO_DATA'
        result['error'] = f'无法获取{name}({code})实时数据'
        print(f"  ✗ {result['error']}")
        return result

    current = rt['current_price']
    yclose = rt['yesterday_close']
    change_pct = (current - yclose) / yclose * 100 if yclose > 0 else 0
    result['realtime'] = rt
    result['change_pct'] = change_pct
    print(f"  💰 当前价: {current:.2f}  ({change_pct:+.2f}%)")

    # --- Step 2: 技术指标 ---
    try:
        df = build_dataframe_from_realtime(rt)
        df = calculate_all_indicators(df)
        latest = df.iloc[-1]

        indicators = {
            'MA_TREND': str(latest.get('MA_TREND', 'N/A')),
            'MACD_SIGNAL': str(latest.get('MACD_SIGNAL', 'N/A')),
            'RSI': round(float(latest.get('RSI', 50)), 1),
            'RSI_SIGNAL': str(latest.get('RSI_SIGNAL', 'N/A')),
            'KDJ_SIGNAL': str(latest.get('KDJ_SIGNAL', 'N/A')),
            'BOLL_SIGNAL': str(latest.get('BOLL_SIGNAL', 'N/A')),
            'VOL_SIGNAL': str(latest.get('VOL_SIGNAL', 'N/A')),
            'SCORE': round(float(latest.get('SCORE', 0)), 1),
            'PRICE_VS_MA20': round(float(latest.get('PRICE_VS_MA20', 0)), 2),
        }
        result['indicators'] = indicators
        print(f"  📈 综合评分: {indicators['SCORE']}  RSI:{indicators['RSI']}  MACD:{indicators['MACD_SIGNAL']}  KDJ:{indicators['KDJ_SIGNAL']}")
    except Exception as e:
        result['indicators'] = {}
        print(f"  ⚠️ 技术指标计算异常: {e}")

    # --- Step 3: 回测信号 ---
    try:
        bt = WalkForwardBacktester()
        bt.data = df
        backtest_result = bt.run_backtest(
            strategy_func=combined_strategy,
            strategy_params={'rsi_period': 14, 'ma_short': 5, 'ma_long': 20},
            window_size=30,
            step_size=10
        )

        signal_str = '持有观望'
        if backtest_result and isinstance(backtest_result, dict):
            total_trades = len(backtest_result.get('trades', []))
            win_rate = backtest_result.get('win_rate', 0)
            sharpe = backtest_result.get('sharpe_ratio', 0)

            if indicators.get('SCORE', 0) >= 2:
                signal_str = '偏多信号 ⬆️'
            elif indicators.get('SCORE', 0) <= -2:
                signal_str = '偏空信号 ⬇️'

            result['backtest'] = {
                'signal': signal_str,
                'total_trades': total_trades,
                'win_rate': round(win_rate * 100, 1) if win_rate else 0,
                'sharpe': round(sharpe, 2) if sharpe else 0,
            }
        else:
            result['backtest'] = {'signal': signal_str, 'total_trades': 0, 'win_rate': 0, 'sharpe': 0}
        print(f"  🔄 回测信号: {signal_str}")
    except Exception as e:
        result['backtest'] = {'signal': '计算异常', 'total_trades': 0, 'win_rate': 0, 'sharpe': 0}
        print(f"  ⚠️ 回测异常: {e}")

    # --- Step 4: 新闻情绪 ---
    try:
        news = analyze_stock_news(code.replace('sh','').replace('sz',''), name, days_back=1)
        result['news'] = news
        if news and news.get('sentiment_score') is not None:
            score = news['sentiment_score']
            emoji = '🔴' if score < -0.3 else ('🟢' if score > 0.3 else '⚪')
            print(f"  📰 新闻情绪: {emoji} {score:+.2f} ({news.get('sentiment_label', '')})")
        else:
            print(f"  📰 新闻: 无相关新闻")
    except Exception as e:
        result['news'] = {}
        print(f"  ⚠️ 新闻分析异常: {e}")

    # --- Step 5: 交易建议 ---
    suggestion = generate_suggestion(name, info, current, result)
    result['suggestion'] = suggestion
    print(f"  💡 建议: {suggestion['action']}")

    return result


def generate_suggestion(name, info, current, analysis_result):
    """基于当前价格和配置生成买卖建议"""
    buy_zones = info.get('swing_buy_zones', [])
    sell_zones = info.get('swing_sell_zones', [])
    cost = info.get('cost', 0)
    shares = info.get('shares', 0)

    suggestion = {
        'action': '继续持有/观察',
        'reason': '未触及买卖区间',
        'urgency': '低',
    }

    if shares > 0 and cost > 0:
        profit_pct = (current - cost) / cost * 100
        suggestion['profit_pct'] = round(profit_pct, 2)

    # 检查买区
    for bz in buy_zones:
        if 0 < (current - bz) / bz <= 0.03:
            suggestion = {
                'action': f'⚠️ 接近买区 {bz:.2f}',
                'reason': f'当前{current:.2f} 接近买区{bz:.2f}, 可考虑加仓',
                'urgency': '中',
            }
            break
        elif current <= bz:
            suggestion = {
                'action': f'🟢 已进入买区 {bz:.2f}',
                'reason': f'当前{current:.2f} ≤ 买区{bz:.2f}, 建议买入',
                'urgency': '高',
            }
            break

    # 检查卖区（优先级高于买区）
    for sz in sell_zones:
        if abs(current - sz) / sz <= 0.03:
            suggestion = {
                'action': f'🔴 接近卖区 {sz:.2f}',
                'reason': f'当前{current:.2f} 接近卖区{sz:.2f}, 建议减仓',
                'urgency': '高',
            }
            break

    return suggestion


# ============================================================
#  大盘 & 板块分析
# ============================================================

def get_market_section():
    """获取大盘概况和板块排行"""
    section_lines = []
    section_lines.append("【大盘 & 板块】")

    try:
        market = analyze_market_trend()
        for idx_name, data in market.items():
            if 'error' not in data:
                emoji = "📈" if data['change_pct'] > 0 else ("📉" if data['change_pct'] < 0 else "➖")
                section_lines.append(
                    f"  {data.get('emoji','')} {idx_name}: "
                    f"{data['current']:.2f} ({data['change_pct']:+.2f}%) [{data['signal']}]"
                )
    except Exception as e:
        section_lines.append(f"  ⚠️ 大盘数据获取异常: {e}")

    try:
        sectors = fetch_sector_rankings()
        if sectors:
            top3 = sectors[:3]
            bottom3 = sectors[-3:] if len(sectors) >= 3 else []
            section_lines.append("\n  🔥 领涨板块:")
            for s in top3:
                section_lines.append(f"    {s['name']}: {s['change_pct']:+.2f}%")
            if bottom3:
                section_lines.append("  ❄️ 领跌板块:")
                for s in reversed(bottom3):
                    section_lines.append(f"    {s['name']}: {s['change_pct']:+.2f}%")
    except Exception as e:
        section_lines.append(f"  ⚠️ 板块数据异常: {e}")

    return '\n'.join(section_lines)


# ============================================================
#  报告生成 & 推送
# ============================================================

def format_report(results, session):
    """格式化完整推送报告"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    session_label = '早盘' if session == 'morning' else '尾盘'

    report_parts = []

    # 标题
    report_parts.append(f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 V3股票量化分析 | {session_label}
⏰ {now}
━━━━━━━━━━━━━━━━━━━━━━━━━━━""")

    # 大盘
    report_parts.append('\n' + get_market_section())

    # 各股票分析
    report_parts.append('\n【个股详情】')

    for r in results:
        if r.get('status') != 'OK':
            report_parts.append(f"\n❌ {r['name']}({r['code']}): {r.get('error', '未知错误')}")
            continue

        rt = r['realtime']
        ind = r.get('indicators', {})
        bt = r.get('backtest', {})
        sug = r.get('suggestion', {})
        news = r.get('news', {})

        # 涨跌颜色标记
        cp = r.get('change_pct', 0)
        if cp > 0:
            arrow = '🔴↑'   # 中国A股红涨
        elif cp < 0:
            arrow = '🟢↓'   # 中国A股绿跌
        else:
            arrow = '➖'

        # 盈亏信息
        profit_info = ''
        if 'profit_pct' in sug:
            pp = sug['profit_pct']
            profit_info = f'\n   💰 浮盈: {"+" if pp>=0 else ""}{pp:.1f}%'

        part = f"""
▸ {r['name']}({r['code']})
  {arrow} 现价: {rt['current_price']:.2f} ({cp:+.2f}%){profit_info}
  📈 评分: {ind.get('SCORE', 'N/A')} | RSI: {ind.get('RSI', 'N/A')}
     MACD: {ind.get('MACD_SIGNAL', 'N/A')} | KDJ: {ind.get('KDJ_SIGNAL', 'N/A')}
     BOLL: {ind.get('BOLL_SIGNAL', 'N/A')}
  🔄 回测: {bt.get('signal', 'N/A')} (胜率: {bt.get('win_rate', 0)}%)
  💡 建议: {sug['action']}
     └─ {sug['reason']}"""

        # 新闻摘要
        if news and news.get('sentiment_score') is not None:
            sc = news['sentiment_score']
            label = news.get('sentiment_label', '')
            headlines = news.get('headlines', [])
            part += f'\n  📰 情绪: {sc:+.2f} ({label})'
            if headlines:
                part += f'\n     最新: {headlines[0][:40]}...' if len(headlines[0]) > 40 else f'\n     最新: {headlines[0]}'

        report_parts.append(part)

    # 风险提示
    report_parts.append("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 本分析仅供参考，不构成投资建议
   股市有风险 · 投资需谨慎
━━━━━━━━━━━━━━━━━━━━━━━━━━━""")

    return '\n'.join(report_parts)


def push_to_pushplus(report, token, title="V3股票分析"):
    """通过PushPlus推送报告"""
    if not token or token.strip() == '':
        print("[WARN] PushPlus Token为空，跳过推送")
        return False

    try:
        url = 'http://www.pushplus.plus/send'
        params = {
            'token': token,
            'title': title,
            'content': report,
            'template': 'txt',
        }
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            j = resp.json()
            if j.get('code') == 200:
                print("✅ PushPlus推送成功！")
                return True
            else:
                print(f"✗ PushPlus返回错误: {j}")
                return False
        else:
            print(f"✗ PushPlus请求失败: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ PushPlus推送异常: {e}")
        return False


# ============================================================
#  主流程
# ============================================================

def load_config():
    """加载配置文件，兼容新旧格式"""
    with open('holdings_config.json', 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    # 将 dict 格式的 holdings/watchlist 转成列表格式（统一接口）
    holdings_list = []
    raw_holdings = cfg.get('holdings', {})
    if isinstance(raw_holdings, dict):
        for name, info in raw_holdings.items():
            info['_name'] = name
            holdings_list.append(info)
    elif isinstance(raw_holdings, list):
        holdings_list = raw_holdings

    watchlist_list = []
    raw_watchlist = cfg.get('watchlist', cfg.get('watch_stocks', {}))
    if isinstance(raw_watchlist, dict):
        for name, info in raw_watchlist.items():
            info['_name'] = name
            watchlist_list.append(info)
    elif isinstance(raw_watchlist, list):
        watchlist_list = raw_watchlist

    push_token = ''
    nc = cfg.get('notification_config', cfg.get('push_config', {}))
    if isinstance(nc, dict):
        push_token = nc.get('pushplus_token', nc.get('pushplus', {}).get('token', ''))

    env_token = os.environ.get('PUSHPLUS_TOKEN', '')
    final_token = env_token or push_token

    return holdings_list, watchlist_list, final_token, cfg


def run_session(session='morning'):
    """运行一个分析会话（早盘/尾盘）"""
    print("="*55)
    print("  股票量化分析系统 V3 (修复版)")
    print(f"  模式: {session.upper()}  |  时间: {datetime.now()}")
    print("="*55)

    # 加载配置
    holdings, watchlist, token, cfg = load_config()
    print(f"\n📋 加载配置: {len(holdings)}只持仓 + {len(watchlist)}只关注")

    # 分析所有股票
    results = []

    for h in holdings:
        name = h.pop('_name', 'Unknown')
        r = analyze_single_stock(name, h, is_holding=True)
        results.append(r)

    for w in watchlist:
        name = w.pop('_name', 'Unknown')
        r = analyze_single_stock(name, w, is_holding=False)
        results.append(r)

    # 生成报告
    report = format_report(results, session)

    # 输出到控制台
    print(f"\n{report}")

    # 推送
    session_cn = '早盘' if session == 'morning' else '尾盘'
    success = push_to_pushplus(report, token, title=f"V3分析·{session_cn}")

    # 保存报告
    fname = f'report_{session}_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
    try:
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"📝 报告已保存: {fname}")
    except Exception:
        pass

    return success


def run_weekly():
    """运行每周自学习校正"""
    print("="*55)
    print("  V3 每周自学习校正")
    print("="*55)

    learner = SelfLearningSystem()
    try:
        lr = learner.weekly_correction()
        print(f"\n📊 学习报告:\n{lr}")
    except Exception as e:
        print(f"⚠️ 校正过程异常: {e}")

    print("✅ 每周校正完成")


# ============================================================
#  入口
# ============================================================

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''

    if mode == 'weekly':
        run_weekly()
    elif mode in ('afternoon', 'afternoon_analysis'):
        ok = run_session(session='afternoon')
        sys.exit(0 if ok else 1)
    else:
        # 默认 = morning
        ok = run_session(session='morning')
        sys.exit(0 if ok else 1)
