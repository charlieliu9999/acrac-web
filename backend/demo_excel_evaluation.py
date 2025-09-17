#!/usr/bin/env python3
"""
Excel评测功能完整演示
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import requests
import json
import time
from pathlib import Path

def create_demo_excel():
    """创建演示用的Excel文件"""
    demo_data = {
        '题号': [1, 2, 3, 4, 5],
        '临床场景': [
            '患者，男性，45岁，胸痛3小时，心电图显示ST段抬高，疑似急性心肌梗死',
            '患者，女性，30岁，右下腹痛伴发热，白细胞计数升高，疑似急性阑尾炎',
            '患者，男性，60岁，突发头痛伴恶心呕吐，血压180/110mmHg，疑似脑血管疾病',
            '患者，女性，25岁，咳嗽伴胸痛2周，胸片显示肺部阴影，疑似肺部感染',
            '患者，男性，55岁，腹痛伴黄疸，肝功能异常，疑似胆道疾病'
        ],
        '首选检查项目（标准化）': [
            'CT冠状动脉造影',
            'CT腹部平扫+增强',
            'CT头颅平扫',
            'CT胸部高分辨率扫描',
            'MRCP胆胰管造影'
        ]
    }
    
    df = pd.DataFrame(demo_data)
    excel_file = 'demo_evaluation.xlsx'
    df.to_excel(excel_file, index=False)
    print(f"✅ 创建演示Excel文件: {excel_file}")
    return excel_file

def upload_excel_file(excel_file):
    """上传Excel文件"""
    url = "http://127.0.0.1:8002/api/v1/acrac/excel-evaluation/upload-excel"
    
    try:
        with open(excel_file, 'rb') as f:
            files = {'file': (excel_file, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            response = requests.post(url, files=files)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Excel文件上传成功")
            print(f"  文件名: {result['filename']}")
            print(f"  测试案例数: {result['total_cases']}")
            return result['test_cases']
        else:
            print(f"❌ 上传失败: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 上传异常: {e}")
        return None

def start_evaluation(test_cases, filename):
    """开始评测"""
    url = "http://127.0.0.1:8002/api/v1/acrac/excel-evaluation/start-evaluation"
    
    try:
        # 直接传递test_cases列表，filename作为查询参数
        params = {"filename": filename} if filename else {}
        response = requests.post(url, json=test_cases, params=params)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 评测已开始")
            print(f"  任务ID: {result['task_id']}")
            print(f"  总案例数: {result['total_cases']}")
            return result['task_id']
        else:
            print(f"❌ 开始评测失败: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 开始评测异常: {e}")
        return None

def check_evaluation_status():
    """检查评测状态"""
    url = "http://127.0.0.1:8002/api/v1/acrac/excel-evaluation/evaluation-status"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"❌ 获取状态失败: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 获取状态异常: {e}")
        return None

def get_evaluation_history():
    """获取评测历史"""
    url = "http://127.0.0.1:8002/api/v1/acrac/excel-evaluation/evaluation-history"
    
    try:
        response = requests.get(url, params={'limit': 10, 'offset': 0})
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n📊 评测历史数据 (共{result['total']}条):")
            for item in result['data']:
                print(f"  任务ID: {item['task_id']}")
                print(f"  文件名: {item['filename']}")
                print(f"  问题: {item['question'][:50]}...")
                print(f"  RAGAS分数: faithfulness={item['ragas_scores']['faithfulness']}")
                print(f"  创建时间: {item['created_at']}")
                print("  ---")
            return result
        else:
            print(f"❌ 获取历史失败: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 获取历史异常: {e}")
        return None

def get_task_results(task_id):
    """获取指定任务的结果"""
    url = f"http://127.0.0.1:8002/api/v1/acrac/excel-evaluation/evaluation-history/{task_id}"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n📋 任务 {task_id} 的详细结果:")
            print(f"  文件名: {result['filename']}")
            print(f"  总案例数: {result['total_cases']}")
            
            for i, item in enumerate(result['results']):
                print(f"\n  案例 {i+1}:")
                print(f"    问题: {item['question'][:50]}...")
                print(f"    标准答案: {item['ground_truth']}")
                print(f"    AI回答: {item['answer'][:50]}..." if item['answer'] else "    AI回答: 未完成")
                print(f"    状态: {item['status']}")
                if item['ragas_scores']['faithfulness']:
                    print(f"    RAGAS分数: F={item['ragas_scores']['faithfulness']:.2f}")
            
            return result
        else:
            print(f"❌ 获取任务结果失败: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 获取任务结果异常: {e}")
        return None

def main():
    """主演示流程"""
    print("🚀 Excel评测功能完整演示")
    print("=" * 50)
    
    # 1. 创建演示Excel文件
    print("\n1️⃣ 创建演示Excel文件")
    excel_file = create_demo_excel()
    
    # 2. 上传Excel文件
    print("\n2️⃣ 上传Excel文件")
    test_cases = upload_excel_file(excel_file)
    
    if not test_cases:
        print("❌ 演示终止：文件上传失败")
        return
    
    # 3. 开始评测
    print("\n3️⃣ 开始评测")
    task_id = start_evaluation(test_cases, excel_file)
    
    if not task_id:
        print("❌ 演示终止：评测启动失败")
        return
    
    # 4. 监控评测进度
    print("\n4️⃣ 监控评测进度")
    print("注意：由于这是演示，实际的AI评测可能需要较长时间")
    
    for i in range(3):  # 检查3次状态
        status = check_evaluation_status()
        if status:
            print(f"  进度: {status.get('progress', 0)}/{status.get('total', 0)}")
            print(f"  运行中: {status.get('is_running', False)}")
            if status.get('error'):
                print(f"  错误: {status['error']}")
        time.sleep(2)
    
    # 5. 获取评测历史
    print("\n5️⃣ 获取评测历史")
    get_evaluation_history()
    
    # 6. 获取任务详细结果
    print("\n6️⃣ 获取任务详细结果")
    get_task_results(task_id)
    
    # 7. 清理演示文件
    print("\n7️⃣ 清理演示文件")
    try:
        os.remove(excel_file)
        print(f"✅ 已删除演示文件: {excel_file}")
    except:
        print(f"⚠️ 无法删除演示文件: {excel_file}")
    
    print("\n🎉 Excel评测功能演示完成！")
    print("\n📝 功能总结:")
    print("  ✅ Excel文件上传和解析")
    print("  ✅ 批量评测任务启动")
    print("  ✅ 评测进度监控")
    print("  ✅ 评测数据存储到数据库")
    print("  ✅ 评测历史查询")
    print("  ✅ 任务结果详细查看")

if __name__ == "__main__":
    main()