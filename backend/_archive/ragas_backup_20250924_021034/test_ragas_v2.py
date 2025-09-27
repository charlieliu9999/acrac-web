#!/usr/bin/env python3
"""
测试RAGAS V2评估器 - 验证0.3.x版本兼容性
"""
import os
import sys
import logging
import asyncio
from pathlib import Path

# 设置环境变量
os.environ['NEST_ASYNCIO_DISABLE'] = '1'
os.environ['UVLOOP_DISABLE'] = '1'

# 加载.env文件
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_single_metric():
    """测试单个指标评估"""
    print("=== 测试单个指标评估 ===")
    
    try:
        from app.services.ragas_evaluator_v2 import RAGASEvaluatorV2
        
        # 创建评估器
        evaluator = RAGASEvaluatorV2()
        print(f"✅ 评估器创建成功 - LLM: {evaluator.llm_model_name}")
        
        # 测试数据
        sample_data = {
            'question': "患者出现胸痛症状，需要进行什么影像学检查？",
            'answer': "建议进行胸部CT检查以排除肺栓塞等疾病。",
            'contexts': ["胸痛是常见的临床症状", "CT检查可以有效诊断胸部疾病"],
            'ground_truth': "胸部CT"
        }
        
        # 创建SingleTurnSample
        sample = evaluator.create_single_turn_sample(sample_data)
        print(f"✅ SingleTurnSample创建成功")
        print(f"   用户输入: {sample.user_input}")
        print(f"   响应: {sample.response}")
        print(f"   上下文数量: {len(sample.retrieved_contexts)}")
        
        # 测试单个指标
        print("\n--- 测试Answer Relevancy ---")
        relevancy_score = await evaluator.answer_relevancy_metric.single_turn_ascore(sample)
        print(f"Answer Relevancy: {relevancy_score:.4f}")
        
        print("\n--- 测试Faithfulness ---")
        try:
            faithfulness_score = await evaluator.faithfulness_metric.single_turn_ascore(sample)
            print(f"Faithfulness: {faithfulness_score:.4f}")
        except Exception as e:
            print(f"❌ Faithfulness评估失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 单指标测试失败: {e}")
        logger.error(f"单指标测试详细错误: {e}", exc_info=True)
        return False

async def test_full_evaluation():
    """测试完整评估流程"""
    print("\n=== 测试完整评估流程 ===")
    
    try:
        from app.services.ragas_evaluator_v2 import RAGASEvaluatorV2
        
        # 创建评估器
        evaluator = RAGASEvaluatorV2()
        
        # 测试数据
        test_samples = [
            {
                'question': "患者出现胸痛症状，需要进行什么影像学检查？",
                'answer': "建议进行胸部CT检查以排除肺栓塞等疾病。",
                'contexts': ["胸痛是常见的临床症状", "CT检查可以有效诊断胸部疾病"],
                'ground_truth': "胸部CT"
            },
            {
                'question': "45岁女性，慢性反复头痛3年，无神经系统异常体征。",
                'answer': "建议进行MR颅脑平扫检查，以排除颅内占位性病变。",
                'contexts': ["慢性头痛需要影像学检查", "MRI是诊断颅内疾病的首选方法"],
                'ground_truth': "MR颅脑(平扫)"
            }
        ]
        
        print(f"测试样本数量: {len(test_samples)}")
        
        # 运行评估
        results = await evaluator.evaluate_batch_async(test_samples)
        
        print(f"\n✅ 评估完成!")
        print(f"总样本数: {results['total_samples']}")
        print(f"平均评分:")
        for metric, score in results['avg_scores'].items():
            print(f"  {metric}: {score:.4f}")
        
        # 显示个别样本结果
        print(f"\n个别样本结果:")
        for i, scores in enumerate(results['individual_scores']):
            print(f"  样本 {i+1}:")
            for metric, score in scores.items():
                print(f"    {metric}: {score:.4f}")
        
        return results
        
    except Exception as e:
        print(f"❌ 完整评估测试失败: {e}")
        logger.error(f"完整评估测试详细错误: {e}", exc_info=True)
        return None

def test_sync_interface():
    """测试同步接口"""
    print("\n=== 测试同步接口 ===")
    
    try:
        from app.services.ragas_evaluator_v2 import RAGASEvaluatorV2
        
        # 创建评估器
        evaluator = RAGASEvaluatorV2()
        
        # 测试数据
        sample_data = {
            'question': "患者出现胸痛症状，需要进行什么影像学检查？",
            'answer': "建议进行胸部CT检查。",
            'contexts': ["胸痛是常见的临床症状", "CT检查可以有效诊断胸部疾病"],
            'ground_truth': "胸部CT"
        }
        
        # 测试同步单样本评估
        scores = evaluator.evaluate_single_sample(sample_data)
        print(f"✅ 同步单样本评估成功:")
        for metric, score in scores.items():
            print(f"  {metric}: {score:.4f}")
        
        # 测试同步批量评估
        test_samples = [sample_data]
        batch_results = evaluator.evaluate_batch(test_samples)
        print(f"✅ 同步批量评估成功:")
        print(f"  平均评分: {batch_results['avg_scores']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 同步接口测试失败: {e}")
        logger.error(f"同步接口测试详细错误: {e}", exc_info=True)
        return False

async def main():
    """主测试函数"""
    print("🚀 开始RAGAS V2评估器测试")
    
    # 测试1: 单指标评估
    success1 = await test_single_metric()
    
    # 测试2: 完整评估流程
    success2 = await test_full_evaluation()
    
    # 测试3: 同步接口
    success3 = test_sync_interface()
    
    print(f"\n📊 测试结果总结:")
    print(f"  单指标评估: {'✅ 通过' if success1 else '❌ 失败'}")
    print(f"  完整评估流程: {'✅ 通过' if success2 else '❌ 失败'}")
    print(f"  同步接口: {'✅ 通过' if success3 else '❌ 失败'}")
    
    if all([success1, success2, success3]):
        print(f"\n🎉 所有测试通过！RAGAS V2评估器工作正常")
    else:
        print(f"\n⚠️  部分测试失败，需要进一步调试")

if __name__ == "__main__":
    asyncio.run(main())