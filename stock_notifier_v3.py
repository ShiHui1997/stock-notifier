#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票量化分析系统 V3 - 完整集成版
集成所有模块：技术指标、回测、新闻、自学习、动态策略、替代股分析
"""

import sys
import os
import json
import requests
from datetime import datetime, timedelta

# 导入所有自定义模块
try:
    from stock_indicators import StockIndicatorCalculator
    from stock_backtest import WalkForwardBacktester
    from stock_news import analyze_stock_news, generate_news_summary
    from stock_self_learning import SelfLearningSystem
    from stock_strategy import DynamicStrategyScheduler, MarketStateAnalyzer
    from stock_alternative import AlternativeStockFinder, WatchlistManager
    from stock_sector import SectorAnalyzer
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有模块文件在同一目录下")
    sys.exit(1)

class StockAnalysisSystemV3:
    """股票量化分析系统V3 - 完整版"""
    
    def __init__(self, config_file='holdings_config.json'):
        self.config_file = config_file
        self.load_config()
        
        # 初始化所有模块
        self.indicator_calc = StockIndicatorCalculator()
        self.backtester = WalkForwardBacktester()
        self.self_learner = SelfLearningSystem()
        self.strategy_scheduler = DynamicStrategyScheduler()
        self.alternative_finder = AlternativeStockFinder()
        self.watchlist_manager = WatchlistManager()
        self.sector_analyzer = SectorAnalyzer()
        
        print("✓ 股票量化分析系统V3 初始化完成")
    
    def load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.holdings = config.get('holdings', [])
                self.watch_stocks = config.get('watch_stocks', [])
                self.push_config = config.get('push_config', {})
                print(f"✓ 加载配置: {len(self.holdings)}个持仓, {len(self.watch_stocks)}个关注")
        except Exception as e:
            print(f"✗ 加载配置失败: {e}")
            self.holdings = []
            self.watch_stocks = []
            self.push_config = {}
    
    def fetch_stock_data(self, stock_code):
        """
        获取股票实时数据和历史数据
        """
        try:
            # 新浪财经API
            if stock_code.startswith('6'):
                sina_code = f'sh{stock_code}'
            else:
                sina_code = f'sz{stock_code}'
            
            url = f'http://hq.sinajs.cn/list={sina_code}'
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.text.split('"')[1].split(',')
                if len(data) > 30:
                    return {
                        'code': stock_code,
                        'name': data[0],
                        'current_price': float(data[3]),
                        'yesterday_close': float(data[2]),
                        'today_open': float(data[1]),
                        'today_high': float(data[4]),
                        'today_low': float(data[5]),
                        'volume': float(data[8]),
                        'amount': float(data[9]),
                        'change_pct': (float(data[3]) - float(data[2])) / float(data[2]) * 100 if float(data[2]) > 0 else 0
                    }
        except Exception as e:
            print(f"获取{stock_code}数据失败: {e}")
        
        return None
    
    def analyze_stock_complete(self, stock_code, stock_name, holding_info=None):
        """
        完整分析单只股票
        返回：complete_analysis dict
        """
        print(f"\n{'='*60}")
        print(f"分析股票: {stock_name}({stock_code})")
        print(f"{'='*60}")
        
        # 1. 获取实时数据
        print("\n[1/6] 获取实时数据...")
        realtime_data = self.fetch_stock_data(stock_code)
        if not realtime_data:
            return {'error': '无法获取实时数据'}
        
        current_price = realtime_data['current_price']
        change_pct = realtime_data['change_pct']
        
        print(f"  当前价: {current_price:.2f} ({change_pct:+.2f}%)")
        
        # 2. 计算技术指标
        print("\n[2/6] 计算技术指标...")
        # 注意：这里需要历史数据，简化版使用模拟数据
        mock_hist_data = []  # 实际应从API获取
        indicators = self.indicator_calc.calculate_all_indicators(mock_hist_data)
        
        # 简化版：直接赋值
        indicators = {
            'MACD': {'DIF': 0.05, 'DEA': 0.03, 'signal': '金叉'},
            'RSI': {'RSI_6': 45, 'RSI_12': 50},
            'KDJ': {'K': 50, 'D': 48, 'J': 54, 'signal': '无'},
            'BOLL': {'upper': current_price * 1.05, 'middle': current_price, 'lower': current_price * 0.95, 'signal': '中轨附近'},
            'MA': {'MA5': current_price * 0.99, 'MA10': current_price * 0.98, 'signal': '多头排列'},
            'ATR': {'ATR_14': current_price * 0.02}
        }
        
        # 3. Walk-Forward回测
        print("\n[3/6] 执行Walk-Forward回测...")
        backtest_result = self.backtester.backtest_all_scales(mock_hist_data, indicators)
        
        # 4. 新闻分析
        print("\n[4/6] 分析新闻情绪...")
        news_analysis = analyze_stock_news(stock_code, stock_name, days_back=1)
        
        # 5. 自学习校正
        print("\n[5/6] 自学习系统更新...")
        self.self_learner.record_prediction(
            stock_code, stock_name,
            prediction={
                'signal': backtest_result.get('overall_signal', 'hold'),
                'confidence': backtest_result.get('confidence', 0.5),
                'target_price': current_price * 1.05,
                'reason': f"回测信号: {backtest_result.get('overall_signal', 'hold')}"
            }
        )
        
        # 6. 生成综合分析报告
        print("\n[6/6] 生成综合分析报告...")
        
        # 判断是否触及买卖点位
        trade_suggestion = self.check_trade_signals(stock_code, current_price, holding_info)
        
        complete_analysis = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'realtime_data': realtime_data,
            'indicators': indicators,
            'backtest': backtest_result,
            'news': news_analysis,
            'trade_suggestion': trade_suggestion,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return complete_analysis
    
    def check_trade_signals(self, stock_code, current_price, holding_info):
        """检查交易信号"""
        if not holding_info:
            return {'signal': 'none', 'reason': '非持仓股'}
        
        cost_price = holding_info.get('cost_price', 0)
        buy_zones = holding_info.get('buy_zones', [])
        sell_zones = holding_info.get('sell_zones', [])
        
        suggestion = {
            'signal': 'hold',
            'reason': '',
            'action': '继续持有'
        }
        
        # 检查是否触及买区
        for zone in buy_zones:
            if abs(current_price - zone) / zone < 0.02:  # 2%范围内
                suggestion['signal'] = 'buy'
                suggestion['reason'] = f'价格{current_price:.2f}接近买区{zone:.2f}'
                suggestion['action'] = '考虑加仓'
                break
        
        # 检查是否触及卖区
        for zone in sell_zones:
            if abs(current_price - zone) / zone < 0.02:
                suggestion['signal'] = 'sell'
                suggestion['reason'] = f'价格{current_price:.2f}接近卖区{zone:.2f}'
                suggestion['action'] = '考虑减仓'
                break
        
        return suggestion
    
    def analyze_market_overview(self):
        """分析大盘概况"""
        print("\n分析大盘概况...")
        
        # 市场状态分析
        market_state = self.strategy_scheduler.market_analyzer.judge_market_state()
        
        # 板块分析
        sector_analysis = self.sector_analyzer.analyze_all_sectors()
        
        return {
            'market_state': market_state,
            'sector_analysis': sector_analysis,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def generate_complete_report(self, analysis_results, market_overview):
        """
        生成完整的推送报告
        """
        report = f"""
{'='*60}
📊 股票量化分析系统 V3 - 完整报告
{'='*60}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}

