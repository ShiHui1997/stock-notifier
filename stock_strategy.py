#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态策略调度器
功能：
1. 市场状态判断（牛市/熊市/震荡）
2. 持仓股票波段价值评估
3. 动态策略参数调整
4. 潜力股自动提名
5. 盯盘列表动态增删
"""

import json
import os
from datetime import datetime, timedelta
import requests

class MarketStateAnalyzer:
    """市场状态分析器"""
    
    def __init__(self):
        self.index_codes = {
            'shanghai': 'sh000001',  # 上证指数
            'shenzhen': 'sz399001',  # 深证成指
            'chuangye': 'sz399006'   # 创业板指
        }
    
    def fetch_index_data(self):
        """获取大盘指数数据"""
        indices = {}
        
        for name, code in self.index_codes.items():
            try:
                url = f'http://hq.sinajs.cn/list={code}'
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.text.split('"')[1].split(',')
                    if len(data) > 3:
                        indices[name] = {
                            'current': float(data[3]),
                            'change_pct': float(data[3]) / float(data[2]) - 1 if float(data[2]) > 0 else 0
                        }
            except Exception as e:
                print(f'获取{name}指数失败: {e}')
        
        return indices
    
    def judge_market_state(self):
        """
        判断市场状态
        返回：market_state dict
        """
        indices = self.fetch_index_data()
        
        if not indices:
            return {
                'state': 'unknown',
                'trend': 'neutral',
                'confidence': 0.0,
                'analysis': '无法获取大盘数据'
            }
        
        # 计算平均涨跌幅
        changes = [idx['change_pct'] for idx in indices.values()]
        avg_change = sum(changes) / len(changes)
        
        # 判断市场状态
        if avg_change > 0.02:  # 涨幅>2%
            state = 'bull'
            trend = 'up'
            emoji = '📈'
        elif avg_change < -0.02:  # 跌幅>2%
            state = 'bear'
            trend = 'down'
            emoji = '📉'
        else:
            state = 'sideways'
            trend = 'neutral'
            emoji = '📊'
        
        # 判断趋势强度
        if abs(avg_change) > 0.03:
            strength = '强'
        elif abs(avg_change) > 0.01:
            strength = '中'
        else:
            strength = '弱'
        
        return {
            'state': state,
            'trend': trend,
            'strength': strength,
            'avg_change': avg_change,
            'indices': indices,
            'emoji': emoji,
            'analysis': f'{emoji} 大盘状态: {state.upper()} ({strength})\n   平均涨跌幅: {avg_change:+.2%}'
        }

class BandValueAssessor:
    """波段价值评估器"""
    
    def __init__(self):
        pass
    
    def assess_stock(self, stock_code, stock_name, price_data, indicators):
        """
        评估股票波段价值
        返回：value_score (0-100)
        """
        score = 0
        reasons = []
        
        # 1. 波动率评分 (0-30分)
        if 'volatility' in price_data:
            volatility = price_data['volatility']
            if volatility > 0.05:  # 日波动率>5%
                score += 30
                reasons.append('波动率适中(适合波段)')
            elif volatility > 0.03:
                score += 20
                reasons.append('波动率一般')
            else:
                score += 10
                reasons.append('波动率较低(不适合波段)')
        
        # 2. 趋势强度评分 (0-30分)
        if 'trend_strength' in indicators:
            trend = indicators['trend_strength']
            if trend > 0.7:
                score += 30
                reasons.append('趋势强劲')
            elif trend > 0.4:
                score += 20
                reasons.append('趋势中等')
            else:
                score += 10
                reasons.append('趋势较弱')
        
        # 3. 技术指标信号评分 (0-40分)
        signal_count = 0
        if indicators.get('MACD', 0) > 0:
            signal_count += 1
        if indicators.get('RSI', 50) < 30 or indicators.get('RSI', 50) > 70:
            signal_count += 1
        if indicators.get('BOLL_signal', '') in ['突破下轨', '突破上轨']:
            signal_count += 1
        
        score += signal_count * 13  # 每个信号约13分
        if signal_count > 0:
            reasons.append(f'技术指标信号({signal_count}/3)')
        
        # 生成评级
        if score >= 80:
            rating = '⭐⭐⭐⭐⭐'
            suggestion = '强烈推荐波段操作'
        elif score >= 60:
            rating = '⭐⭐⭐⭐☆'
            suggestion = '适合波段操作'
        elif score >= 40:
            rating = '⭐⭐⭐☆☆'
            suggestion = '可谨慎波段操作'
        elif score >= 20:
            rating = '⭐⭐☆☆☆'
            suggestion = '波段价值较低,建议长持'
        else:
            rating = '⭐☆☆☆☆'
            suggestion = '波段价值很低,建议替换'
        
        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'value_score': score,
            'rating': rating,
            'suggestion': suggestion,
            'reasons': reasons,
            'detail': f'{rating} (得分: {score}/100)\n   {" | ".join(reasons)}\n   💡 {suggestion}'
        }

class DynamicStrategyScheduler:
    """动态策略调度器"""
    
    def __init__(self, config_file='holdings_config.json'):
        self.config_file = config_file
        self.market_analyzer = MarketStateAnalyzer()
        self.value_assessor = BandValueAssessor()
        
    def load_config(self):
        """加载持仓配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'加载配置失败: {e}')
            return None
    
    def adjust_strategy_by_market(self, market_state):
        """
        根据市场状态调整策略参数
        """
        state = market_state['state']
        
        if state == 'bull':
            # 牛市：更激进
            params = {
                'buy_threshold': 0.3,  # 降低买入阈值
                'sell_threshold': 0.8,  # 提高卖出阈值
                'position_ratio': 0.8,   # 提高仓位
                'stop_loss': -0.05,       # 放宽止损
                'take_profit': 0.10        # 提高止盈
            }
            suggestion = '📈 牛市状态: 建议更激进策略,抓住上涨机会'
        elif state == 'bear':
            # 熊市：更保守
            params = {
                'buy_threshold': 0.7,  # 提高买入阈值
                'sell_threshold': 0.4,  # 降低卖出阈值
                'position_ratio': 0.3,   # 降低仓位
                'stop_loss': -0.03,       # 严格止损
                'take_profit': 0.05        # 降低止盈
            }
            suggestion = '📉 熊市状态: 建议更保守策略,保护本金'
        else:
            # 震荡市：中性
            params = {
                'buy_threshold': 0.5,
                'sell_threshold': 0.6,
                'position_ratio': 0.5,
                'stop_loss': -0.04,
                'take_profit': 0.08
            }
            suggestion = '📊 震荡市状态: 建议中性策略,高抛低吸'
        
        return {
            'market_state': state,
            'strategy_params': params,
            'suggestion': suggestion
        }
    
    def nominate_potential_stocks(self, sector_name, exclude_codes=[]):
        """
        提名潜力股
        返回：potential_stocks list
        """
        # 板块对应的潜力股池（简化版，实际需要动态调整）
        stock_pools = {
            '办公集采': [
                {'code': '002301', 'name': '齐心集团', 'reason': '行业龙头'},
                {'code': '603899', 'name': '晨光股份', 'reason': '文具龙头'},
                {'code': '000726', 'name': '鲁泰A', 'reason': '纺织龙头'}
            ],
            '金融': [
                {'code': '000617', 'name': '中油资本', 'reason': '中字头金融'},
                {'code': '601318', 'name': '中国平安', 'reason': '保险龙头'},
                {'code': '600036', 'name': '招商银行', 'reason': '银行龙头'}
            ],
            '有色金属': [
                {'code': '601899', 'name': '紫金矿业', 'reason': '铜金矿龙头'},
                {'code': '600547', 'name': '山东黄金', 'reason': '黄金龙头'},
                {'code': '002460', 'name': '赣锋锂业', 'reason': '锂矿龙头'}
            ],
            '通信设备': [
                {'code': '603690', 'name': '共进股份', 'reason': '宽带设备'},
                {'code': '000063', 'name': '中兴通讯', 'reason': '5G龙头'},
                {'code': '300308', 'name': '中际旭创', 'reason': '光模块龙头'}
            ]
        }
        
        pool = stock_pools.get(sector_name, [])
        
        # 过滤已持有的股票
        potential = [s for s in pool if s['code'] not in exclude_codes]
        
        return potential[:3]  # 返回前3名
    
    def generate_strategy_report(self, holdings, market_state):
        """
        生成策略报告
        """
        report = f"""
🎯 动态策略调度报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

{market_state['analysis']}

"""
        
        # 策略建议
        strategy = self.adjust_strategy_by_market(market_state)
        report += f"{strategy['suggestion']}\n\n"
        
        report += "📊 持仓股票波段价值评估:\n"
        
        for holding in holdings:
            code = holding['code']
            name = holding['name']
            
            # 简化版：实际应该从数据库或API获取
            mock_price_data = {'volatility': 0.04}
            mock_indicators = {'MACD': 1, 'RSI': 45, 'trend_strength': 0.6}
            
            assessment = self.value_assessor.assess_stock(code, name, mock_price_data, mock_indicators)
            report += f"   {name}({code}): {assessment['detail']}\n"
        
        report += "\n💡 操作建议:\n"
        report += "   1. 优先操作波段价值高的股票\n"
        report += "   2. 长期无波段价值的股票建议替换\n"
        report += "   3. 关注板块轮动,及时调整持仓\n"
        
        return report

def test_dynamic_strategy():
    """测试动态策略调度器"""
    print('=== 测试动态策略调度器 ===\n')
    
    scheduler = DynamicStrategyScheduler()
    
    # 测试市场状态判断
    print('1. 判断市场状态...')
    market_state = scheduler.market_analyzer.judge_market_state()
    print(market_state['analysis'])
    
    # 测试策略调整
    print('\n2. 调整策略参数...')
    strategy = scheduler.adjust_strategy_by_market(market_state)
    print(strategy['suggestion'])
    print(f'   策略参数: {strategy["strategy_params"]}')
    
    # 测试潜力股提名
    print('\n3. 提名潜力股...')
    potentials = scheduler.nominate_potential_stocks('通信设备', exclude_codes=['603690'])
    for stock in potentials:
        print(f'   {stock["name"]}({stock["code"]}): {stock["reason"]}')
    
    # 生成报告
    print('\n4. 生成策略报告...')
    mock_holdings = [
        {'code': '002301', 'name': '齐心集团'},
        {'code': '000617', 'name': '中油资本'}
    ]
    report = scheduler.generate_strategy_report(mock_holdings, market_state)
    print(report)
    
    print('\n✓ 测试完成')

if __name__ == '__main__':
    test_dynamic_strategy()
