#!/usr/bin/env python3
"""
LLM输出调试脚本
专门调试RAGAS评测中LLM的输出和解析问题
"""
import os
import sys
import json
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

sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def debug_single_metric():
    """调试单个指标的LLM输出"""
    print("=" * 70)
    print("LLM输出调试")
    print("=" * 70)
    
    try:
        from ragas.dataset_schema import SingleTurnSample
        from ragas.metrics import Faithfulness, ContextPrecision, ContextRecall
        from langchain_openai import ChatOpenAI
        
        # 初始化LLM
        llm = ChatOpenAI(
            model="Qwen/Qwen2.5-32B-Instruct",
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url="https://api.siliconflow.cn/v1",
            temperature=0.1,
            timeout=60,
            max_retries=2
        )
        
        # 测试数据
        test_data = {
            "question": "糖尿病患者的饮食管理建议？",
            "answer": "糖尿病患者饮食管理：1. 控制总热量 2. 合理分配三大营养素 3. 定时定量进餐",
            "contexts": [
                "糖尿病需要严格的饮食控制",
                "营养均衡对血糖控制很重要"
            ],
            "ground_truth": "糖尿病患者应该控制饮食"
        }
        
        sample = SingleTurnSample(
            user_input=test_data["question"],
            response=test_data["answer"],
            retrieved_contexts=test_data["contexts"],
            reference=test_data["ground_truth"]
        )
        
        print(f"\\n📋 测试数据:")
        print(f"   问题: {test_data['question']}")
        print(f"   答案: {test_data['answer']}")
        print(f"   上下文: {test_data['contexts']}")
        print(f"   标准答案: {test_data['ground_truth']}")
        
        # 测试Context Precision
        print(f"\\n🔍 测试 Context Precision...")
        try:
            context_precision = ContextPrecision(llm=llm)
            
            # 手动调用内部方法来查看LLM输出
            print("   调用LLM进行上下文精确度评估...")
            
            # 直接调用评估
            score = context_precision.single_turn_score(sample)
            print(f"   Context Precision 得分: {score}")
            
        except Exception as e:
            print(f"   ❌ Context Precision 失败: {e}")
            logger.error(f"Context Precision 详细错误: {e}", exc_info=True)
        
        # 测试Context Recall
        print(f"\\n🔍 测试 Context Recall...")
        try:
            context_recall = ContextRecall(llm=llm)
            
            print("   调用LLM进行上下文召回率评估...")
            score = context_recall.single_turn_score(sample)
            print(f"   Context Recall 得分: {score}")
            
        except Exception as e:
            print(f"   ❌ Context Recall 失败: {e}")
            logger.error(f"Context Recall 详细错误: {e}", exc_info=True)
        
        # 测试Faithfulness
        print(f"\\n🔍 测试 Faithfulness...")
        try:
            faithfulness = Faithfulness(llm=llm)
            
            print("   调用LLM进行忠实度评估...")
            score = faithfulness.single_turn_score(sample)
            print(f"   Faithfulness 得分: {score}")
            
        except Exception as e:
            print(f"   ❌ Faithfulness 失败: {e}")
            logger.error(f"Faithfulness 详细错误: {e}", exc_info=True)
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        logger.error(f"详细错误: {e}", exc_info=True)

def test_llm_direct():
    """直接测试LLM响应"""
    print(f"\\n🤖 直接测试LLM响应")
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage
        
        llm = ChatOpenAI(
            model="Qwen/Qwen2.5-32B-Instruct",
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            base_url="https://api.siliconflow.cn/v1",
            temperature=0.1,
            timeout=60,
            max_retries=2
        )
        
        # 测试简单的LLM调用
        test_prompt = """请回答：糖尿病患者的饮食管理建议是什么？
        
请用中文回答，并且格式化为JSON：
{
  "answer": "你的回答",
  "confidence": 0.9
}"""
        
        print(f"   发送提示: {test_prompt[:100]}...")
        
        response = llm.invoke([HumanMessage(content=test_prompt)])
        print(f"   LLM响应: {response.content}")
        
        # 尝试解析JSON
        try:
            parsed = json.loads(response.content)
            print(f"   JSON解析成功: {parsed}")
        except:
            print(f"   JSON解析失败，原始响应: {response.content}")
        
    except Exception as e:
        print(f"❌ LLM测试失败: {e}")
        logger.error(f"详细错误: {e}", exc_info=True)

def main():
    """主函数"""
    # 1. 调试单个指标
    debug_single_metric()
    
    # 2. 直接测试LLM
    test_llm_direct()
    
    print("\\n" + "=" * 70)
    print("🎯 LLM调试完成")
    print("=" * 70)

if __name__ == "__main__":
    main()