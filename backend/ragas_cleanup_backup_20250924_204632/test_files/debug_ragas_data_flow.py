#!/usr/bin/env python3
"""
RAGAS数据流调试脚本
跟踪从数据库到评测系统的完整数据流
"""
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

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
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def extract_answer_from_result(result_data, inference_method):
    """从result数据中提取答案"""
    if not result_data or not isinstance(result_data, dict):
        return None
    
    # RAG方式：直接从answer字段获取
    if inference_method == 'rag' and 'answer' in result_data:
        answer = result_data['answer']
        if isinstance(answer, str) and answer.strip():
            return answer.strip()
    
    # 新格式：从llm_recommendations解析
    if 'llm_recommendations' in result_data:
        llm_rec = result_data['llm_recommendations']
        if isinstance(llm_rec, dict) and 'recommendations' in llm_rec:
            recommendations = llm_rec['recommendations']
            if isinstance(recommendations, list) and recommendations:
                # 将推荐结果转换为文本
                rec_texts = []
                for rec in recommendations:
                    if isinstance(rec, dict) and 'procedure_name' in rec:
                        rank = rec.get('rank', '')
                        procedure = rec.get('procedure_name', '')
                        rating = rec.get('appropriateness_rating', '')
                        reason = rec.get('recommendation_reason', '')
                        
                        rec_text = f"推荐{rank}: {procedure}"
                        if rating:
                            rec_text += f" (适宜性: {rating})"
                        if reason:
                            rec_text += f" - {reason}"
                        rec_texts.append(rec_text)
                
                if rec_texts:
                    return "\\n".join(rec_texts)
    
    return None

def extract_contexts_from_result(result_data, inference_method):
    """从result数据中提取上下文"""
    contexts = []
    
    if not result_data or not isinstance(result_data, dict):
        return contexts
    
    # 直接从contexts字段获取
    if 'contexts' in result_data:
        contexts_data = result_data['contexts']
        if isinstance(contexts_data, list):
            for ctx in contexts_data:
                if isinstance(ctx, str) and ctx.strip():
                    contexts.append(ctx.strip())
                elif isinstance(ctx, dict):
                    # 尝试从字典中提取文本
                    for key in ['content', 'text', 'description']:
                        if key in ctx and isinstance(ctx[key], str) and ctx[key].strip():
                            contexts.append(ctx[key].strip())
                            break
    
    # 从scenarios获取上下文
    if 'scenarios' in result_data:
        scenarios = result_data['scenarios']
        if isinstance(scenarios, list):
            for scenario in scenarios:
                if isinstance(scenario, dict):
                    # 构建场景描述作为上下文
                    context_parts = []
                    if 'description_zh' in scenario:
                        context_parts.append(f"场景: {scenario['description_zh']}")
                    if 'clinical_context' in scenario:
                        context_parts.append(f"临床背景: {scenario['clinical_context']}")
                    if 'patient_population' in scenario:
                        context_parts.append(f"患者群体: {scenario['patient_population']}")
                    
                    if context_parts:
                        contexts.append(" | ".join(context_parts))
    
    return contexts

def debug_data_extraction():
    """调试数据提取过程"""
    print("=" * 70)
    print("RAGAS数据流调试")
    print("=" * 70)
    
    try:
        from app.core.database import get_db
        from app.models.system_models import InferenceLog
        
        # 获取数据库会话
        db = next(get_db())
        
        # 查询指定ID的推理记录
        run_ids = [42, 43, 44]
        runs = db.query(InferenceLog).filter(InferenceLog.id.in_(run_ids)).all()
        
        print(f"\\n📊 查询到 {len(runs)} 条推理记录")
        
        ragas_data_list = []
        
        for run in runs:
            print(f"\\n🔍 处理记录 ID: {run.id}")
            print(f"   查询: {run.query_text}")
            print(f"   推理方法: {run.inference_method}")
            
            if not run.result:
                print("   ❌ 无结果数据")
                continue
            
            result = run.result if isinstance(run.result, dict) else json.loads(run.result)
            
            # 提取答案
            answer = extract_answer_from_result(result, run.inference_method)
            print(f"   答案提取: {'✅' if answer else '❌'}")
            if answer:
                print(f"   答案内容: {answer[:100]}...")
            
            # 提取上下文
            contexts = extract_contexts_from_result(result, run.inference_method)
            print(f"   上下文提取: {'✅' if contexts else '❌'}")
            print(f"   上下文数量: {len(contexts)}")
            if contexts:
                print(f"   第一个上下文: {contexts[0][:80]}...")
            
            # 构建RAGAS数据
            ragas_data = {
                "question": run.query_text,
                "answer": answer or "无答案",
                "contexts": contexts or ["无上下文"],
                "ground_truth": "",  # 暂时为空
                "run_id": run.id,
                "inference_method": run.inference_method
            }
            
            ragas_data_list.append(ragas_data)
            
            print(f"   RAGAS数据构建: ✅")
            print(f"   - 问题长度: {len(ragas_data['question'])}")
            print(f"   - 答案长度: {len(ragas_data['answer'])}")
            print(f"   - 上下文数量: {len(ragas_data['contexts'])}")
        
        db.close()
        
        # 保存调试数据
        debug_file = f"debug_ragas_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(debug_file, 'w', encoding='utf-8') as f:
            json.dump(ragas_data_list, f, ensure_ascii=False, indent=2)
        
        print(f"\\n💾 调试数据已保存到: {debug_file}")
        
        return ragas_data_list
        
    except Exception as e:
        print(f"❌ 数据提取失败: {e}")
        logger.error(f"详细错误: {e}", exc_info=True)
        return []

def test_ragas_evaluation(ragas_data_list):
    """测试RAGAS评测"""
    if not ragas_data_list:
        print("\\n❌ 无数据可测试")
        return
    
    print(f"\\n🧪 开始RAGAS评测测试")
    
    try:
        from app.services.ragas_evaluator_v2 import ACRACRAGASEvaluator
        
        # 创建评估器
        evaluator = ACRACRAGASEvaluator()
        print("✅ 评估器创建成功")
        
        # 测试单个样本
        test_sample = ragas_data_list[0]
        print(f"\\n🔬 测试样本:")
        print(f"   问题: {test_sample['question']}")
        print(f"   答案: {test_sample['answer'][:100]}...")
        print(f"   上下文数量: {len(test_sample['contexts'])}")
        
        # 显示完整的提交数据
        print(f"\\n📋 提交给RAGAS的完整数据:")
        print(json.dumps(test_sample, ensure_ascii=False, indent=2))
        
        # 执行评测
        print(f"\\n⚡ 开始评测...")
        scores = evaluator.evaluate_sample(test_sample)
        
        print(f"\\n📊 评测结果:")
        for metric, score in scores.items():
            status = "✅" if score > 0 else "⚠️"
            print(f"   {status} {metric}: {score:.4f}")
        
        return scores
        
    except Exception as e:
        print(f"❌ 评测失败: {e}")
        logger.error(f"详细错误: {e}", exc_info=True)
        return None

def main():
    """主函数"""
    # 1. 调试数据提取
    ragas_data_list = debug_data_extraction()
    
    # 2. 测试RAGAS评测
    if ragas_data_list:
        test_ragas_evaluation(ragas_data_list)
    
    print("\\n" + "=" * 70)
    print("🎯 调试完成")
    print("=" * 70)

if __name__ == "__main__":
    main()