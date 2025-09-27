#!/usr/bin/env python3
"""
独立测试RAGAS评估逻辑
"""
import os
import json
import logging

# 设置环境变量
os.environ['NEST_ASYNCIO_DISABLE'] = '1'
os.environ['UVLOOP_DISABLE'] = '1'

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ragas_evaluation():
    """测试RAGAS评估"""
    try:
        # 导入RAGAS相关模块
        import ragas
        from datasets import Dataset
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        
        # 配置API
        api_key = os.getenv('SILICONFLOW_API_KEY', 'sk-ybghruztazvtitpwrityokshmckxkwflviwpuvseqopmxfze')
        base_url = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
        llm_model = os.getenv('SILICONFLOW_LLM_MODEL', 'Qwen/Qwen2.5-32B-Instruct')
        emb_model = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')
        
        logger.info(f"使用LLM模型: {llm_model}")
        logger.info(f"使用嵌入模型: {emb_model}")
        logger.info(f"API Base URL: {base_url}")
        
        # 初始化模型
        llm = ChatOpenAI(model=llm_model, api_key=api_key, base_url=base_url, temperature=0)
        emb = OpenAIEmbeddings(model=emb_model, api_key=api_key, base_url=base_url)
        
        # 测试数据
        user_input = "患者出现胸痛症状，需要进行哪些检查？"
        answer = "对于胸痛患者，建议进行心电图检查、胸部X线检查、心肌酶谱检测等基础检查。"
        contexts = [
            "胸痛是常见的临床症状，可能由心血管疾病、呼吸系统疾病等多种原因引起。",
            "心电图检查是诊断心血管疾病的重要手段，可以发现心律失常、心肌缺血等问题。",
            "胸部X线检查可以观察肺部和心脏的形态结构，排除肺部疾病。"
        ]
        reference = "胸痛患者应进行心电图、胸部X线、心肌酶谱等检查以明确诊断。"
        
        # 准备数据
        data_dict = {
            'question': [user_input],
            'answer': [answer],
            'contexts': [contexts],
            'ground_truth': [reference],
        }
        
        metrics = [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ]
        
        logger.info("开始RAGAS评估...")
        data = Dataset.from_dict(data_dict)
        
        # 执行评估
        res = ragas.evaluate(
            dataset=data,
            metrics=metrics,
            llm=llm,
            embeddings=emb,
        )
        
        logger.info(f"RAGAS评估结果类型: {type(res)}")
        logger.info(f"RAGAS评估结果: {res}")
        
        # 处理结果
        if isinstance(res, dict):
            base = res
            logger.info("结果是字典类型")
        elif hasattr(res, 'scores') and isinstance(res.scores, dict):
            base = res.scores
            logger.info("结果有scores属性")
        elif hasattr(res, '__dict__'):
            base = res.__dict__
            logger.info("使用__dict__属性")
        else:
            try:
                base = dict(res)
                logger.info("转换为字典")
            except Exception as e:
                logger.error(f"无法转换结果: {e}")
                base = {}
        
        logger.info(f"处理后的base结果: {base}")
        
        # 清理函数
        def clean(v):
            try:
                f = float(v)
                if f != f:  # NaN检查
                    logger.warning(f"发现NaN值: {v}")
                    return 0.0
                return f
            except Exception as e:
                logger.warning(f"无法转换为float: {v}, 错误: {e}")
                return 0.0
        
        # 提取评分
        out = {
            'faithfulness': clean(base.get('faithfulness', 0.0)),
            'answer_relevancy': clean(base.get('answer_relevancy', 0.0)),
            'context_precision': clean(base.get('context_precision', 0.0)),
            'context_recall': clean(base.get('context_recall', 0.0)),
        }
        
        logger.info(f"最终评分结果: {out}")
        return out
        
    except Exception as e:
        logger.error(f"RAGAS评估失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = test_ragas_evaluation()
    if result:
        print(json.dumps(result, indent=2))
    else:
        print("评估失败")