#!/usr/bin/env python3
"""
RAGAS医疗数据评测脚本
使用真实的医疗查询和推荐数据进行RAGAS评估
"""

import os
import sys
import asyncio
import logging
import json
from typing import Dict, Any, List

# 设置事件循环策略以避免uvloop冲突
try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except Exception:
    pass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ragas_medical():
    """使用真实医疗数据测试RAGAS评估"""
    try:
        # 导入RAGAS相关模块
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        from datasets import Dataset
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        
        # 配置API
        api_key = os.getenv("SILICONFLOW_API_KEY")
        base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        model_name = os.getenv("SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
        
        if not api_key:
            logger.error("未找到SILICONFLOW_API_KEY环境变量")
            return None
            
        logger.info(f"使用API密钥: {api_key[:10]}...")
        logger.info(f"使用基础URL: {base_url}")
        logger.info(f"使用模型: {model_name}")
        
        # 初始化模型
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.1
        )
        
        embeddings = OpenAIEmbeddings(
            model="BAAI/bge-large-zh-v1.5",
            api_key=api_key,
            base_url=base_url
        )
        
        logger.info("模型初始化成功")
        
        # 准备真实的医疗测试数据
        medical_data = {
            "question": [
                "患者男性，65岁，主诉胸痛3小时，伴有出汗、恶心。心电图显示ST段抬高。应该如何处理？",
                "女性患者，45岁，反复咳嗽2周，伴有发热和胸痛。胸片显示右下肺阴影。诊断和治疗建议？",
                "儿童患者，8岁，发热39°C，咽痛，颈部淋巴结肿大。体检发现扁桃体红肿有脓点。处理方案？"
            ],
            "answer": [
                "根据患者症状和心电图表现，高度怀疑急性ST段抬高型心肌梗死(STEMI)。建议立即启动急诊PCI流程，给予双联抗血小板治疗(阿司匹林+氯吡格雷)，抗凝治疗(肝素)，他汀类药物，并密切监测生命体征。",
                "根据症状和影像学表现，考虑社区获得性肺炎。建议完善血常规、CRP、痰培养等检查，给予经验性抗生素治疗(如阿莫西林克拉维酸钾或左氧氟沙星)，对症支持治疗，注意观察病情变化。",
                "根据临床表现，考虑急性化脓性扁桃体炎。建议给予青霉素类抗生素治疗(如阿莫西林)，退热药物(对乙酰氨基酚)，多饮水，注意休息。如症状持续或加重，需复诊评估。"
            ],
            "contexts": [
                [
                    "急性ST段抬高型心肌梗死是冠心病的严重类型，需要紧急血管再通治疗",
                    "PCI(经皮冠状动脉介入治疗)是STEMI的首选治疗方法",
                    "双联抗血小板治疗可以显著降低血栓形成风险",
                    "早期识别和快速处理是改善预后的关键"
                ],
                [
                    "社区获得性肺炎是常见的呼吸系统感染性疾病",
                    "胸片是诊断肺炎的重要影像学检查",
                    "经验性抗生素治疗应根据当地耐药情况选择",
                    "病情评估包括症状、体征和实验室检查"
                ],
                [
                    "急性扁桃体炎多由细菌感染引起，以链球菌最常见",
                    "青霉素类抗生素是治疗链球菌感染的首选药物",
                    "儿童发热需要及时退热，避免高热惊厥",
                    "症状持续或加重时需要重新评估诊断和治疗"
                ]
            ],
            "ground_truth": [
                "急性STEMI需要立即进行急诊PCI治疗，同时给予规范的药物治疗包括双抗、抗凝、他汀等。",
                "社区获得性肺炎需要根据病情严重程度选择合适的抗生素治疗，并进行对症支持治疗。",
                "急性化脓性扁桃体炎需要抗生素治疗，首选青霉素类，同时进行退热等对症治疗。"
            ]
        }
        
        logger.info("医疗测试数据准备完成")
        
        # 创建数据集
        dataset = Dataset.from_dict(medical_data)
        logger.info(f"数据集创建完成，包含{len(dataset)}条记录")
        
        # 定义评估指标
        metrics = [
            faithfulness,
            answer_relevancy, 
            context_precision,
            context_recall
        ]
        
        logger.info("开始RAGAS医疗数据评估...")
        
        # 执行评估
        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=llm,
            embeddings=embeddings
        )
        
        logger.info("RAGAS医疗数据评估完成")
        logger.info(f"评估结果: {result}")
        logger.info(f"结果类型: {type(result)}")
        
        # 提取和显示分数
        scores_dict = {}
        
        # 从原始结果字符串中解析分数
        result_str = str(result)
        logger.info(f"原始结果字符串: {result_str}")
        
        # 尝试从字符串中提取分数
        import re
        score_pattern = r"'(\w+)':\s*([\d\.]+|nan)"
        matches = re.findall(score_pattern, result_str)
        
        for metric, score_str in matches:
            try:
                if score_str == 'nan':
                    scores_dict[metric] = float('nan')
                else:
                    scores_dict[metric] = float(score_str)
            except ValueError:
                logger.warning(f"无法解析分数: {metric} = {score_str}")
                
        if not scores_dict:
            logger.error("无法提取评分结果")
            return None
            
        logger.info("=== RAGAS医疗数据评分结果 ===")
        for metric, score in scores_dict.items():
            logger.info(f"{metric}: {score:.4f}")
            
        # 保存结果到文件
        result_file = "ragas_medical_evaluation_result.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump({
                "evaluation_type": "medical_data",
                "dataset_size": len(dataset),
                "scores": scores_dict,
                "raw_result": str(result)
            }, f, ensure_ascii=False, indent=2)
            
        logger.info(f"评估结果已保存到: {result_file}")
        return scores_dict
        
    except Exception as e:
        logger.error(f"RAGAS医疗数据评测失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_ragas_medical()