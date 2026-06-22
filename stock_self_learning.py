#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自学习校正模块
功能：
1. 记录每日预测结果
2. 对比预测与实际走势
3. 计算预测偏差
4. 自动调整指标权重
5. 生成学习报告
"""

import json
import os
from datetime import datetime, timedelta
import pandas as pd

class SelfLearningSystem:
    """自学习校正系统"""
    
    def __init__(self, data_dir='./data'):
        self.data_dir = data_dir
        self.prediction_log = os.path.join(data_dir, 'predictions.json')
        self.performance_log = os.path.join(data_dir, 'performance.json')
        self.weight_config = os.path.join(data_dir, 'weights.json')
        
        # 确保数据目录存在
        os.makedirs(data_dir, exist_ok=True)
        
        # 加载或初始化权重配置
        self.weights = self._load_weights()
    
    def _load_weights(self):
        """加载指标权重配置"""
        default_weights = {
            'MACD': 1.0,
            'RSI': 0.8,
            'KDJ': 0.7,
            'BOLL': 0.9,
            'MA': 0.8,
            'VOL': 0.6,
            'ATR': 0.5
        }
        
        if os.path.exists(self.weight_config):
            try:
                with open(self.weight_config, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default_weights
        else:
            return default_weights
    
    def _save_weights(self):
        """保存权重配置"""
        with open(self.weight_config, 'w', encoding='utf-8') as f:
            json.dump(self.weights, f, ensure_ascii=False, indent=2)
    
    def record_prediction(self, stock_code, stock_name, prediction, actual=None):
        """
        记录每日预测
        prediction: dict = {
            'signal': 'buy'/'sell'/'hold',
            'confidence': 0.75,
            'target_price': 7.50,
            'reason': 'MACD金叉+RSI超卖'
        }
        """
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        record = {
            'date': date_str,
            'stock_code': stock_code,
            'stock_name': stock_name,
            'prediction': prediction,
            'actual': actual,  # 将在次日更新
            'error': None
        }
        
        # 读取现有记录
        predictions = []
        if os.path.exists(self.prediction_log):
            with open(self.prediction_log, 'r', encoding='utf-8') as f:
                predictions = json.load(f)
        
        # 追加新记录
        predictions.append(record)
        
        # 保存
        with open(self.prediction_log, 'w', encoding='utf-8') as f:
            json.dump(predictions, f, ensure_ascii=False, indent=2)
        
        print(f'✓ 记录 {stock_name} 预测: {prediction["signal"]} (置信度: {prediction["confidence"]})')
    
    def update_actual_result(self, stock_code, actual_price, actual_change):
        """
        更新实际结果（次日调用）
        """
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        if not os.path.exists(self.prediction_log):
            return
        
        with open(self.prediction_log, 'r', encoding='utf-8') as f:
            predictions = json.load(f)
        
        # 找到昨天的预测记录
        for record in predictions:
            if record['date'] == date_str and record['stock_code'] == stock_code:
                record['actual'] = {
                    'price': actual_price,
                    'change': actual_change,
                    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 计算预测误差
                pred = record['prediction']
                if pred['signal'] == 'buy' and actual_change > 0:
                    record['error'] = 'correct'
                elif pred['signal'] == 'sell' and actual_change < 0:
                    record['error'] = 'correct'
                elif pred['signal'] == 'hold' and abs(actual_change) < 1.0:
                    record['error'] = 'correct'
                else:
                    record['error'] = 'wrong'
                
                print(f'✓ 更新 {record["stock_name"]} 实际结果: {actual_change:+.2f}% [{record["error"]}]')
                break
        
        # 保存
        with open(self.prediction_log, 'w', encoding='utf-8') as f:
            json.dump(predictions, f, ensure_ascii=False, indent=2)
    
    def calculate_accuracy(self, days=7):
        """
        计算预测准确率
        """
        if not os.path.exists(self.prediction_log):
            return {'accuracy': 0.0, 'sample_size': 0}
        
        with open(self.prediction_log, 'r', encoding='utf-8') as f:
            predictions = json.load(f)
        
        # 过滤最近N天的记录
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        recent = [p for p in predictions if p['date'] >= cutoff_date and p['error'] is not None]
        
        if not recent:
            return {'accuracy': 0.0, 'sample_size': 0}
        
        correct_count = sum(1 for p in recent if p['error'] == 'correct')
        accuracy = correct_count / len(recent)
        
        return {
            'accuracy': round(accuracy, 3),
            'sample_size': len(recent),
            'correct_count': correct_count,
            'wrong_count': len(recent) - correct_count
        }
    
    def adjust_weights(self):
        """
        根据预测准确率调整指标权重
        """
        accuracy = self.calculate_accuracy(days=30)
        
        if accuracy['sample_size'] < 10:
            print(f'样本量不足({accuracy["sample_size"]}条), 暂不调整权重')
            return
        
        # 读取预测记录，分析各指标的有效性
        if not os.path.exists(self.prediction_log):
            return
        
        with open(self.prediction_log, 'r', encoding='utf-8') as f:
            predictions = json.load(f)
        
        # 简化版：根据整体准确率调整
        if accuracy['accuracy'] > 0.6:
            # 准确率高，略微增加权重
            for key in self.weights:
                self.weights[key] = min(2.0, self.weights[key] * 1.05)
            print(f'✓ 预测准确率{accuracy["accuracy"]:.1%}, 增加指标权重')
        elif accuracy['accuracy'] < 0.4:
            # 准确率低，降低权重
            for key in self.weights:
                self.weights[key] = max(0.3, self.weights[key] * 0.95)
            print(f'⚠ 预测准确率{accuracy["accuracy"]:.1%}, 降低指标权重')
        
        # 保存更新后的权重
        self._save_weights()
    
    def generate_learning_report(self):
        """
        生成自学习报告
        """
        accuracy_7d = self.calculate_accuracy(days=7)
        accuracy_30d = self.calculate_accuracy(days=30)
        
        report = f"""
