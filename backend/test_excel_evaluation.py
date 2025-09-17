#!/usr/bin/env python3
"""
测试Excel评测功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from app.core.database import get_db
from app.api.api_v1.endpoints.excel_evaluation_api import ExcelEvaluationService
from app.models.system_models import ExcelEvaluationData
import uuid

def create_test_excel():
    """创建测试Excel文件"""
    test_data = {
        '题号': [1, 2, 3],
        '临床场景': [
            '患者，男性，45岁，胸痛3小时，疑似心肌梗死',
            '患者，女性，30岁，腹痛伴发热，疑似阑尾炎',
            '患者，男性，60岁，头痛伴恶心呕吐，疑似脑血管疾病'
        ],
        '首选检查项目（标准化）': [
            'CT冠状动脉造影',
            'CT腹部平扫+增强',
            'CT头颅平扫'
        ]
    }
    
    df = pd.DataFrame(test_data)
    excel_file = 'test_evaluation.xlsx'
    df.to_excel(excel_file, index=False)
    print(f"✅ 创建测试Excel文件: {excel_file}")
    return excel_file

def test_excel_parsing():
    """测试Excel解析功能"""
    try:
        # 创建测试Excel文件
        excel_file = create_test_excel()
        
        # 读取文件内容
        with open(excel_file, 'rb') as f:
            content = f.read()
        
        # 创建服务实例
        db = next(get_db())
        service = ExcelEvaluationService(db=db)
        
        # 解析Excel文件
        test_cases = service.parse_excel_file(content)
        
        print(f"✅ 成功解析Excel文件，共{len(test_cases)}个测试案例")
        for i, case in enumerate(test_cases):
            print(f"  案例{i+1}: {case['clinical_query'][:30]}...")
        
        # 清理测试文件
        os.remove(excel_file)
        
        return test_cases
        
    except Exception as e:
        print(f"❌ Excel解析测试失败: {e}")
        return None

def test_database_save():
    """测试数据库保存功能"""
    try:
        db = next(get_db())
        service = ExcelEvaluationService(db=db)
        
        # 创建测试数据
        task_id = str(uuid.uuid4())
        filename = "test_evaluation.xlsx"
        test_cases = [
            {
                'clinical_query': '测试临床场景1',
                'ground_truth': '测试标准答案1'
            }
        ]
        results = [
            {
                'contexts': ['测试上下文1'],
                'answer': '测试回答1',
                'ragas_scores': {
                    'faithfulness': 0.8,
                    'answer_relevancy': 0.9,
                    'context_precision': 0.7,
                    'context_recall': 0.85
                },
                'status': 'completed'
            }
        ]
        
        # 保存到数据库
        service.save_evaluation_data_to_db(task_id, filename, test_cases, results)
        
        # 验证保存结果
        saved_data = db.query(ExcelEvaluationData).filter(
            ExcelEvaluationData.task_id == task_id
        ).first()
        
        if saved_data:
            print("✅ 数据库保存测试成功")
            print(f"  任务ID: {saved_data.task_id}")
            print(f"  文件名: {saved_data.filename}")
            print(f"  问题: {saved_data.question}")
            print(f"  标准答案: {saved_data.ground_truth}")
            print(f"  RAGAS分数: faithfulness={saved_data.faithfulness}")
        else:
            print("❌ 数据库保存测试失败：未找到保存的数据")
            
    except Exception as e:
        print(f"❌ 数据库保存测试失败: {e}")

if __name__ == "__main__":
    print("开始测试Excel评测功能...")
    
    # 测试Excel解析
    print("\n1. 测试Excel解析功能")
    test_cases = test_excel_parsing()
    
    # 测试数据库保存
    print("\n2. 测试数据库保存功能")
    test_database_save()
    
    print("\n🎉 Excel评测功能测试完成")