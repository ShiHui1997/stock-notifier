#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Walk-Forward回测引擎
实现多尺度滚动窗口回测、参数优化、性能评估
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

class WalkForwardBacktester:
    """
    Walk-Forward回测引擎
    
    核心思想：
    1. 使用滚动时间窗口进行回测
    2. 在训练窗口优化参数
    3. 在测试窗口验证策略
    4. 滚动前进，避免过拟合
    """
    
    def __init__(self, data=None, initial_capital=100000):
        """
        初始化回测引擎

        Args:
            data: DataFrame with columns ['日期', '开盘', '收盘', '最高', '最低', '成交量']
            initial_capital: 初始资金
        """
        self.data = data
        self.initial_capital = initial_capital
        
    def run_backtest(self, strategy_func, strategy_params, window_size=60, step_size=20):
        """
        运行Walk-Forward回测
        
        Args:
            strategy_func: 策略函数，返回买卖信号
            strategy_params: 策略参数
            window_size: 训练窗口大小（天）
            step_size: 滚动步长（天）
        
        Returns:
            dict: 回测结果
        """
        results = []
        equity_curve = []
        
        # 滚动窗口
        for start in range(0, len(self.data) - window_size, step_size):
            train_start = start
            train_end = start + window_size
            test_start = train_end
            test_end = min(test_start + step_size, len(self.data))
            
            if test_start >= len(self.data):
                break
            
            # 训练窗口
            train_data = self.data.iloc[train_start:train_end]
            
            # 测试窗口
            test_data = self.data.iloc[test_start:test_end]
            
            # 优化参数（在训练窗口）
            optimal_params = self._optimize_parameters(strategy_func, train_data, strategy_params)
            
            # 测试策略（在测试窗口）
            test_result = self._test_strategy(strategy_func, test_data, optimal_params)
            
            results.append({
                'train_period': f"{train_data.iloc[0]['日期']} ~ {train_data.iloc[-1]['日期']}",
                'test_period': f"{test_data.iloc[0]['日期']} ~ {test_data.iloc[-1]['日期']}",
                'optimal_params': optimal_params,
                'returns': test_result['returns'],
                'sharpe': test_result['sharpe'],
                'max_drawdown': test_result['max_drawdown'],
                'win_rate': test_result['win_rate']
            })
            
            equity_curve.extend(test_result['equity_curve'])
        
        return {
            'results': results,
            'equity_curve': equity_curve,
            'summary': self._calculate_summary(results)
        }
    
    def _optimize_parameters(self, strategy_func, train_data, param_grid):
        """
        在训练窗口优化参数
        
        Args:
            strategy_func: 策略函数
            train_data: 训练数据
            param_grid: 参数网格
        
        Returns:
            dict: 最优参数
        """
        best_params = None
        best_sharpe = -np.inf
        
        # 简化版：使用默认参数
        # 完整版应该实现网格搜索或贝叶斯优化
        return param_grid
    
    def _test_strategy(self, strategy_func, test_data, params):
        """
        在测试窗口测试策略
        
        Args:
            strategy_func: 策略函数
            test_data: 测试数据
            params: 策略参数
        
        Returns:
            dict: 测试结果
        """
        # 生成信号
        signals = strategy_func(test_data, params)
        
        # 计算收益
        portfolio_value = self.initial_capital
        shares = 0
        trades = []
        equity_curve = [portfolio_value]
        
        for i in range(1, len(signals)):
            signal = signals.iloc[i]
            price = test_data.iloc[i]['收盘']
            
            if signal['signal'] == 'BUY' and shares == 0:
                # 买入
                shares = portfolio_value / price
                trades.append({'date': test_data.iloc[i]['日期'], 'type': 'BUY', 'price': price})
            elif signal['signal'] == 'SELL' and shares > 0:
                # 卖出
                portfolio_value = shares * price
                shares = 0
                trades.append({'date': test_data.iloc[i]['日期'], 'type': 'SELL', 'price': price})
            
            # 记录权益曲线
            current_value = portfolio_value if shares == 0 else shares * price
            equity_curve.append(current_value)
        
        # 计算性能指标
        equity_series = pd.Series(equity_curve)
        returns = equity_series.pct_change().dropna()
        
        total_return = (equity_curve[-1] - self.initial_capital) / self.initial_capital * 100
        sharpe = self._calculate_sharpe(returns)
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        win_rate = self._calculate_win_rate(trades)
        
        return {
            'returns': total_return,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'equity_curve': equity_curve,
            'trades': trades
        }
    
    def _calculate_sharpe(self, returns, risk_free_rate=0.02/252):
        """计算夏普比率"""
        excess_returns = returns - risk_free_rate
        return np.sqrt(252) * excess_returns.mean() / excess_returns.std()
    
    def _calculate_max_drawdown(self, equity_curve):
        """计算最大回撤"""
        peak = pd.Series(equity_curve).expanding().max()
        drawdown = (pd.Series(equity_curve) - peak) / peak * 100
        return drawdown.min()
    
    def _calculate_win_rate(self, trades):
        """计算胜率"""
        if len(trades) < 2:
            return 0
        
        wins = 0
        total_pairs = 0
        
        for i in range(1, len(trades)):
            if trades[i]['type'] == 'SELL' and trades[i-1]['type'] == 'BUY':
                total_pairs += 1
                if trades[i]['price'] > trades[i-1]['price']:
                    wins += 1
        
        return wins / total_pairs * 100 if total_pairs > 0 else 0
    
    def _calculate_summary(self, results):
        """计算回测汇总统计"""
        if not results:
            return {}
        
        returns = [r['returns'] for r in results]
        sharpes = [r['sharpe'] for r in results]
        drawdowns = [r['max_drawdown'] for r in results]
        win_rates = [r['win_rate'] for r in results]
        
        return {
            'avg_returns': np.mean(returns),
            'avg_sharpe': np.mean(sharpes),
            'avg_max_drawdown': np.mean(drawdowns),
            'avg_win_rate': np.mean(win_rates),
            'best_return': max(returns),
            'worst_return': min(returns),
            'total_periods': len(results)
        }

