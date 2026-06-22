#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本 - 验证所有模块功能
"""

import sys
import os

def test_all_modules():
    """测试所有模块"""
    print("="*60)
    print("股票量化分析系统 V3 - 模块测试")
    print("="*60 + "\n")
    
    test_results = {
        'passed': [],
        'failed': [],
        'warnings': []
    }
    
    # 1. 测试技术指标模块
    print("\n[1/7] 测试技术指标模块...")
    try:
        from stock_indicators import StockIndicatorCalculator
        calc = StockIndicatorCalculator()
        print("   ✓ 导入成功")
        test_results['passed'].append('stock_indicators')
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        test_results['failed'].append('stock_indicators')
    
    # 2. 测试回测模块
    print("\n[2/7] 测试回测模块...")
    try:
        from stock_backtest import WalkForwardBacktester
        backtester = WalkForwardBacktester()
        print("   ✓ 导入成功")
        test_results['passed'].append('stock_backtest')
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        test_results['failed'].append('stock_backtest')
    
    # 3. 测试新闻分析模块
    print("\n[3/7] 测试新闻分析模块...")
    try:
        from stock_news import analyze_sentiment, classify_news_importance
        score = analyze_sentiment('公司业绩增长超预期')
        print(f"   ✓ 情感分析测试: {score}")
        test_results['passed'].append('stock_news')
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        test_results['failed'].append('stock_news')
    
    # 4. 测试自学习模块
    print("\n[4/7] 测试自学习模块...")
    try:
        from stock_self_learning import SelfLearningSystem
        sls = SelfLearningSystem(data_dir='./test_data')
        print("   ✓ 初始化成功")
        test_results['passed'].append('stock_self_learning')
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        test_results['failed'].append('stock_self_learning')
    
    # 5. 测试动态策略模块
    print("\n[5/7] 测试动态策略模块...")
    try:
        from stock_strategy import DynamicStrategyScheduler, MarketStateAnalyzer
        scheduler = DynamicStrategyScheduler()
        print("   ✓ 导入成功")
        test_results['passed'].append('stock_strategy')
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        test_results['failed'].append('stock_strategy')
    
    # 6. 测试替代股分析模块
    print("\n[6/7] 测试替代股分析模块...")
    try:
        from stock_alternative import AlternativeStockFinder, WatchlistManager
        finder = AlternativeStockFinder()
        print("   ✓ 导入成功")
        test_results['passed'].append('stock_alternative')
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        test_results['failed'].append('stock_alternative')
    
    # 7. 测试板块分析模块
    print("\n[7/7] 测试板块分析模块...")
    try:
        from stock_sector import SectorAnalyzer
        analyzer = SectorAnalyzer()
        print("   ✓ 导入成功")
        test_results['passed'].append('stock_sector')
    except Exception as e:
        print(f"   ✗ 测试失败: {e}")
        test_results['failed'].append('stock_sector')
    
    # 打印测试结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    print(f"\n✓ 通过: {len(test_results['passed'])}/7")
    for module in test_results['passed']:
        print(f"   - {module}")
    
    if test_results['failed']:
        print(f"\n✗ 失败: {len(test_results['failed'])}/7")
        for module in test_results['failed']:
            print(f"   - {module}")
    
    print("\n" + "="*60)
    
    # 返回测试结果
    if len(test_results['failed']) == 0:
        print("\n🎉 所有模块测试通过！系统可以部署。")
        return True
    else:
        print(f"\n⚠️  有{len(test_results['failed'])}个模块测试失败，请检查。")
        return False

def test_integration():
    """测试集成功能"""
    print("\n" + "="*60)
    print("集成测试")
    print("="*60 + "\n")
    
    try:
        # 测试主程序导入
        print("1. 测试主程序导入...")
        from stock_notifier_v3 import StockAnalysisSystemV3
        print("   ✓ 主程序导入成功")
        
        # 测试配置文件加载
        print("\n2. 测试配置文件加载...")
        if os.path.exists('holdings_config.json'):
            print("   ✓ 配置文件存在")
        else:
            print("   ⚠️  配置文件不存在，将使用默认配置")
        
        print("\n✓ 集成测试基本通过")
        return True
        
    except Exception as e:
        print(f"\n✗ 集成测试失败: {e}")
        return False

if __name__ == '__main__':
    print("\n开始测试股票量化分析系统 V3...\n")
    
    # 模块测试
    module_test_passed = test_all_modules()
    
    # 集成测试
    integration_passed = test_integration()
    
    # 最终结论
    print("\n" + "="*60)
    print("最终结论")
    print("="*60)
    
    if module_test_passed and integration_passed:
        print("\n✓ 所有测试通过！系统已准备就绪。")
        print("\n下一步：")
        print("   1. 部署到GitHub仓库")
        print("   2. 配置GitHub Secrets (PUSH_PLUS_TOKEN)")
        print("   3. 启用GitHub Actions")
        print("   4. 观察推送结果并优化")
    else:
        print("\n⚠️  测试未完全通过，请检查失败模块。")
    
    print("\n" + "="*60 + "\n")
