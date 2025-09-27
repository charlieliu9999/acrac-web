#!/usr/bin/env python3
"""
通过 API 方式测试 RAGAS 评测功能
使用 test_full_data.xlsx 的前5条数据进行同步评测
"""
import requests
import json
import pandas as pd
from pathlib import Path

def main():
    # 读取测试数据
    xlsx_path = Path('test_full_data.xlsx')
    if not xlsx_path.exists():
        print(f'ERROR: Excel file not found: {xlsx_path}')
        return
    
    df = pd.read_excel(xlsx_path).head(5)
    test_cases = []
    for _, row in df.iterrows():
        test_cases.append({
            'question_id': str(row['题号']),
            'clinical_query': str(row['临床场景']),
            'ground_truth': str(row['首选检查项目（标准化）'])
        })
    
    # 构造请求
    payload = {
        'test_cases': test_cases,
        'model_name': 'Qwen/Qwen2.5-32B-Instruct',
        'async_mode': False,  # 同步模式
        'task_name': 'API测试_5条样例'
    }
    
    print('=== 发起 RAGAS 评测 API 请求 ===')
    print(f'测试用例数量: {len(test_cases)}')
    print('模式: 同步评测')
    
    try:
        response = requests.post(
            'http://127.0.0.1:8001/api/v1/ragas/evaluate',
            json=payload,
            timeout=1800  # 30分钟超时
        )
        
        if response.status_code == 200:
            result = response.json()
            print('\n=== 评测结果 ===')
            print(f"状态: {result.get('status')}")
            print(f"任务ID: {result.get('task_id')}")
            print(f"处理时间: {result.get('processing_time', 0):.2f}秒")
            
            if result.get('results'):
                print(f"\n结果数量: {len(result['results'])}")
                for i, res in enumerate(result['results'][:5]):
                    print(f"  {i+1}. {res.get('question_id')} - 成功: {res.get('success')}")
                    if res.get('metrics'):
                        metrics = res['metrics']
                        print(f"     指标: faithfulness={metrics.get('faithfulness', 0):.3f}, "
                              f"answer_relevancy={metrics.get('answer_relevancy', 0):.3f}")
            
            if result.get('summary'):
                print(f"\n汇总指标:")
                summary = result['summary']
                for key, value in summary.items():
                    if isinstance(value, (int, float)):
                        print(f"  {key}: {value:.3f}")
            
            if result.get('error'):
                print(f"\n错误信息: {result['error']}")
                
        else:
            print(f'API 请求失败: {response.status_code}')
            print(f'响应: {response.text}')
            
    except Exception as e:
        print(f'请求异常: {e}')

if __name__ == '__main__':
    main()
