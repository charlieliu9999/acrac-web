#!/usr/bin/env python3
"""
简单的RAGAS评测测试脚本
"""

import os
import sys
import asyncio
import logging

# 设置事件循环策略，避免uvloop冲突
try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except Exception:
    pass

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ragas_simple():
    """测试RAGAS评估器"""
    try:
        # 导入RAGAS相关模块
        import ragas
        from datasets import Dataset
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        
        logger.info("RAGAS模块导入成功")
        
        # 配置API
        api_key = os.getenv("SILICONFLOW_API_KEY")
        base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        llm_model = "Qwen/Qwen2.5-7B-Instruct"
        emb_model = "BAAI/bge-m3"
        
        if not api_key:
            logger.error("未设置SILICONFLOW_API_KEY")
            return
            
        logger.info(f"使用模型: {llm_model}")
        logger.info(f"使用嵌入模型: {emb_model}")
        logger.info(f"API基础URL: {base_url}")
        
        # 初始化模型
        llm = ChatOpenAI(
            model=llm_model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.1
        )
        
        emb = OpenAIEmbeddings(
            model=emb_model,
            api_key=api_key,
            base_url=base_url
        )
        
        logger.info("模型初始化成功")
        
        # 准备测试数据
        test_data = {
            "question": ["患者男性，65岁，突发剧烈头痛，伴恶心呕吐，怀疑蛛网膜下腔出血，请推荐合适的影像学检查"],
            "answer": ["推荐进行CT颅脑平扫检查，这是诊断蛛网膜下腔出血的首选影像学检查方法"],
            "contexts": [["蛛网膜下腔出血是神经外科急症，CT颅脑平扫是首选检查", "急性期CT可显示高密度血液信号"]],
            "ground_truth": ["CT颅脑平扫是蛛网膜下腔出血的首选检查方法"]
        }
        
        dataset = Dataset.from_dict(test_data)
        logger.info("测试数据准备完成")
        
        # 执行评估
        metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
        
        logger.info("开始RAGAS评估...")
        result = ragas.evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=llm,
            embeddings=emb
        )
        
        logger.info("RAGAS评估完成")
        logger.info(f"评估结果: {result}")
        logger.info(f"结果类型: {type(result)}")
        
        # 提取分数 - RAGAS返回EvaluationResult对象
        try:
            # 尝试不同的属性访问方式
            if hasattr(result, 'scores') and hasattr(result.scores, 'to_dict'):
                # DataFrame格式
                scores_dict = result.scores.to_dict('records')[0] if len(result.scores) > 0 else {}
            elif hasattr(result, 'scores') and isinstance(result.scores, dict):
                scores_dict = result.scores
            elif hasattr(result, '__dict__'):
                # 直接访问对象属性
                scores_dict = {}
                for attr in dir(result):
                    if not attr.startswith('_') and not callable(getattr(result, attr)):
                        try:
                            value = getattr(result, attr)
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                scores_dict[attr] = value
                        except:
                            pass
            else:
                logger.error(f"无法处理的结果格式: {type(result)}")
                logger.info(f"可用属性: {dir(result)}")
                return None
        except Exception as e:
            logger.error(f"提取分数时出错: {e}")
            # 尝试直接打印结果的所有属性
            logger.info(f"结果对象属性: {dir(result)}")
            if hasattr(result, 'scores'):
                logger.info(f"scores属性: {result.scores}")
                logger.info(f"scores类型: {type(result.scores)}")
            return None
            
        logger.info("=== RAGAS评分结果 ===")
        for metric, score in scores_dict.items():
            logger.info(f"{metric}: {score}")
            
        return scores_dict
        
    except Exception as e:
        logger.error(f"RAGAS评测失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_ragas_simple()