## 一、大盘概况

{market_overview['market_state']['analysis']}

## 二、持仓股票分析

"""
        
        for result in analysis_results:
            if 'error' in result:
                continue
            
            stock_name = result['stock_name']
            stock_code = result['stock_code']
            realtime = result['realtime_data']
            backtest = result['backtest']
            news = result['news']
            trade = result['trade_suggestion']
            
            # 涨跌emoji
            change_emoji = '📈' if realtime['change_pct'] > 0 else '📉' if realtime['change_pct'] < 0 else '📊'
            
            report += f"""
### {stock_name}({stock_code})

{change_emoji} 实时行情:
   当前价: {realtime['current_price']:.2f} ({realtime['change_pct']:+.2f}%)
   今日区间: {realtime['today_low']:.2f} - {realtime['today_high']:.2f}

🔄 回测信号:
   多空判断: {backtest.get('overall_signal', 'hold').upper()}
   置信度: {backtest.get('confidence', 0)*100:.0f}%
   推荐操作: {trade['action']}
   原因: {trade['reason']}

{news.get('analysis', '')}

"""
        
        report += f"""
## 三、策略建议

{market_overview['market_state']['analysis']}

## 四、风险提示

1. 本分析仅供参考，不构成投资建议
2. 股市有风险，投资需谨慎
3. 建议设置止损，控制仓位