def simple_moving_average_strategy(data, params):
    """
    简单移动平均策略（示例）
    
    Args:
        data: DataFrame with price data
        params: dict with 'short_window', 'long_window'
    
    Returns:
        DataFrame with signals
    """
    short_window = params.get('short_window', 5)
    long_window = params.get('long_window', 20)
    
    signals = pd.DataFrame(index=data.index)
    signals['signal'] = 'HOLD'
    
    # 计算短期和长期均线
    signals['short_ma'] = data['收盘'].rolling(window=short_window).mean()
    signals['long_ma'] = data['收盘'].rolling(window=long_window).mean()
    
    # 生成信号
    signals['signal'] = np.where(
        signals['short_ma'] > signals['long_ma'],
        'BUY',
        np.where(
            signals['short_ma'] < signals['long_ma'],
            'SELL',
            'HOLD'
        )
    )
    
    return signals

def rsi_strategy(data, params):
    """
    RSI策略（示例）
    
    Args:
        data: DataFrame with RSI indicator
        params: dict with 'oversold', 'overbought'
    
    Returns:
        DataFrame with signals
    """
    oversold = params.get('oversold', 30)
    overbought = params.get('overbought', 70)
    
    signals = pd.DataFrame(index=data.index)
    signals['signal'] = 'HOLD'
    
    # 生成信号
    signals['signal'] = np.where(
        data['RSI'] < oversold,
        'BUY',
        np.where(
            data['RSI'] > overbought,
            'SELL',
            'HOLD'
        )
    )
    
    return signals

def combined_strategy(data, params):
    """
    组合策略：结合多个指标
    
    Args:
        data: DataFrame with all indicators
        params: dict with strategy parameters
    
    Returns:
        DataFrame with signals
    """
    signals = pd.DataFrame(index=data.index)
    signals['signal'] = 'HOLD'
    signals['score'] = 0
    
    # RSI评分
    signals['score'] += np.where(data['RSI'] < 30, 2, 0)
    signals['score'] += np.where(data['RSI'] > 70, -2, 0)
    
    # MACD评分
    signals['score'] += np.where((data['DIF'] > data['DEA']) & (data['MACD'] > 0), 1, 0)
    signals['score'] += np.where((data['DIF'] < data['DEA']) & (data['MACD'] < 0), -1, 0)
    
    # 均线评分
    signals['score'] += np.where(data['MA_TREND'] == '多头', 1, 0)
    signals['score'] += np.where(data['MA_TREND'] == '空头', -1, 0)
    
    # 生成信号
    signals['signal'] = np.where(
        signals['score'] >= 3,
        'BUY',
        np.where(
            signals['score'] <= -2,
            'SELL',
            'HOLD'
        )
    )
    
    return signals

class MultiScaleBacktester:
    """
    多尺度回测器
    在不同时间窗口上运行回测，综合评估策略稳定性
    """
    
    def __init__(self, stock_code, start_date, end_date):
        """
        初始化多尺度回测器
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
        """
        self.stock_code = stock_code
        self.start_date = start_date
        self.end_date = end_date
        self.data = None
    
    def fetch_data(self):
        """获取历史数据"""
        try:
            import akshare as ak
            self.data = ak.stock_zh_a_hist(
                symbol=self.stock_code,
                period='daily',
                start_date=self.start_date,
                end_date=self.end_date,
                adjust='qfq'
            )
            return True
        except Exception as e:
            print(f"获取数据失败: {e}")
            return False
    
    def run_multi_scale_backtest(self, strategy_func, params):
        """
        运行多尺度回测
        
        Returns:
            dict: 各尺度的回测结果
        """
        if self.data is None:
            if not self.fetch_data():
                return None
        
        scales = [
            {'name': '30天', 'window': 30, 'step': 10},
            {'name': '60天', 'window': 60, 'step': 15},
            {'name': '90天', 'window': 90, 'step': 20},
            {'name': '120天', 'window': 120, 'step': 30}
        ]
        
        results = {}
        
        for scale in scales:
            print(f"\n运行 {scale['name']} 尺度回测...")
            
            backtester = WalkForwardBacktester(
                self.data,
                initial_capital=100000
            )
            
            result = backtester.run_backtest(
                strategy_func,
                params,
                window_size=scale['window'],
                step_size=scale['step']
            )
            
            results[scale['name']] = result
        
        return results
    
    def generate_report(self, results):
        """生成回测报告"""
        report = {
            'stock_code': self.stock_code,
            'test_period': f"{self.start_date} ~ {self.end_date}",
            'scales': {}
        }
        
        for scale_name, result in results.items():
            if result and 'summary' in result:
                report['scales'][scale_name] = result['summary']
        
        return report

if __name__ == "__main__":
    print("Walk-Forward回测引擎就绪")
    print("\n使用示例:")
    print("  backtester = MultiScaleBacktester('603690', '20250101', '20250623')")
    print("  results = backtester.run_multi_scale_backtest(combined_strategy, {})")
    print("  report = backtester.generate_report(results)")
