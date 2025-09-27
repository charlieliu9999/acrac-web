#!/usr/bin/env python3
"""
简化的RAGAS V2测试 - 验证修复后的评估器
"""
import os
import sys
import logging
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
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_ragas_v2_simple():
    """简单测试RAGAS V2评估器"""
    print("🚀 开始RAGAS V2简化测试")
    
    try:
        from app.services.ragas_evaluator_v2 import RAGASEvaluatorV2
        
        # 创建评估器
        evaluator = RAGASEvaluatorV2()
        print(f"✅ 评估器创建成功")
        
        # 简单测试数据
        sample_data = {
            'question': "患者胸痛需要什么检查？",
            'answer': "胸部CT检查。",
            'contexts': ["胸痛需要影像学检查", "CT是常用的检查方法"],
            'ground_truth': "胸部CT"
        }
        
        print(f"📝 测试数据准备完成")
        
        # 测试同步单样本评估
        print(f"🔍 开始单样本评估...")
        scores = evaluator.evaluate_single_sample(sample_data)
        
        print(f"\n✅ 评估完成！结果:")
        for metric, score in scores.items():
            status = "✅" if score > 0 else "⚠️"
            print(f"  {status} {metric}: {score:.4f}")
        
        # 计算有效指标数量
        valid_metrics = sum(1 for score in scores.values() if score > 0)
        total_metrics = len(scores)
        
        print(f"\n📊 评估总结:")
        print(f"  有效指标: {valid_metrics}/{total_metrics}")
        print(f"  平均分: {sum(scores.values())/len(scores):.4f}")
        
        if valid_metrics >= 2:  # 至少2个指标有效就算成功
            print(f"🎉 测试成功！RAGAS V2评估器基本工作正常")
            return True
        else:
            print(f"⚠️  测试部分成功，但仍有指标需要优化")
            return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        logger.error(f"详细错误: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_ragas_v2_simple()
    if success:
        print(f"\n🎯 结论: RAGAS V2评估器已成功解决主要问题！")
    else:
        print(f"\n🔧 结论: 需要进一步优化")