#!/usr/bin/env python3
"""
简化的answer_relevancy测试
"""
import os
import logging

# 设置环境变量
os.environ['NEST_ASYNCIO_DISABLE'] = '1'
os.environ['UVLOOP_DISABLE'] = '1'

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_answer_relevancy():
    """测试answer_relevancy指标"""
    try:
        from datasets import Dataset
        from ragas.metrics import answer_relevancy
        from ragas import evaluate
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        
        # 配置API
        api_key = 'sk-ybghruztazvtitpwrityokshmckxkwflviwpuvseqopmxfze'
        base_url = 'https://api.siliconflow.cn/v1'
        llm_model = os.getenv('SILICONFLOW_LLM_MODEL', 'Qwen/Qwen2.5-32B-Instruct')
        emb_model = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')
        
        print(f"配置信息:")
        print(f"  LLM模型: {llm_model}")
        print(f"  嵌入模型: {emb_model}")
        print(f"  API Base URL: {base_url}")
        
        # 初始化模型
        llm = ChatOpenAI(model=llm_model, api_key=api_key, base_url=base_url, temperature=0)
        emb = OpenAIEmbeddings(model=emb_model, api_key=api_key, base_url=base_url)
        
        # 测试数据
        question = "患者出现胸痛症状，需要进行哪些检查？"
        answer = "对于胸痛患者，建议进行心电图检查、胸部X线检查、心肌酶谱检测等基础检查。"
        contexts = [
            "胸痛是常见的临床症状，可能由心血管疾病、呼吸系统疾病等多种原因引起。",
            "心电图检查是诊断心血管疾病的重要手段，可以发现心律失常、心肌缺血等问题。",
            "胸部X线检查可以观察肺部和心脏的形态结构，排除肺部疾病。"
        ]
        
        print(f"\n测试数据:")
        print(f"  问题: {question}")
        print(f"  答案: {answer}")
        print(f"  上下文数量: {len(contexts)}")
        
        # 准备数据集
        data_dict = {
            'question': [question],
            'answer': [answer],
            'contexts': [contexts],
        }
        
        dataset = Dataset.from_dict(data_dict)
        print(f"\n数据集创建成功，样本数: {len(dataset)}")
        
        # 执行评估
        print("\n开始answer_relevancy评估...")
        result = evaluate(
            dataset=dataset,
            metrics=[answer_relevancy],
            llm=llm,
            embeddings=emb,
        )
        
        print(f"\n评估完成!")
        print(f"结果类型: {type(result)}")
        print(f"结果内容: {result}")
        
        # 详细分析结果
        if hasattr(result, '_scores_dict'):
            scores_dict = result._scores_dict
            print(f"\n_scores_dict: {scores_dict}")
            
            ar_scores = scores_dict.get('answer_relevancy', [])
            print(f"answer_relevancy原始值: {ar_scores}")
            
            if isinstance(ar_scores, list) and len(ar_scores) > 0:
                ar_value = ar_scores[0]
                print(f"第一个值: {ar_value}")
                print(f"值的类型: {type(ar_value)}")
                
                if isinstance(ar_value, (int, float)):
                    import math
                    if math.isnan(ar_value):
                        print("❌ 检测到NaN值!")
                    elif math.isinf(ar_value):
                        print("❌ 检测到无穷大值!")
                    else:
                        print(f"✅ 正常数值: {ar_value}")
                else:
                    print(f"❓ 非数值类型: {ar_value}")
        
        if hasattr(result, '_repr_dict'):
            repr_dict = result._repr_dict
            print(f"\n_repr_dict: {repr_dict}")
            
            ar_repr = repr_dict.get('answer_relevancy')
            print(f"answer_relevancy表示值: {ar_repr}")
            
            if isinstance(ar_repr, (int, float)):
                import math
                if math.isnan(ar_repr):
                    print("❌ 表示值也是NaN!")
                else:
                    print(f"✅ 表示值正常: {ar_repr}")
        
        return result
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("=== Answer Relevancy NaN 问题调试 ===")
    result = test_answer_relevancy()
    
    if result:
        print("\n=== 测试完成 ===")
    else:
        print("\n=== 测试失败 ===")