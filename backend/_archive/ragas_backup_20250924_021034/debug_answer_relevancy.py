#!/usr/bin/env python3
"""
调试answer_relevancy评分为NaN的问题
"""
import os
import json
import logging
import numpy as np

# 设置环境变量
os.environ['NEST_ASYNCIO_DISABLE'] = '1'
os.environ['UVLOOP_DISABLE'] = '1'

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_answer_relevancy_detailed():
    """详细测试answer_relevancy指标"""
    try:
        # 导入RAGAS相关模块
        import ragas
        from datasets import Dataset
        from ragas.metrics import answer_relevancy
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        
        # 配置API
        api_key = os.getenv('SILICONFLOW_API_KEY', 'sk-ybghruztazvtitpwrityokshmckxkwflviwpuvseqopmxfze')
        base_url = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
        llm_model = os.getenv('SILICONFLOW_LLM_MODEL', 'Qwen/Qwen2.5-32B-Instruct')
        emb_model = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')
        
        logger.info(f"使用LLM模型: {llm_model}")
        logger.info(f"使用嵌入模型: {emb_model}")
        
        # 初始化模型
        llm = ChatOpenAI(model=llm_model, api_key=api_key, base_url=base_url, temperature=0)
        emb = OpenAIEmbeddings(model=emb_model, api_key=api_key, base_url=base_url)
        
        # 测试多个不同的案例
        test_cases = [
            {
                "name": "医疗案例1",
                "question": "患者出现胸痛症状，需要进行哪些检查？",
                "answer": "对于胸痛患者，建议进行心电图检查、胸部X线检查、心肌酶谱检测等基础检查。",
                "contexts": [
                    "胸痛是常见的临床症状，可能由心血管疾病、呼吸系统疾病等多种原因引起。",
                    "心电图检查是诊断心血管疾病的重要手段，可以发现心律失常、心肌缺血等问题。",
                    "胸部X线检查可以观察肺部和心脏的形态结构，排除肺部疾病。"
                ]
            },
            {
                "name": "简单案例",
                "question": "什么是感冒？",
                "answer": "感冒是一种常见的呼吸道疾病，通常由病毒感染引起。",
                "contexts": [
                    "感冒是由病毒感染引起的上呼吸道疾病。",
                    "感冒的症状包括鼻塞、流鼻涕、咳嗽等。"
                ]
            },
            {
                "name": "英文案例",
                "question": "What is diabetes?",
                "answer": "Diabetes is a chronic condition that affects how your body processes blood sugar.",
                "contexts": [
                    "Diabetes is a metabolic disorder characterized by high blood sugar levels.",
                    "There are two main types of diabetes: Type 1 and Type 2."
                ]
            }
        ]
        
        for i, case in enumerate(test_cases):
            logger.info(f"\n=== 测试案例 {i+1}: {case['name']} ===")
            
            # 准备数据
            data_dict = {
                'question': [case['question']],
                'answer': [case['answer']],
                'contexts': [case['contexts']],
            }
            
            data = Dataset.from_dict(data_dict)
            
            try:
                # 单独测试answer_relevancy
                logger.info("开始answer_relevancy评估...")
                res = ragas.evaluate(
                    dataset=data,
                    metrics=[answer_relevancy],
                    llm=llm,
                    embeddings=emb,
                )
                
                logger.info(f"评估结果类型: {type(res)}")
                logger.info(f"评估结果: {res}")
                
                # 提取评分
                if hasattr(res, '_scores_dict'):
                    scores = res._scores_dict
                    logger.info(f"_scores_dict: {scores}")
                    
                    ar_score = scores.get('answer_relevancy')
                    if isinstance(ar_score, list) and len(ar_score) > 0:
                        ar_value = ar_score[0]
                    else:
                        ar_value = ar_score
                    
                    logger.info(f"answer_relevancy原始值: {ar_value}")
                    logger.info(f"是否为NaN: {ar_value != ar_value if isinstance(ar_value, (int, float)) else 'N/A'}")
                    
                    if isinstance(ar_value, (int, float)):
                        if np.isnan(ar_value):
                            logger.warning("检测到NaN值！")
                        elif np.isinf(ar_value):
                            logger.warning("检测到无穷大值！")
                        else:
                            logger.info(f"正常数值: {ar_value}")
                
            except Exception as e:
                logger.error(f"案例 {case['name']} 评估失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 测试嵌入模型连接
        logger.info("\n=== 测试嵌入模型连接 ===")
        try:
            test_text = "这是一个测试文本"
            embedding = emb.embed_query(test_text)
            logger.info(f"嵌入向量长度: {len(embedding)}")
            logger.info(f"嵌入向量前5个值: {embedding[:5]}")
        except Exception as e:
            logger.error(f"嵌入模型测试失败: {e}")
        
        # 测试LLM连接
        logger.info("\n=== 测试LLM连接 ===")
        try:
            response = llm.invoke("请简单回答：什么是人工智能？")
            logger.info(f"LLM响应: {response.content[:100]}...")
        except Exception as e:
            logger.error(f"LLM测试失败: {e}")
            
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_answer_relevancy_detailed()