#!/usr/bin/env python3
"""
真实数据评测脚本
使用增强版RAGAS评估器对真实推理数据进行完整评测
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
                            rec_text += f" - {reason[:100]}..."  # 限制长度
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

def load_real_data():
    """加载真实推理数据"""
    try:
        from app.core.database import get_db
        from app.models.system_models import InferenceLog
        
        # 获取数据库会话
        db = next(get_db())
        
        # 查询指定ID的推理记录
        run_ids = [42, 43, 44]
        runs = db.query(InferenceLog).filter(InferenceLog.id.in_(run_ids)).all()
        
        print(f"📊 从数据库加载了 {len(runs)} 条推理记录")
        
        ragas_data_list = []
        
        for run in runs:
            print(f"\\n🔍 处理记录 ID: {run.id}")
            print(f"   查询: {run.query_text}")
            
            if not run.result:
                print("   ❌ 无结果数据，跳过")
                continue
            
            result = run.result if isinstance(run.result, dict) else json.loads(run.result)
            
            # 提取答案
            answer = extract_answer_from_result(result, run.inference_method)
            if not answer:
                print("   ❌ 无法提取答案，跳过")
                continue
            
            # 提取上下文
            contexts = extract_contexts_from_result(result, run.inference_method)
            if not contexts:
                print("   ❌ 无法提取上下文，跳过")
                continue
            
            # 构建RAGAS数据
            ragas_data = {
                "question": run.query_text,
                "answer": answer,
                "contexts": contexts,
                "ground_truth": "",  # 暂时为空
                "run_id": run.id,
                "inference_method": run.inference_method
            }
            
            ragas_data_list.append(ragas_data)
            print(f"   ✅ 数据提取成功")
            print(f"      - 问题: {len(ragas_data['question'])} 字符")
            print(f"      - 答案: {len(ragas_data['answer'])} 字符")
            print(f"      - 上下文: {len(ragas_data['contexts'])} 个")
        
        db.close()
        return ragas_data_list
        
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        logger.error(f"详细错误: {e}", exc_info=True)
        return []

def run_evaluation():
    """运行完整评测"""
    print("=" * 70)
    print("真实数据RAGAS评测")
    print("=" * 70)
    
    # 1. 加载真实数据
    real_data = load_real_data()
    if not real_data:
        print("❌ 无真实数据可评测")
        return
    
    # 2. 创建增强版评估器
    try:
        from enhanced_ragas_evaluator import EnhancedRAGASEvaluator
        evaluator = EnhancedRAGASEvaluator()
        print(f"\\n✅ 增强版评估器创建成功")
    except Exception as e:
        print(f"❌ 评估器创建失败: {e}")
        return
    
    # 3. 运行批量评测
    print(f"\\n🚀 开始评测 {len(real_data)} 条真实数据")
    
    results = evaluator.evaluate_batch(real_data)
    
    # 4. 显示详细结果
    print(f"\\n📊 评测结果详情:")
    print(f"{'ID':<4} {'临床场景':<30} {'Faithfulness':<12} {'Answer Relevancy':<15} {'Context Precision':<16} {'Context Recall':<13}")
    print("-" * 100)
    
    for i, (data, scores) in enumerate(zip(real_data, results['individual_scores'])):
        run_id = data['run_id']
        question = data['question'][:25] + "..." if len(data['question']) > 25 else data['question']
        
        print(f"{run_id:<4} {question:<30} {scores['faithfulness']:<12.3f} {scores['answer_relevancy']:<15.3f} {scores['context_precision']:<16.3f} {scores['context_recall']:<13.3f}")
    
    # 5. 显示汇总结果
    print(f"\\n📈 汇总结果:")
    avg_scores = results['avg_scores']
    total_score = 0
    valid_metrics = 0
    
    for metric, score in avg_scores.items():
        status = "✅" if score > 0 else "⚠️"
        print(f"   {status} {metric}: {score:.4f}")
        if score > 0:
            total_score += score
            valid_metrics += 1
    
    if valid_metrics > 0:
        overall_avg = total_score / valid_metrics
        print(f"\\n🎯 总体平均分: {overall_avg:.4f}")
        print(f"📊 有效指标: {valid_metrics}/4 ({(valid_metrics/4)*100:.1f}%)")
        
        if valid_metrics == 4:
            print(f"\\n🎉 评测成功！所有指标都正常工作")
        elif valid_metrics >= 3:
            print(f"\\n✅ 评测基本成功，大部分指标正常")
        else:
            print(f"\\n⚠️  评测部分成功，仍需优化")
    else:
        print(f"\\n❌ 评测失败，所有指标都为0")
    
    # 6. 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = f"real_data_evaluation_results_{timestamp}.json"
    
    # 添加原始数据到结果中
    full_results = {
        'evaluation_results': results,
        'original_data': real_data,
        'metadata': {
            'timestamp': timestamp,
            'evaluator': 'EnhancedRAGASEvaluator',
            'total_samples': len(real_data),
            'valid_metrics': valid_metrics,
            'overall_average': overall_avg if valid_metrics > 0 else 0.0
        }
    }
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(full_results, f, ensure_ascii=False, indent=2)
    
    print(f"\\n💾 详细结果已保存到: {result_file}")
    
    return results

if __name__ == "__main__":
    run_evaluation()
    
    print("\\n" + "=" * 70)
    print("🎯 真实数据评测完成")
    print("=" * 70)