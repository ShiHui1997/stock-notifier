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
    from stock_backtest import WalkForwardBacktester, MultiScaleBacktester, simple_moving_average_strategy, combined_strategy
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


# ============================================================
# 历史K线数据获取（多级降级策略）
# 优先级: Yahoo Finance(国际) → akshare(国内) → 东方财富(国内) → 模拟兜底
# ============================================================

def _code_to_yahoo_ticker(stock_code):
    """将内部股票代码转换为Yahoo Finance ticker格式"""
    code = stock_code
    if code.startswith('sz'):
        return f'{code[2:]}.SZ'
    elif code.startswith('sh'):
        return f'{code[2:]}.SH'
    else:
        # 纯数字：6开头=沪市，其他=深市
        if code.startswith('6'):
            return f'{code}.SH'
        else:
            return f'{code}.SZ'


def fetch_history_data_yahoo(stock_code, days=120):
    """
    [数据源1/4] 使用yfinance获取Yahoo Finance历史数据。
    Yahoo Finance是美国服务，GitHub Actions(美国)可稳定访问，不受中国API地域限制。
    返回标准化DataFrame或None。
    """
    import pandas as pd
    import traceback

    try:
        import yfinance as yf
    except ImportError:
        print("  [数据源1-Yahoo] yfinance未安装，跳过")
        return None

    ticker = _code_to_yahoo_ticker(stock_code)
    
    try:
        print(f"  [数据源1-Yahoo] 正在获取 {ticker} 近{days}天历史K线...")
        
        # period映射: days -> yfinance period string
        if days <= 30:
            period = '1mo'
        elif days <= 60:
            period = '2mo'
        elif days <= 120:
            period = '4mo'
        else:
            period = '6mo'
        
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, auto_adjust=True)

        if hist is None or hist.empty:
            print(f"  [数据源1-Yahoo] 返回空数据: {ticker}")
            return None

        # Yahoo返回英文列名 → 标准化为中文列名（与系统一致）
        df = pd.DataFrame({
            '日期': hist.index.strftime('%Y-%m-%d'),
            '开盘': hist['Open'].values,
            '收盘': hist['Close'].values,
            '最高': hist['High'].values,
            '最低': hist['Low'].values,
            '成交量': hist['Volume'].values.astype(int),
            '成交额': (hist['Close'] * hist['Volume']).values,
        })

        # 过滤掉成交量为0的行（可能为休市/异常数据）
        df = df[df['成交量'] > 0].reset_index(drop=True)

        print(f"  ✅ [Yahoo成功] 获取到 {len(df)} 天历史数据 ({df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]})")
        return df

    except Exception as e:
        err_type = type(e).__name__
        print(f"  [数据源1-Yahoo] 失败: {err_type}: {e}")
        # 不打印完整traceback避免刷屏（限流等是常见情况）
        if 'RateLimit' in err_type or 'rate' in str(e).lower():
            print(f"  [数据源1-Yahoo] 提示: Yahoo限流通常是临时的，下次运行会自动恢复")
        else:
            traceback.print_exc()
        return None


