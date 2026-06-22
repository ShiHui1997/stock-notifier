#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块轮动与大盘分析模块
追踪行业板块热度、大盘趋势、潜力股挖掘
"""

import requests
import json
from datetime import datetime
import pandas as pd

# 板块配置
SECTOR_CONFIG = {
    '齐心集团': {
        'sector': '办公集采/B2B电商',
        'industry_code': 'B2B电商',
        'related_stocks': ['002301', '300959', '603108']
    },
    '中油资本': {
        'sector': '金融/石油',
        'industry_code': '金融',
        'related_stocks': ['000617', '600028', '601857']
    },
    '紫金矿业': {
        'sector': '有色金属/黄金',
        'industry_code': '贵金属',
        'related_stocks': ['601899', '600547', '002155']
    },
    '共进股份': {
        'sector': '通信设备/5G',
        'industry_code': '通信设备',
        'related_stocks': ['603690', '000063', '600498']
    }
}

def fetch_sector_rankings():
    """
    获取行业板块涨跌排行
    
    Returns:
        list: 板块排名列表
    """
    try:
        # 使用东方财富板块数据API
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            'pn': 1,
            'pz': 50,
            'po': 1,
            'np': 1,
            'fltt': 2,
            'invt': 2,
            'fid': 'f3',
            'fs': 'm:90+t:2',  # 行业板块
            'fields': 'f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13'
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'diff' in data['data']:
                sectors = []
                for item in data['data']['diff'][:20]:  # 取前20个板块
                    sectors.append({
                        'name': item.get('f14', ''),
                        'code': item.get('f12', ''),
                        'change_pct': item.get('f3', 0),
                        'lead_stock': item.get('f204', ''),  # 领涨股
                    })
                return sectors
    except Exception as e:
        print(f"获取板块排行失败: {e}")
    
    return []

def analyze_market_trend():
    """
    分析大盘趋势
    
    Returns:
        dict: 大盘分析结果
    """
    indices = {
        'sh000001': ('上证指数', '📊'),
        'sz399001': ('深证成指', '📈'),
        'sz399006': ('创业板指', '🚀'),
        'sh000300': ('沪深300', '🏆')
    }
    
    results = {}
    
    for code, (name, emoji) in indices.items():
        try:
            # 使用新浪API获取指数数据
            url = f"http://hq.sinajs.cn/list={code}"
            response = requests.get(url, timeout=5)
            response.encoding = 'gbk'
            
            if response.status_code == 200:
                data = response.text.split('"')[1].split(',')
                if len(data) > 3:
                    current = float(data[3])
                    prev_close = float(data[2])
                    change_pct = (current - prev_close) / prev_close * 100
                    
                    # 判断趋势
                    trend = '上涨 📈' if change_pct > 0 else '下跌 📉'
                    signal = '多头' if change_pct > 0.5 else '空头' if change_pct < -0.5 else '震荡'
                    
                    results[name] = {
                        'current': current,
                        'change_pct': round(change_pct, 2),
                        'trend': trend,
                        'signal': signal,
                        'emoji': emoji
                    }
        except Exception as e:
            print(f"获取{name}数据失败: {e}")
            results[name] = {'error': str(e)}
    
    return results

def calculate_band_value_score(df, days=20):
    """
    计算波段价值评分
    
    评分标准：
    1. 波动率（越高越好）
    2. 趋势强度（越明显越好）
    3. 成交量活跃度（越高越好）
    
    Returns:
        float: 评分 (0-100)
    """
    if df is None or len(df) < days:
        return 0
    
    recent_data = df.tail(days)
    
    # 1. 波动率评分 (40%)
    returns = recent_data['收盘'].pct_change().dropna()
    volatility = returns.std() * np.sqrt(252) * 100  # 年化波动率
    volatility_score = min(volatility / 40 * 40, 40)  # 最高40分
    
    # 2. 趋势强度评分 (30%)
    # 使用MA5和MA20的距离来衡量趋势强度
    if 'MA5' in recent_data.columns and 'MA20' in recent_data.columns:
        trend_strength = abs(recent_data['MA5'].iloc[-1] - recent_data['MA20'].iloc[-1]) / recent_data['MA20'].iloc[-1] * 100
        trend_score = min(trend_strength / 5 * 30, 30)  # 最高30分
    else:
        trend_score = 0
    
    # 3. 成交量活跃度评分 (30%)
    if '成交量' in recent_data.columns:
        vol_ma = recent_data['成交量'].mean()
        vol_latest = recent_data['成交量'].iloc[-1]
        vol_ratio = vol_latest / vol_ma if vol_ma > 0 else 1
        vol_score = min(vol_ratio * 15, 30)  # 最高30分
    else:
        vol_score = 0
    
    total_score = volatility_score + trend_score + vol_score
    
    return round(total_score, 2)

def find_alternative_stocks(sector_name, current_stock_code, top_n=5):
    """
    在同板块中寻找替代股
    
    Args:
        sector_name: 板块名称
        current_stock_code: 当前股票代码
        top_n: 返回前N只股票
    
    Returns:
        list: 替代股列表
    """
    try:
        # 获取板块成分股
        import akshare as ak
        
        # 根据板块名称获取成分股
        # 这里需要映射到实际的板块代码
        sector_mapping = {
            '通信设备': '通信',
            'B2B电商': '电商',
            '金融': '金融',
            '贵金属': '黄金'
        }
        
        search_key = sector_mapping.get(sector_name, sector_name)
        
        # 搜索同板块股票
        df_sector = ak.stock_board_industry_cons_em(symbol=f"{sector_name}板块")
        
        if df_sector is not None and not df_sector.empty:
            # 排除当前股票
            alternatives = df_sector[df_sector['代码'] != current_stock_code]
            
            # 按涨跌幅排序
            alternatives = alternatives.sort_values('涨跌幅', ascending=False)
            
            result = []
            for _, row in alternatives.head(top_n).iterrows():
                result.append({
                    'code': row['代码'],
                    'name': row['名称'],
                    'price': row['最新价'],
                    'change_pct': row['涨跌幅'],
                    'reason': '同板块领涨股' if row['涨跌幅'] > 0 else '同板块低估值'
                })
            
            return result
    
    except Exception as e:
        print(f"寻找替代股失败: {e}")
    
    return []

def generate_sector_report():
    """
    生成板块分析报告
    
    Returns:
        str: 格式化的报告文本
    """
    report = []
    report.append("📊 板块动态分析")
    report.append("="*50)
    
    # 1. 大盘趋势
    report.append("\n【大盘趋势】")
    market = analyze_market_trend()
    
    if market:
        for index_name, data in market.items():
            if 'error' not in data:
                report.append(f"  {data['emoji']} {index_name}: {data['current']:.2f} ({data['change_pct']:+.2f}%) {data['trend']}")
    
    # 2. 板块热度
    report.append("\n【板块热度TOP10】")
    sectors = fetch_sector_rankings()
    
    if sectors:
        for i, sector in enumerate(sectors[:10], 1):
            report.append(f"  {i}. {sector['name']}: {sector['change_pct']:+.2f}%")
    
    # 3. 持仓板块分析
    report.append("\n【持仓板块分析】")
    for stock_name, config in SECTOR_CONFIG.items():
        report.append(f"  • {stock_name}: {config['sector']}")
    
    return "\n".join(report)

def should_add_to_watchlist(new_stock):
    """
    判断是否应该将新股票加入盯盘列表
    
    Args:
        new_stock: 新股票信息
    
    Returns:
        bool: 是否应该加入
    """
    # 判断条件：
    # 1. 属于热门板块
    # 2. 技术面良好（RSI、MACD等）
    # 3. 成交量活跃
    # 4. 有新闻催化
    
    # 简化版：暂时返回False，需要人工确认
    return False

def should_remove_from_watchlist(stock_name, df, days=30):
    """
    判断是否应该将股票从盯盘列表移除
    
    Args:
        stock_name: 股票名称
        df: 历史数据
        days: 评估周期
    
    Returns:
        tuple: (是否移除, 原因)
    """
    # 计算波段价值评分
    score = calculate_band_value_score(df, days)
    
    if score < 30:
        return True, f"波段价值评分过低({score:.1f}/100)，缺乏交易机会"
    
    # 检查是否长期横盘
    if df is not None and len(df) >= days:
        recent = df.tail(days)
        price_change = (recent['收盘'].iloc[-1] - recent['收盘'].iloc[0]) / recent['收盘'].iloc[0] * 100
        
        if abs(price_change) < 5:
            return True, f"近{days}天涨跌幅仅{price_change:.2f}%，缺乏波动性"
    
    return False, ""


class SectorAnalyzer:
    """板块分析器（类包装）"""

    def __init__(self):
        pass

    def get_sector_rankings(self):
        """获取板块排行"""
        return fetch_sector_rankings()

    def get_market_trend(self):
        """获取大盘趋势"""
        return analyze_market_trend()

    def get_band_value_score(self, df, days=20):
        """计算波段价值评分"""
        return calculate_band_value_score(df, days)

    def find_alternatives(self, sector_name, current_code, top_n=5):
        """寻找替代股"""
        return find_alternative_stocks(sector_name, current_code, top_n)

    def generate_report(self):
        """生成分析报告"""
        return generate_sector_report()

    def should_add(self, new_stock):
        """判断是否加入盯盘"""
        return should_add_to_watchlist(new_stock)

    def should_remove(self, stock_name, df, days=30):
        """判断是否移除盯盘"""
        return should_remove_from_watchlist(stock_name, df, days)


if __name__ == "__main__":
    print("板块分析模块就绪")
    print("\n测试板块报告生成...")
    report = generate_sector_report()
    print(report)
