#!/usr/bin/env python3
"""调试RAGAS评估问题的脚本"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# 在导入任何其他模块之前，强制设置默认事件循环策略
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

# 禁用nest_asyncio以避免事件循环冲突
os.environ['NEST_ASYNCIO_DISABLE'] = '1'

# 手动加载.env文件
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 设置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """主函数"""
    try:
        # 导入RAGAS相关模块
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        
        logger.info("RAGAS模块导入成功")
        
        # 读取配置
        from app.services.ragas_evaluator import RAGASEvaluator
        
        # 创建评估器
        logger.info("创建RAGAS评估器...")
        evaluator = RAGASEvaluator()
        logger.info(f"评估器创建成功，LLM: {evaluator.llm_model_name}, Embedding: {evaluator.embedding_model_name}")
        
        # 准备测试数据
        test_data = {
            'question': ["患者出现胸痛症状，需要进行什么影像学检查？"],
            'answer': ["建议进行胸部CT检查以排除肺栓塞等疾病。"],
            'contexts': [["胸痛是常见的临床症状", "CT检查可以有效诊断胸部疾病"]],
            'ground_truth': ["胸部CT"]
        }
        
        logger.info("准备测试数据...")
        dataset = Dataset.from_dict(test_data)
        logger.info(f"数据集创建成功，包含 {len(dataset)} 个样本")
        logger.info(f"数据集列: {dataset.column_names}")
        logger.info(f"样本数据: {dataset[0]}")
        
        # 测试LLM连接
        logger.info("测试LLM连接...")
        try:
            test_response = evaluator.llm.invoke("Hello, this is a test.")
            logger.info(f"LLM测试成功: {test_response.content[:100]}...")
        except Exception as e:
            logger.error(f"LLM测试失败: {e}")
            return
        
        # 测试Embedding连接
        logger.info("测试Embedding连接...")
        try:
            test_embedding = evaluator.embeddings.embed_query("test query")
            logger.info(f"Embedding测试成功，维度: {len(test_embedding)}")
        except Exception as e:
            logger.error(f"Embedding测试失败: {e}")
            return
        
        # 执行RAGAS评估
        logger.info("开始RAGAS评估...")
        try:
            result = evaluate(
                dataset=dataset,
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
                llm=evaluator.llm,
                embeddings=evaluator.embeddings,
                raise_exceptions=True  # 启用异常抛出以便调试
            )
            logger.info("RAGAS评估完成")
            logger.info(f"评估结果类型: {type(result)}")
            
            # 转换为DataFrame查看结果
            if hasattr(result, 'to_pandas'):
                df = result.to_pandas()
                logger.info(f"结果DataFrame:\n{df}")
                logger.info(f"列名: {df.columns.tolist()}")
                
                # 检查每个指标的值
                for metric in ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']:
                    if metric in df.columns:
                        value = df[metric].iloc[0]
                        logger.info(f"{metric}: {value} (类型: {type(value)})")
                    else:
                        logger.warning(f"缺少指标: {metric}")
            else:
                logger.info(f"评估结果: {result}")
                
        except Exception as e:
            logger.error(f"RAGAS评估失败: {e}")
            import traceback
            logger.error(f"详细错误信息:\n{traceback.format_exc()}")
            return
        
        logger.info("调试完成")
        
    except Exception as e:
        logger.error(f"调试脚本执行失败: {e}")
        import traceback
        logger.error(f"详细错误信息:\n{traceback.format_exc()}")

if __name__ == "__main__":
    main()