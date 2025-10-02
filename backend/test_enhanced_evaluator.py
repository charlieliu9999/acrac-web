#!/usr/bin/env python3
"""
测试增强版RAGAS评估器
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.enhanced_ragas_evaluator import create_enhanced_evaluator

async def test_evaluator():
    """测试评估器"""
    try:
        print("🚀 开始测试增强版RAGAS评估器")
        
        # 创建评估器
        evaluator = create_enhanced_evaluator()
        print("✅ 增强版RAGAS评估器创建成功")
        
        # 测试数据
        test_data = {
            "id": "test_001",
            "question": "糖尿病患者的饮食管理建议？",
            "answer": "糖尿病患者饮食管理：1. 控制总热量 2. 合理分配三大营养素 3. 定时定量进餐",
            "contexts": [
                "糖尿病需要严格的饮食控制",
                "营养均衡对血糖控制很重要"
            ],
            "ground_truth": "糖尿病患者应该控制饮食"
        }
        
        print(f"\n📊 测试数据:")
        print(f"   问题: {test_data['question']}")
        print(f"   答案: {test_data['answer']}")
        print(f"   上下文数量: {len(test_data['contexts'])}")
        
        # 运行评估
        result = await evaluator.evaluate_with_detailed_results(test_data)
        
        print(f"\n✅ 评估完成！")
        print(f"评测结果:")
        print(f"  状态: {result.status.value}")
        print(f"  指标分数:")
        for metric, score in result.metrics.items():
            status = "✅" if score > 0 else "⚠️"
            print(f"    {status} {metric}: {score:.4f}")
        
        print(f"  医学术语分析: {result.medical_term_analysis}")
        print(f"  中文处理信息: {result.chinese_processing_info}")
        
        if result.status.value == "completed":
            print(f"\n🎉 测试成功！增强版评估器工作正常")
        else:
            print(f"\n❌ 测试失败: {result.error_message}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_evaluator())












