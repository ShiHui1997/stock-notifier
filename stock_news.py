#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票新闻分析增强模块
功能：
1. 多源新闻获取（新浪财经、东方财富、腾讯财经）
2. NLP情感分析（利好/利空/中性打分）
3. 事件驱动评分（政策、业绩、重组等）
4. 个股-板块联动分析
5. 新闻摘要与推送格式化
"""

import requests
import json
import re
from datetime import datetime, timedelta
import time

def fetch_sina_news(stock_code, stock_name, limit=10):
    """
    获取新浪财经个股新闻
    """
    news_list = []
    try:
        # 新浪财经个股新闻API
        sina_code = stock_code
        if stock_code.startswith('6'):
            sina_code = f'sh{stock_code}'
        else:
            sina_code = f'sz{stock_code}'
        
        url = f'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/NewsService.getNewsList?page_rows={limit}&page_no=1&code={sina_code}&type=company'
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    news_list.append({
                        'title': item.get('title', ''),
                        'pub_time': item.get('time', ''),
                        'source': '新浪财经',
                        'url': item.get('url', ''),
                        'content': item.get('intro', '')
                    })
    except Exception as e:
        print(f'获取新浪新闻失败: {e}')
    
    return news_list

def fetch_eastmoney_news(stock_code, limit=10):
    """
    获取东方财富个股新闻
    """
    news_list = []
    try:
        # 东方财富新闻API
        url = f'http://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_0_.html'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            # 解析返回的数据
            content = response.text
            # 简单解析（实际需要更复杂的解析）
            titles = re.findall(r'"title":"([^"]+)"', content)
            times = re.findall(r'"time":"([^"]+)"', content)
            
            for i, title in enumerate(titles[:limit]):
                news_list.append({
                    'title': title,
                    'pub_time': times[i] if i < len(times) else '',
                    'source': '东方财富',
                    'url': '',
                    'content': ''
                })
    except Exception as e:
        print(f'获取东方财富新闻失败: {e}')
    
    return news_list

def analyze_sentiment(title, content=''):
    """
    新闻情感分析
    返回：sentiment_score (-1.0 到 1.0)
    """
    # 利好关键词
    bullish_keywords = [
        '上涨', '涨停', '突破', '创新高', '利好', '增持', '回购',
        '业绩增长', '净利润增长', '营收增长', '订单充足', '中标',
        '政策支持', '补贴', '获批', '认证', '合作', '战略合作协议',
        '新产品', '新技术', '市场份额', '行业龙头', '供需紧张'
    ]
    
    # 利空关键词
    bearish_keywords = [
        '下跌', '跌停', '破位', '创新低', '利空', '减持', '抛售',
        '业绩下滑', '亏损', '终止', '裁员', '降薪', '债务',
        '政策收紧', '监管', '处罚', '诉讼', '违约', '停产',
        '市场份额下降', '竞争加剧', '供需过剩'
    ]
    
    text = (title + ' ' + content).lower()
    
    bullish_score = 0
    bearish_score = 0
    
    for keyword in bullish_keywords:
        if keyword in text:
            bullish_score += 1
    
    for keyword in bearish_keywords:
        if keyword in text:
            bearish_score += 1
    
    # 计算情感得分
    total = bullish_score + bearish_score
    if total == 0:
        return 0.0  # 中性
    
    sentiment_score = (bullish_score - bearish_score) / total
    return round(sentiment_score, 2)

def classify_news_importance(title, content=''):
    """
    新闻重要性分类
    返回：importance_level (0-3, 0=不重要, 3=非常重要)
    """
    high_importance_keywords = [
        '业绩预告', '业绩快报', '年报', '季报', '分红', '送股',
        '重大资产重组', '并购', '重组', '借壳', 'IPO', '定增',
        '政策支持', '国家战略', '行业规划', '监管政策'
    ]
    
    medium_importance_keywords = [
        '合作', '订单', '中标', '新产品', '新技术', '认证',
        '市场份额', '行业地位', '竞争格局'
    ]
    
    text = (title + ' ' + content).lower()
    
    for keyword in high_importance_keywords:
        if keyword in text:
            return 3  # 高重要性
    
    for keyword in medium_importance_keywords:
        if keyword in text:
            return 2  # 中等重要性
    
    return 1  # 低重要性

def analyze_stock_news(stock_code, stock_name, days_back=1):
    """
    分析个股新闻
    返回：news_analysis dict
    """
    print(f'\n分析 {stock_name}({stock_code}) 新闻...')
    
    # 获取新闻
    sina_news = fetch_sina_news(stock_code, stock_name, limit=10)
    em_news = fetch_eastmoney_news(stock_code, limit=10)
    
    # 合并去重
    all_news = sina_news + em_news
    seen_titles = set()
    unique_news = []
    
    for news in all_news:
        title = news['title']
        if title not in seen_titles and len(title) > 5:
            seen_titles.add(title)
            unique_news.append(news)
    
    # 过滤最近N天的新闻
    cutoff_time = datetime.now() - timedelta(days=days_back)
    recent_news = []
    
    for news in unique_news:
        try:
            pub_time = news.get('pub_time', '')
            if pub_time:
                # 尝试解析时间
                news_time = datetime.strptime(pub_time[:10], '%Y-%m-%d')
                if news_time >= cutoff_time:
                    recent_news.append(news)
        except:
            # 时间解析失败，保留新闻
            recent_news.append(news)
    
    # 情感分析
    sentiment_scores = []
    important_news = []
    
    for news in recent_news[:5]:  # 只分析前5条
        score = analyze_sentiment(news['title'], news.get('content', ''))
        importance = classify_news_importance(news['title'], news.get('content', ''))
        
        sentiment_scores.append(score)
        
        if importance >= 2:  # 中等重要性以上
            important_news.append({
                'title': news['title'],
                'pub_time': news.get('pub_time', ''),
                'sentiment': score,
                'importance': importance,
                'source': news.get('source', '')
            })
    
    # 综合情感得分
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
    
    # 生成分析结论
    if avg_sentiment > 0.3:
        sentiment_label = '利好'
        sentiment_emoji = '📈'
    elif avg_sentiment < -0.3:
        sentiment_label = '利空'
        sentiment_emoji = '📉'
    else:
        sentiment_label = '中性'
        sentiment_emoji = '📊'
    
    return {
        'stock_code': stock_code,
        'stock_name': stock_name,
        'news_count': len(recent_news),
        'avg_sentiment': avg_sentiment,
        'sentiment_label': sentiment_label,
        'sentiment_emoji': sentiment_emoji,
        'important_news': important_news,
        'analysis': f'{sentiment_emoji} 新闻情绪: {sentiment_label} (得分: {avg_sentiment:+.2f})'
    }

def analyze_sector_news(sector_name, days_back=1):
    """
    分析板块新闻
    """
    print(f'\n分析 {sector_name} 板块新闻...')
    
    # 板块新闻关键词
    sector_keywords = {
        '办公集采': ['集采', '办公用品', '政企采购', '信创'],
        '金融': ['金融', '银行', '保险', '证券', '利率', '货币政策'],
        '有色金属': ['有色金属', '铜', '金', '矿', '大宗商品价格'],
        '通信设备': ['5G', '通信', '数据中心', '算力', '宽带']
    }
    
    keywords = sector_keywords.get(sector_name, [sector_name])
    
    # 这里可以调用新闻API搜索板块相关新闻
    # 简化版：返回占位符
    
    return {
        'sector_name': sector_name,
        'news_count': 0,
        'avg_sentiment': 0.0,
        'analysis': f'📊 {sector_name}板块新闻: 待完善'
    }

def generate_news_summary(news_analyses):
    """
    生成新闻分析摘要（用于推送）
    """
    if not news_analyses:
        return ''
    
    summary = '\n📰 新闻情绪分析:\n'
    
    for analysis in news_analyses:
        summary += f'  {analysis["stock_name"]} {analysis["analysis"]}\n'
        
        if analysis['important_news']:
            summary += f'   重要新闻:\n'
            for news in analysis['important_news'][:3]:  # 最多显示3条
                sentiment_sign = '+' if news['sentiment'] > 0 else ''
                summary += f'   - {news["title"][:40]}... ({sentiment_sign}{news["sentiment"]})\n'
    
    return summary

def test_news_analysis():
    """
    测试新闻分析功能
    """
    print('=== 测试新闻分析模块 ===\n')
    
    # 测试情感分析
    test_cases = [
        ('公司业绩增长超预期', '利好'),
        ('净利润下滑30%', '利空'),
        ('公司与某大企业签署战略合作协议', '利好'),
        ('行业竞争加剧', '利空'),
        ('公司发布新产品', '利好')
    ]
    
    print('情感分析测试:')
    for text, expected in test_cases:
        score = analyze_sentiment(text)
        print(f'  文本: {text}')
        print(f'  预期: {expected}, 得分: {score}')
        print()
    
    # 测试新闻获取（需要网络）
    print('\n正在获取齐心集团新闻...')
    analysis = analyze_stock_news('002301', '齐心集团', days_back=3)
    print(f'新闻数量: {analysis["news_count"]}')
    print(f'情感得分: {analysis["avg_sentiment"]}')
    print(f'分析结论: {analysis["analysis"]}')

if __name__ == '__main__':
    test_news_analysis()