🤖 自学习系统报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

📊 预测准确率:
   近7天: {accuracy_7d['accuracy']:.1%} ({accuracy_7d['correct_count']}/{accuracy_7d['sample_size']})
   近30天: {accuracy_30d['accuracy']:.1%} ({accuracy_30d['correct_count']}/{accuracy_30d['sample_size']})

⚖️ 当前指标权重:
"""
        
        for indicator, weight in self.weights.items():
            report += f'   {indicator}: {weight:.2f}\n'
        
        report += '\n💡 建议:\n'
        
        if accuracy_30d['accuracy'] < 0.4:
            report += '   - 预测准确率较低,建议人工复核信号\n'
            report += '   - 考虑调整买卖点位或增加过滤条件\n'
        elif accuracy_30d['accuracy'] > 0.6:
            report += '   - 预测准确率良好,可继续信任信号\n'
            report += '   - 建议逐步增加仓位\n'
        else:
            report += '   - 预测准确率一般,建议谨慎操作\n'
        
        return report
    
    def weekly_correction(self):
        """
        每周校正（建议每周日运行）
        """
        print('\n' + '='*60)
        print('开始每周自学习校正...')
        print('='*60 + '\n')
        
        # 1. 调整权重
        self.adjust_weights()
        
        # 2. 生成报告
        report = self.generate_learning_report()
        print(report)
        
        # 3. 保存报告
        report_file = os.path.join(self.data_dir, f'learning_report_{datetime.now().strftime("%Y%m%d")}.txt')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f'\n✓ 校正完成,报告已保存: {report_file}')
        
        return report

def test_self_learning():
    """
    测试自学习系统
    """
    print('=== 测试自学习校正模块 ===\n')
    
    # 创建自学习系统
    sls = SelfLearningSystem(data_dir='./test_data')
    
    # 模拟记录预测
    print('1. 记录预测...')
    sls.record_prediction(
        stock_code='002301',
        stock_name='齐心集团',
        prediction={
            'signal': 'buy',
            'confidence': 0.75,
            'target_price': 6.80,
            'reason': 'MACD金叉+RSI超卖'
        }
    )
    
    # 模拟更新实际结果
    print('\n2. 更新实际结果...')
    sls.update_actual_result(
        stock_code='002301',
        actual_price=6.75,
        actual_change=1.2
    )
    
    # 计算准确率
    print('\n3. 计算准确率...')
    accuracy = sls.calculate_accuracy(days=7)
    print(f'准确率: {accuracy["accuracy"]:.1%}')
    
    # 生成报告
    print('\n4. 生成学习报告...')
    report = sls.generate_learning_report()
    print(report)
    
    print('\n✓ 测试完成')

if __name__ == '__main__':
    test_self_learning()
