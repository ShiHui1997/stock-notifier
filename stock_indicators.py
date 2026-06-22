#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票技术指标计算模块
计算常用技术指标：MA/MACD/RSI/KDJ/BOLL/ATR/CCI/VOL等
"""

import pandas as pd
import numpy as np


def calculate_all_indicators(df):
    """
    计算所有技术指标
    
    Args:
        df: DataFrame with columns ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额']
    
    Returns:
        df: DataFrame with all technical indicators
    """
    
    # ========== 均线系统 ==========
    df = _calculate_ma(df)
    
    # ========== MACD ==========
    df = _calculate_macd(df)
    
    # ========== RSI ==========
    df = _calculate_rsi(df)
    
    # ========== KDJ ==========
    df = _calculate_kdj(df)
    
    # ========== 布林带 ==========
    df = _calculate_boll(df)
    
    # ========== ATR ==========
    df = _calculate_atr(df)
    
    # ========== CCI ==========
    df = _calculate_cci(df)
    
    # ========== 成交量指标 ==========
    df = _calculate_volume_indicators(df)
    
    # ========== 综合分析评分 ==========
    df = _calculate_score(df)
    
    return df

def _calculate_ma(df):
    """计算均线系统"""
    df['MA5'] = df['收盘'].rolling(window=5).mean()
    df['MA10'] = df['收盘'].rolling(window=10).mean()
    df['MA20'] = df['收盘'].rolling(window=20).mean()
    df['MA60'] = df['收盘'].rolling(window=60).mean()
    
    # 均线趋势
    df['MA_TREND'] = np.where(
        (df['MA5'] > df['MA10']) & (df['MA10'] > df['MA20']),
        '多头',
        np.where(
            (df['MA5'] < df['MA10']) & (df['MA10'] < df['MA20']),
            '空头',
            '震荡'
        )
    )
    
    # 价格相对于均线的位置
    df['PRICE_VS_MA20'] = ((df['收盘'] - df['MA20']) / df['MA20'] * 100).round(2)
    
    return df

def _calculate_macd(df):
    """计算MACD指标"""
    # 快速EMA(12)和慢速EMA(26)
    df['EMA12'] = df['收盘'].ewm(span=12, adjust=False).mean()
    df['EMA26'] = df['收盘'].ewm(span=26, adjust=False).mean()
    
    # DIF = 快速EMA - 慢速EMA
    df['DIF'] = df['EMA12'] - df['EMA26']
    
    # DEA = DIF的9日EMA
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    
    # MACD柱 = (DIF - DEA) * 2
    df['MACD'] = (df['DIF'] - df['DEA']) * 2
    
    # MACD金叉死叉信号
    df['MACD_SIGNAL'] = np.where(
        (df['DIF'] > df['DEA']) & (df['DIF'].shift(1) <= df['DEA'].shift(1)),
        '金叉',
        np.where(
            (df['DIF'] < df['DEA']) & (df['DIF'].shift(1) >= df['DEA'].shift(1)),
            '死叉',
            '持有'
        )
    )
    
    # MACD柱状图方向
    df['MACD_BAR_TREND'] = np.where(
        df['MACD'] > df['MACD'].shift(1),
        '放大',
        '缩小'
    )
    
    return df

def _calculate_rsi(df, period=14):
    """计算RSI指标"""
    delta = df['收盘'].diff()
    
    # 上涨和下跌
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # 平均收益和平均损失
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # 相对强度
    rs = avg_gain / avg_loss
    
    # RSI
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # RSI信号
    df['RSI_SIGNAL'] = np.where(
        df['RSI'] < 30,
        '超卖',
        np.where(
            df['RSI'] > 70,
            '超买',
            '中性'
        )
    )
    
    return df

def _calculate_kdj(df, n=9):
    """计算KDJ指标"""
    # 最低价和最高价的N日滚动
    low_list = df['最低'].rolling(window=n).min()
    high_list = df['最高'].rolling(window=n).max()
    
    # RSV
    rsv = (df['收盘'] - low_list) / (high_list - low_list) * 100
    
    # K值 (RSV的3日EMA)
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    
    # D值 (K值的3日EMA)
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    
    # J值
    df['J'] = 3 * df['K'] - 2 * df['D']
    
    # KDJ信号
    df['KDJ_SIGNAL'] = np.where(
        (df['K'] < 20) & (df['D'] < 20),
        '超卖',
        np.where(
            (df['K'] > 80) & (df['D'] > 80),
            '超买',
            '中性'
        )
    )
    
    # KDJ金叉死叉
    df['KDJ_CROSS'] = np.where(
        (df['K'] > df['D']) & (df['K'].shift(1) <= df['D'].shift(1)),
        '金叉',
        np.where(
            (df['K'] < df['D']) & (df['K'].shift(1) >= df['D'].shift(1)),
            '死叉',
            '持有'
        )
    )
    
    return df

def _calculate_boll(df, period=20, std_dev=2):
    """计算布林带指标"""
    # 中轨 = N日MA
    df['BOLL_MID'] = df['收盘'].rolling(window=period).mean()
    
    # 标准差
    df['BOLL_STD'] = df['收盘'].rolling(window=period).std()
    
    # 上轨和下轨
    df['BOLL_UP'] = df['BOLL_MID'] + (std_dev * df['BOLL_STD'])
    df['BOLL_DOWN'] = df['BOLL_MID'] - (std_dev * df['BOLL_STD'])
    
    # 价格在中轨的位置 (%)
    df['BOLL_POSITION'] = (
        (df['收盘'] - df['BOLL_DOWN']) / 
        (df['BOLL_UP'] - df['BOLL_DOWN']) * 100
    ).round(2)
    
    # 布林带信号
    df['BOLL_SIGNAL'] = np.where(
        df['BOLL_POSITION'] < 20,
        '接近下轨',
        np.where(
            df['BOLL_POSITION'] > 80,
            '接近上轨',
            '中性'
        )
    )
    
    # 布林带宽度 (波动率)
    df['BOLL_WIDTH'] = ((df['BOLL_UP'] - df['BOLL_DOWN']) / df['BOLL_MID'] * 100).round(2)
    
    return df

def _calculate_atr(df, period=14):
    """计算ATR(平均真实波幅)"""
    # 真实波幅TR
    df['TR'] = np.maximum(
        df['最高'] - df['最低'],
        np.maximum(
            abs(df['最高'] - df['收盘'].shift(1)),
            abs(df['最低'] - df['收盘'].shift(1))
        )
    )
    
    # ATR
    df['ATR'] = df['TR'].rolling(window=period).mean()
    
    # ATR占比
    df['ATR_RATIO'] = (df['ATR'] / df['收盘'] * 100).round(2)
    
    return df

def _calculate_cci(df, period=14):
    """计算CCI(商品通道指数)"""
    # 典型价格TP
    df['TP'] = (df['最高'] + df['最低'] + df['收盘']) / 3
    
    # TP的移动平均
    df['TP_MA'] = df['TP'].rolling(window=period).mean()
    
    # 平均绝对偏差
    df['TP_MD'] = abs(df['TP'] - df['TP_MA']).rolling(window=period).mean()
    
    # CCI
    df['CCI'] = (df['TP'] - df['TP_MA']) / (0.015 * df['TP_MD'])
    
    # CCI信号
    df['CCI_SIGNAL'] = np.where(
        df['CCI'] > 100,
        '超买',
        np.where(
            df['CCI'] < -100,
            '超卖',
            '中性'
        )
    )
    
    return df

def _calculate_volume_indicators(df):
    """计算成交量指标"""
    # 成交量MA
    df['VOL_MA5'] = df['成交量'].rolling(window=5).mean()
    df['VOL_MA10'] = df['成交量'].rolling(window=10).mean()
    
    # 量能比
    df['VOL_RATIO'] = (df['成交量'] / df['VOL_MA5']).round(2)
    
    # 量能信号
    df['VOL_SIGNAL'] = np.where(
        df['VOL_RATIO'] > 2,
        '放量',
        np.where(
            df['VOL_RATIO'] < 0.5,
            '缩量',
            '正常'
        )
    )
    
    # 价量关系
    df['PRICE_UP'] = df['收盘'] > df['收盘'].shift(1)
    df['VOL_UP'] = df['成交量'] > df['成交量'].shift(1)
    
    df['PRICE_VOL_SIGNAL'] = np.where(
        (df['PRICE_UP']) & (df['VOL_UP']),
        '价涨量增✅',
        np.where(
            (df['PRICE_UP']) & (~df['VOL_UP']),
            '价涨量缩⚠️',
            np.where(
                (~df['PRICE_UP']) & (df['VOL_UP']),
                '价跌量增🔴',
                '价跌量缩'
            )
        )
    )
    
    return df

def _calculate_score(df):
    """计算综合分析评分"""
    df['SCORE'] = 0
    
    # RSI评分
    df['SCORE'] += np.where(df['RSI'] < 30, 2, 0)
    df['SCORE'] += np.where((df['RSI'] >= 30) & (df['RSI'] < 45), 1, 0)
    df['SCORE'] += np.where(df['RSI'] > 70, -2, 0)
    
    # MACD评分
    df['SCORE'] += np.where((df['DIF'] > df['DEA']) & (df['MACD'] > 0), 1, 0)
    df['SCORE'] += np.where((df['DIF'] > df['DEA']) & (df['MACD'] < 0), 0.5, 0)
    df['SCORE'] += np.where((df['DIF'] < df['DEA']) & (df['MACD'] < 0), -1, 0)
    
    # 均线评分
    df['SCORE'] += np.where(df['MA_TREND'] == '多头', 1, 0)
    df['SCORE'] += np.where(df['MA_TREND'] == '空头', -1, 0)
    
    # 布林带评分
    df['SCORE'] += np.where(df['BOLL_POSITION'] < 20, 1, 0)
    df['SCORE'] += np.where(df['BOLL_POSITION'] > 80, -1, 0)
    
    # KDJ评分
    df['SCORE'] += np.where((df['K'] < 20) & (df['D'] < 20), 1, 0)
    df['SCORE'] += np.where((df['K'] > 80) & (df['D'] > 80), -1, 0)
    
    # 成交量评分
    df['SCORE'] += np.where(df['VOL_RATIO'] > 1.5, 0.5, 0)
    
    return df

def generate_signal(df):
    """
    生成买卖信号
    
    Returns:
        dict: 信号详情
    """
    if df is None or df.empty:
        return None
    
    latest = df.iloc[-1]
    
    signal = {
        'date': latest['日期'],
        'close': latest['收盘'],
        'score': latest['SCORE'],
        'ma_trend': latest['MA_TREND'],
        'macd_signal': latest['MACD_SIGNAL'],
        'rsi_signal': latest['RSI_SIGNAL'],
        'kdj_signal': latest['KDJ_SIGNAL'],
        'boll_signal': latest['BOLL_SIGNAL'],
        'vol_signal': latest['VOL_SIGNAL'],
        'price_vol': latest['PRICE_VOL_SIGNAL'],
    }
    
    # 综合建议
    if signal['score'] >= 3:
        signal['advice'] = '🟢 强烈买入'
        signal['action'] = '可以大仓位买入'
    elif signal['score'] >= 1:
        signal['advice'] = '🟡 可以买入'
        signal['action'] = '可以小仓位试探'
    elif signal['score'] >= -1:
        signal['advice'] = '🟡 观望'
        signal['action'] = '继续观察'
    else:
        signal['advice'] = '🔴 不建议买入'
        signal['action'] = '等待更好时机'
    
    return signal


class StockIndicatorCalculator:
    """技术指标计算器（类包装 - 放在文件末尾）"""
    
    def __init__(self):
        pass
    
    def calculate_all(self, df):
        """计算所有指标（类方法）"""
        return calculate_all_indicators(df)
    
    def generate_signal(self, df):
        """生成买卖信号（类方法）"""
        return generate_signal(df)


if __name__ == "__main__":
    # 测试代码
    print("技术指标计算模块就绪")
    print("主要功能:")
    print("  1. calculate_all_indicators(df) - 计算所有指标")
    print("  2. generate_signal(df) - 生成买卖信号")
    print("  3. StockIndicatorCalculator类 - 面向对象接口")