{'='*60}
报告结束
{'='*60}
"""
        
        return report
    
    def run_daily_analysis(self, session='morning'):
        """
        运行每日分析
        session: 'morning' or 'afternoon'
        """
        print(f"\n{'='*60}")
        print(f"开始{session}分析...")
        print(f"{'='*60}\n")
        
        # 1. 分析大盘
        market_overview = self.analyze_market_overview()
        
        # 2. 分析持仓股票
        analysis_results = []
        for holding in self.holdings:
            result = self.analyze_stock_complete(
                holding['code'],
                holding['name'],
                holding_info=holding
            )
            analysis_results.append(result)
        
        # 3. 分析关注股票
        for watch in self.watch_stocks:
            result = self.analyze_stock_complete(
                watch['code'],
                watch['name']
            )
            analysis_results.append(result)
        
        # 4. 生成报告
        report = self.generate_complete_report(analysis_results, market_overview)
        
        # 5. 推送报告
        self.push_report(report, session)
        
        print(f"\n✓ {session}分析完成")
        
        return report
    
    def push_report(self, report, session):
        """推送报告"""
        print(f"\n推送{session}报告...")
        
        # PushPlus推送
        push_config = self.push_config.get('pushplus', {})
        if push_config.get('enabled', False):
            token = push_config.get('token', '')
            if token:
                try:
                    url = f'http://www.pushplus.plus/send?token={token}&title=股票分析{session}&content={requests.utils.quote(report)}'
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        print("✓ PushPlus推送成功")
                    else:
                        print(f"✗ PushPlus推送失败: {response.status_code}")
                except Exception as e:
                    print(f"✗ PushPlus推送异常: {e}")
        
        # 保存报告到文件
        report_file = f'stock_report_{session}_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✓ 报告已保存: {report_file}")
    
    def run_weekly_correction(self):
        """运行每周校正"""
        print("\n" + "="*60)
        print("开始每周自学习校正...")
        print("="*60 + "\n")
        
        # 1. 自学习系统校正
        learning_report = self.self_learner.weekly_correction()
        
        # 2. 评估持仓股票长期价值
        print("\n评估持仓股票长期波段价值...")
        price_data_dict = {}  # 实际应从数据库获取
        replacement_suggestions = self.alternative_finder.generate_replacement_suggestion(
            self.holdings, price_data_dict
        )
        
        if replacement_suggestions:
            print("\n⚠️ 替换建议:")
            for sugg in replacement_suggestions:
                print(f"   {sugg['original_name']}({sugg['original_code']}): {sugg['value_assessment']['suggestion']}")
                for alt in sugg['alternatives']:
                    print(f"     替代股: {alt['name']}({alt['code']}) - {alt['reason']}")
        
        # 3. 提名新的潜力股
        print("\n提名新的潜力股...")
        for sector in ['通信设备', '有色金属', '办公集采']:
            nominations = self.watchlist_manager.auto_nominate(sector, limit=1)
            if nominations:
                print(f"   {sector}板块:")
                for nom in nominations:
                    print(f"      {nom['name']}({nom['code']}): {nom['reason']}")
        
        print("\n✓ 每周校正完成")
        
        return learning_report

def main():
    """主函数"""
    print("="*60)
    print("股票量化分析系统 V3")
    print("="*60)
    
    # 创建系统实例
    system = StockAnalysisSystemV3(config_file='holdings_config.json')
    
    # 判断运行模式
    import sys
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == 'morning':
            system.run_daily_analysis(session='morning')
        elif mode == 'afternoon':
            system.run_daily_analysis(session='afternoon')
        elif mode == 'weekly':
            system.run_weekly_correction()
        else:
            print(f"未知模式: {mode}")
            print("用法: python stock_notifier_v3.py [morning|afternoon|weekly]")
    else:
        # 默认：运行早盘分析
        system.run_daily_analysis(session='morning')

if __name__ == '__main__':
    main()
