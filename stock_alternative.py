#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同板块替代股分析模块
功能：
1. 判断持仓股长期波段价值
2. 同板块替代股筛选
3. 替代股对比分析
4. 自动生成替换建议
5. 盯盘列表动态管理
"""

import json
import os
from datetime import datetime, timedelta
import requests

class AlternativeStockFinder:
    """同板块替代股分析器"""
    
    def __init__(self):
        # 板块分类映射
        self.sector_mapping = {
            '002301': '办公集采',
            '000617': '金融',
            '601899': '有色金属',
            '603690': '通信设备'
        }
        
        # 同板块股票池（简化版，实际应从API动态获取）
        self.sector_stocks = {
            '办公集采': [
                {'code': '002301', 'name': '齐心集团', 'market_cap': 50, 'volatility': 0.04},
                {'code': '603899', 'name': '晨光股份', 'market_cap': 500, 'volatility': 0.03},
                {'code': '000726', 'name': '鲁泰A', 'market_cap': 80, 'volatility': 0.025}
            ],
            '金融': [
                {'code': '000617', 'name': '中油资本', 'market_cap': 1000, 'volatility': 0.02},
                {'code': '601318', 'name': '中国平安', 'market_cap': 8000, 'volatility': 0.015},
                {'code': '600036', 'name': '招商银行', 'market_cap': 12000, 'volatility': 0.018}
            ],
            '有色金属': [
                {'code': '601899', 'name': '紫金矿业', 'market_cap': 3000, 'volatility': 0.035},
                {'code': '600547', 'name': '山东黄金', 'market_cap': 800, 'volatility': 0.04},
                {'code': '002460', 'name': '赣锋锂业', 'market_cap': 1500, 'volatility': 0.05}
            ],
            '通信设备': [
                {'code': '603690', 'name': '共进股份', 'market_cap': 80, 'volatility': 0.045},
                {'code': '000063', 'name': '中兴通讯', 'market_cap': 1500, 'volatility': 0.03},
                {'code': '300308', 'name': '中际旭创', 'market_cap': 2000, 'volatility': 0.055}
            ]
        }
    
    def assess_long_term_value(self, stock_code, stock_name, price_data, days=30):
        """
        评估股票长期波段价值
        返回：value_assessment dict
        """
        # 获取历史波动率
        volatility = price_data.get('volatility', 0.0)
        avg_amplitude = price_data.get('avg_amplitude', 0.0)  # 平均振幅
        
        # 评估维度
        scores = {
            'volatility': 0,  # 波动率得分
            'trend': 0,       # 趋势强度得分
            'liquidity': 0,    # 流动性得分
            'sector_outlook': 0 # 板块前景得分
        }
        
        # 1. 波动率评分 (0-40分)
        if volatility >= 0.05:
            scores['volatility'] = 40
        elif volatility >= 0.03:
            scores['volatility'] = 30
        elif volatility >= 0.02:
            scores['volatility'] = 20
        else:
            scores['volatility'] = 10
        
        # 2. 趋势强度评分 (0-30分)
        trend_strength = price_data.get('trend_strength', 0.5)
        scores['trend'] = int(trend_strength * 30)
        
        # 3. 流动性评分 (0-15分)
        avg_volume = price_data.get('avg_volume', 0)
        if avg_volume > 500000000:  # 5亿以上
            scores['liquidity'] = 15
        elif avg_volume > 100000000:  # 1亿以上
            scores['liquidity'] = 10
        elif avg_volume > 50000000:  # 5000万以上
            scores['liquidity'] = 5
        else:
            scores['liquidity'] = 0
        
        # 4. 板块前景评分 (0-15分)
        sector = self.sector_mapping.get(stock_code, '')
        sector_outlook = {
            '办公集采': 10,  # 中等
            '金融': 8,       # 偏低
            '有色金属': 12,   # 中高
            '通信设备': 14    # 高（5G、AI算力）
        }
        scores['sector_outlook'] = sector_outlook.get(sector, 10)
        
        # 总分
        total_score = sum(scores.values())
        
        # 判断是否值得长期关注
        if total_score >= 70:
            value_level = '高'
            suggestion = '强烈推荐继续持有并波段操作'
            action = 'keep'
        elif total_score >= 50:
            value_level = '中'
            suggestion = '可以持有，适度波段操作'
            action = 'keep'
        elif total_score >= 30:
            value_level = '低'
            suggestion = '波段价值较低，建议考虑替换'
            action = 'consider_replace'
        else:
            value_level = '很低'
            suggestion = '无波段价值，强烈建议替换'
            action = 'replace'
        
        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'total_score': total_score,
            'value_level': value_level,
            'suggestion': suggestion,
            'action': action,
            'scores': scores,
            'detail': f'长期波段价值: {value_level} (得分: {total_score}/100)\n'
                     f'  波动率: {scores["volatility"]}/40 | 趋势: {scores["trend"]}/30\n'
                     f'  流动性: {scores["liquidity"]}/15 | 板块前景: {scores["sector_outlook"]}/15\n'
                     f'💡 {suggestion}'
        }
    
    def find_alternatives(self, stock_code, stock_name, top_n=3):
        """
        寻找同板块替代股
        返回：alternatives list
        """
        # 确定板块
        sector = self.sector_mapping.get(stock_code, '')
        if not sector:
            return []
        
        # 获取同板块股票
        candidates = self.sector_stocks.get(sector, [])
        
        # 过滤自己
        candidates = [s for s in candidates if s['code'] != stock_code]
        
        # 按波动率排序（波动率高的更适合波段）
        candidates.sort(key=lambda x: x['volatility'], reverse=True)
        
        # 返回前N名
        alternatives = []
        for candidate in candidates[:top_n]:
            alternatives.append({
                'code': candidate['code'],
                'name': candidate['name'],
                'volatility': candidate['volatility'],
                'market_cap': candidate['market_cap'],
                'reason': f'同板块({sector})，波动率{candidate["volatility"]:.1%}，适合波段'
            })
        
        return alternatives
    
    def compare_stocks(self, original_code, original_name, alternative_code, alternative_name):
        """
        对比原股票和替代股
        返回：comparison dict
        """
        # 简化版：实际应从API获取详细数据
        comparison = {
            'original': {
                'code': original_code,
                'name': original_name,
                'volatility': 0.02,  # 模拟数据
                'avg_change': 0.5,
                'risk_level': '低'
            },
            'alternative': {
                'code': alternative_code,
                'name': alternative_name,
                'volatility': 0.05,  # 模拟数据
                'avg_change': 1.2,
                'risk_level': '中'
            },
            'conclusion': f'替代股{alternative_name}波动率更高，波段空间更大，建议考虑替换'
        }
        
        return comparison
    
    def generate_replacement_suggestion(self, holdings, price_data_dict):
        """
        生成替换建议
        返回：suggestions list
        """
        suggestions = []
        
        for holding in holdings:
            code = holding['code']
            name = holding['name']
            
            # 评估长期价值
            price_data = price_data_dict.get(code, {})
            assessment = self.assess_long_term_value(code, name, price_data)
            
            # 如果建议替换
            if assessment['action'] in ['consider_replace', 'replace']:
                # 寻找替代股
                alternatives = self.find_alternatives(code, name, top_n=2)
                
                if alternatives:
                    suggestion = {
                        'original_code': code,
                        'original_name': name,
                        'value_assessment': assessment,
                        'alternatives': alternatives,
                        'urgency': 'high' if assessment['action'] == 'replace' else 'medium'
                    }
                    suggestions.append(suggestion)
        
        return suggestions

class WatchlistManager:
    """盯盘列表动态管理器"""
    
    def __init__(self, config_file='holdings_config.json'):
        self.config_file = config_file
        self.alternative_finder = AlternativeStockFinder()
    
    def load_watchlist(self):
        """加载盯盘列表"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('watch_stocks', [])
        except Exception as e:
            print(f'加载盯盘列表失败: {e}')
            return []
    
    def save_watchlist(self, watch_stocks):
        """保存盯盘列表"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            config['watch_stocks'] = watch_stocks
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            print(f'✓ 盯盘列表已更新')
            return True
        except Exception as e:
            print(f'保存盯盘列表失败: {e}')
            return False
    
    def auto_nominate(self, sector_name,limit=2):
        """自动提名潜力股加入盯盘列表"""
        # 获取板块股票池
        sector_stocks = self.alternative_finder.sector_stocks.get(sector_name, [])
        
        # 当前盯盘列表
        current_watch = self.load_watchlist()
        current_codes = [s['code'] for s in current_watch]
        
        # 过滤已盯盘的股票
        new_nominations = []
        for stock in sector_stocks:
            if stock['code'] not in current_codes and stock['volatility'] >= 0.03:
                new_nominations.append({
                    'code': stock['code'],
                    'name': stock['name'],
                    'sector': sector_name,
                    'volatility': stock['volatility'],
                    'reason': f'板块({sector_name})潜力股，波动率{stock["volatility"]:.1%}'
                })
        
        # 按波动率排序
        new_nominations.sort(key=lambda x: x['volatility'], reverse=True)
        
        return new_nominations[:limit]
    
    def auto_remove(self, holdings, price_data_dict):
        """自动提名移除长期无价值的股票"""
        suggestions = []
        
        for holding in holdings:
            code = holding['code']
            name = holding['name']
            
            # 评估价值
            price_data = price_data_dict.get(code, {})
            assessment = self.alternative_finder.assess_long_term_value(code, name, price_data)
            
            # 如果价值很低且已持有较长时间（模拟判断）
            if assessment['total_score'] < 30:
                suggestions.append({
                    'code': code,
                    'name': name,
                    'reason': f'长期波段价值很低(得分: {assessment["total_score"]}/100)',
                    'action': 'remove_from_watchlist'
                })
        
        return suggestions

def test_alternative_analysis():
    """测试替代股分析功能"""
    print('=== 测试同板块替代股分析 ===\n')
    
    finder = AlternativeStockFinder()
    manager = WatchlistManager()
    
    # 测试长期价值评估
    print('1. 评估长期波段价值...')
    mock_price_data = {
        'volatility': 0.02,
        'avg_amplitude': 0.015,
        'trend_strength': 0.3,
        'avg_volume': 50000000
    }
    
    assessment = finder.assess_long_term_value('000617', '中油资本', mock_price_data)
    print(assessment['detail'])
    
    # 测试替代股寻找
    print('\n2. 寻找替代股...')
    alternatives = finder.find_alternatives('000617', '中油资本', top_n=2)
    for alt in alternatives:
        print(f'   {alt["name"]}({alt["code"]}): {alt["reason"]}')
    
    # 测试对比分析
    print('\n3. 对比分析...')
    if alternatives:
        comparison = finder.compare_stocks('000617', '中油资本', 
                                           alternatives[0]['code'], alternatives[0]['name'])
        print(comparison['conclusion'])
    
    # 测试自动提名
    print('\n4. 自动提名潜力股...')
    nominations = manager.auto_nominate('通信设备', limit=2)
    for nom in nominations:
        print(f'   {nom["name"]}({nom["code"]}): {nom["reason"]}')
    
    print('\n✓ 测试完成')

if __name__ == '__main__':
    test_alternative_analysis()