def fetch_history_data_akshare(stock_code, days=120):
    """
    [数据源2/4] 使用akshare获取真实历史K线数据。
    返回DataFrame（含日期/开盘/收盘/最高/最低/成交量/成交额），
    或None表示获取失败。注意：GitHub Actions(海外)可能无法访问此数据源。
    """
    import pandas as pd
    import traceback
    try:
        import akshare as ak
    except ImportError:
        print("  [数据源1-akshare] 未安装，跳过")
        return None

    # 清理代码格式（去掉sh/sz前缀）
    code = stock_code
    if code.startswith('sh') or code.startswith('sz'):
        code = code[2:]

    # 计算起始日期（往前推days天）
    from datetime import datetime, timedelta
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    end_date = datetime.now().strftime('%Y%m%d')

    try:
        print(f"  [数据源1-akshare] 正在获取 {code} 近{days}天历史K线...")
        df = ak.stock_zh_a_hist(
            symbol=code,
            period='daily',
            start_date=start_date,
            end_date=end_date,
            adjust='qfq'  # 前复权
        )

        if df is None or df.empty:
            print(f"  [数据源1-akshare] 返回空数据: {code}")
            return None

        # 标准化列名（akshare返回中文列名，与系统一致）
        needed_cols = ['日期', '开盘', '收盘', '最高', '最低', '成交量']
        if not all(c in df.columns for c in needed_cols):
            print(f"  [数据源1-akshare] 列名不匹配，当前列: {list(df.columns)}")
            return None

        # 确保'成交额'列存在（某些股票可能没有）
        if '成交额' not in df.columns:
            df['成交额'] = df['收盘'] * df['成交量']

        print(f"  ✅ [akshare成功] 获取到 {len(df)} 天历史数据 ({df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]})")
        return df

    except Exception as e:
        print(f"  [数据源1-akshare] 失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None


def fetch_history_data_eastmoney(stock_code, days=120):
    """
    [数据源3/4] 使用东方财富HTTP直连API获取历史K线数据。
    使用urllib.request（与新浪实时行情一致），无需额外依赖。
    返回DataFrame或None。
    注意：GitHub Actions(海外)可能无法访问此数据源。
    东方财富K-line API: push2his.eastmoney.com
    深市secid格式: 0.xxxxxx   沪市secid格式: 1.xxxxxx
    klines每行格式: 日期,开盘,收盘,最高,最低,成交量,成交额,...
    """
    import pandas as pd
    import urllib.request
    import traceback

    # 转换为东方财富 secid 格式
    code = stock_code
    if code.startswith('sz'):
        pure_code = code[2:]
        secid = f'0.{pure_code}'  # 深市
    elif code.startswith('sh'):
        pure_code = code[2:]
        secid = f'1.{pure_code}'  # 沪市
    else:
        # 纯数字代码判断
        if code.startswith('6'):
            secid = f'1.{code}'  # 6开头=沪市
        else:
            secid = f'0.{code}'  # 其他=深市
        pure_code = code

    from datetime import datetime, timedelta
    end_date = datetime.now().strftime('%Y%m%d')

    url = (
        f'http://push2his.eastmoney.com/api/qt/stock/kline/get'
        f'?secid={secid}'
        f'&fields1=f1,f2,f3,f4,f5,f6'
        f'&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'
        f'&klt=101'       # 101=日K
        f'&fqt=1'         # 1=前复权
        f'&end={end_date}'
        f'&lmt={days}'     # 返回天数
    )

    headers = {
        'Referer': 'http://quote.eastmoney.com',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        print(f"  [数据源3-东方财富] 正在获取 {pure_code} 近{days}天历史K线...")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8')

        data = json.loads(raw)

        if data.get('rc') != 0 or not data.get('data'):
            print(f"  [数据源2-东方财富] API返回错误: rc={data.get('rc')}, has_data={bool(data.get('data'))}")
            return None

        klines = data['data'].get('klines', [])
        if not klines:
            print(f"  [数据源2-东方财富] K线数据为空（可能停牌或退市）")
            return None

        # 解析kline字符串 → DataFrame
        rows = []
        for line in klines:
            parts = line.split(',')
            if len(parts) >= 7:
                rows.append({
                    '日期': parts[0],
                    '开盘': float(parts[1]),
                    '收盘': float(parts[2]),
                    '最高': float(parts[3]),
                    '最低': float(parts[4]),
                    '成交量': int(float(parts[5])),
                    '成交额': float(parts[6]),
                })

        df = pd.DataFrame(rows)
        print(f"  ✅ [东方财富成功] 获取到 {len(df)} 天历史数据 ({df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]})")
        return df

    except json.JSONDecodeError as e:
        print(f"  [数据源2-东方财富] JSON解析失败（可能被限制）: {e}")
        return None
    except Exception as e:
        print(f"  [数据源2-东方财富] 失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None


def build_dataframe_from_realtime(rt_data):
    """
    [数据源4/4 - 兜底] 从实时数据构建模拟DataFrame。
    仅在前三个真实数据源都失败时才使用！
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

    # --- Step 2: 技术指标（四级数据源降级策略） ---
    # 优先级: 1.Yahoo Finance(国际) → 2.akshare(国内) → 3.东方财富(国内) → 4.模拟兜底
    # Yahoo Finance从GitHub Actions(美国)可稳定访问；中国API在海外可能被封锁
    data_source = '未知'
    try:
        hist_df = None

        # [第1级] Yahoo Finance（国际数据源，GA环境最可靠）
        hist_df = fetch_history_data_yahoo(code, days=120)
        if hist_df is not None:
            data_source = f'{len(hist_df)}天(Yahoo)'

        # [第2级] akshare
        if hist_df is None:
            hist_df = fetch_history_data_akshare(code, days=120)
            if hist_df is not None:
                data_source = f'{len(hist_df)}天(akshare)'

        # [第3级] 东方财富直连
        if hist_df is None:
            hist_df = fetch_history_data_eastmoney(code, days=120)
            if hist_df is not None:
                data_source = f'{len(hist_df)}天(东方财富)'

        # [第4级] 兜底：模拟数据（仅当所有真实数据源都失败）
        if hist_df is None:
            df = build_dataframe_from_realtime(rt)
            df = calculate_all_indicators(df)
            data_source = f'{len(df)}天(⚠️模拟)'
            print(f"  ⚠️ 所有真实数据源均失败，使用{data_source}")
        else:
            # 真实数据：计算指标 + 覆盖最新价格为实时值
            df = calculate_all_indicators(hist_df)
            last_idx = len(df) - 1
            df.iloc[last_idx, df.columns.get_loc('开盘')] = rt['today_open']
            df.iloc[last_idx, df.columns.get_loc('收盘')] = rt['current_price']
            df.iloc[last_idx, df.columns.get_loc('最高')] = rt['today_high']
            df.iloc[last_idx, df.columns.get_loc('最低')] = rt['today_low']
            df.iloc[last_idx, df.columns.get_loc('成交量')] = rt['volume']
            if '成交额' in df.columns:
                df.iloc[last_idx, df.columns.get_loc('成交额')] = rt['amount']
            print(f"  ✅ 使用真实K线: {data_source}")
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

    # --- Step 3: 回测信号（多尺度Walk-Forward） ---
    try:
        bt = WalkForwardBacktester()
        bt.data = df

        # 根据数据量动态调整回测参数
        data_len = len(df)
        if data_len >= 120:
            # 真实数据：多尺度综合回测
            ms = MultiScaleBacktester(
                stock_code=code.replace('sh','').replace('sz',''),
                start_date=df['日期'].iloc[0].replace('-',''),
                end_date=df['日期'].iloc[-1].replace('-','')
            )
            ms.data = df
            ms_result = ms.run_multi_scale_backtest(combined_strategy, {})

            if ms_result:
                # 综合多尺度结果
                win_rates = []
                sharpe_values = []
                total_trades = 0
                for scale_name, scale_data in ms_result.items():
                    if scale_data and 'summary' in scale_data:
                        wr = scale_data['summary'].get('avg_win_rate', 0)
                        sp = scale_data['summary'].get('avg_sharpe', 0)
                        win_rates.append(wr)
                        sharpe_values.append(sp)
                    if scale_data and 'results' in scale_data:
                        for r in scale_data['results']:
                            if 'trades' in r:
                                total_trades += len(r.get('trades', []))

                avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0
                avg_sharpe = sum(sharpe_values) / len(sharpe_values) if sharpe_values else 0

                signal_str = '持有观望'
                score_val = indicators.get('SCORE', 0)
                if avg_win_rate > 55 and score_val >= 1:
                    signal_str = '偏多信号 ⬆️'
                elif avg_win_rate < 45 and score_val <= -1:
                    signal_str = '偏空信号 ⬇️'

                result['backtest'] = {
                    'signal': signal_str,
                    'total_trades': total_trades,
                    'win_rate': round(avg_win_rate, 1),
                    'sharpe': round(avg_sharpe, 2),
                    'data_source': data_source,
                    'scales_tested': list(ms_result.keys()) if ms_result else [],
                }
            else:
                result['backtest'] = {'signal': '持有观望', 'total_trades': 0, 'win_rate': 0, 'sharpe': 0, 'data_source': data_source}
        else:
            # 模拟数据：单窗口快速回测
            backtest_result = bt.run_backtest(
                strategy_func=combined_strategy,
                strategy_params={'rsi_period': 14, 'ma_short': 5, 'ma_long': 20},
                window_size=min(30, data_len // 2),
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
                    'data_source': data_source,
                }
            else:
                result['backtest'] = {'signal': '持有观望', 'total_trades': 0, 'win_rate': 0, 'sharpe': 0, 'data_source': data_source}
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
  🔄 回测: {bt.get('signal', 'N/A')} (胜率: {bt.get('win_rate', 0)}% | 夏普: {bt.get('sharpe', 0)})
     └─ 数据源: {bt.get('data_source', 'N/A')}
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

    # 兜底：从环境变量读取模式（yml可能通过env传参）
    if not mode:
        mode = os.environ.get('PERIOD', os.environ.get('MODE', ''))
        if mode == '尾盘':
            mode = 'afternoon'
        elif mode == '早盘':
            mode = 'morning'

    if mode == 'weekly':
        run_weekly()
    elif mode in ('afternoon', 'afternoon_analysis'):
        ok = run_session(session='afternoon')
        sys.exit(0 if ok else 1)
    else:
        # 默认 = morning
        ok = run_session(session='morning')
        sys.exit(0 if ok else 1)
