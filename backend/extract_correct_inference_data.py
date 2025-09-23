#!/usr/bin/env python3
"""
基于实际数据库表结构提取推理数据用于RAGAS评测
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# 数据库连接配置
DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '5432'),
    'database': os.getenv('PGDATABASE', 'acrac_db'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'password')
}

def extract_answer_from_result(result_data, inference_method):
    """从result数据中提取答案"""
    if not result_data or not isinstance(result_data, dict):
        return None
    
    # RAG方式：直接从answer字段获取
    if inference_method == 'rag' and 'answer' in result_data:
        answer = result_data['answer']
        if isinstance(answer, str) and answer.strip():
            return answer.strip()
    
    # No-RAG方式：从llm_raw_response解析
    if inference_method == 'no-rag' and 'llm_raw_response' in result_data:
        raw_response = result_data['llm_raw_response']
        if isinstance(raw_response, str) and raw_response.strip():
            try:
                # 尝试解析JSON
                parsed = json.loads(raw_response)
                if 'recommendations' in parsed and isinstance(parsed['recommendations'], list):
                    # 将推荐结果转换为文本
                    recommendations = []
                    for rec in parsed['recommendations']:
                        if isinstance(rec, dict) and 'procedure_name' in rec:
                            rank = rec.get('rank', '')
                            procedure = rec.get('procedure_name', '')
                            reason = rec.get('reason', '')
                            if procedure:
                                rec_text = f"推荐{rank}: {procedure}"
                                if reason:
                                    rec_text += f" - {reason}"
                                recommendations.append(rec_text)
                    
                    if recommendations:
                        return "\n".join(recommendations)
                
                # 如果没有recommendations，返回原始响应
                return raw_response
            except json.JSONDecodeError:
                # 如果不是JSON，直接返回原始响应
                return raw_response
    
    return None

def extract_contexts_from_result(result_data, inference_method):
    """从result数据中提取上下文"""
    contexts = []
    
    if not result_data or not isinstance(result_data, dict):
        return contexts
    
    # RAG方式：从contexts字段获取
    if inference_method == 'rag' and 'contexts' in result_data:
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
    
    # No-RAG方式：从scenarios获取上下文
    if inference_method == 'no-rag' and 'scenarios' in result_data:
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

def extract_ragas_data():
    """提取RAGAS评测数据"""
    try:
        # 连接数据库
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("=== 从数据库提取推理数据 ===")
        
        # 查询推理记录
        cursor.execute("""
            SELECT id, query_text, inference_method, result, success, created_at
            FROM inference_logs 
            WHERE success = true AND result IS NOT NULL
            ORDER BY created_at DESC 
            LIMIT 20;
        """)
        
        records = cursor.fetchall()
        print(f"查询到 {len(records)} 条推理记录")
        
        ragas_data = []
        
        for record in records:
            log_id = record['id']
            question = record['query_text']
            inference_method = record['inference_method']
            result_data = record['result']
            created_at = record['created_at']
            
            print(f"\n处理推理记录 {log_id}:")
            print(f"  查询: {question}")
            print(f"  方法: {inference_method}")
            
            # 提取答案
            answer = extract_answer_from_result(result_data, inference_method)
            
            # 提取上下文
            contexts = extract_contexts_from_result(result_data, inference_method)
            
            print(f"  答案长度: {len(answer) if answer else 0} 字符")
            print(f"  上下文数量: {len(contexts)}")
            
            # 检查数据完整性
            if question and answer:
                ragas_item = {
                    "question": question,
                    "answer": answer,
                    "contexts": contexts,
                    "ground_truth": None,  # 暂时没有标准答案
                    "inference_method": inference_method,
                    "log_id": log_id,
                    "created_at": created_at.isoformat() if created_at else None
                }
                ragas_data.append(ragas_item)
                print("  ✅ 数据完整，已添加")
            else:
                print("  ❌ 数据不完整，跳过")
                if not question:
                    print("    - 缺少问题")
                if not answer:
                    print("    - 缺少答案")
        
        cursor.close()
        conn.close()
        
        # 保存数据
        if ragas_data:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"correct_ragas_data_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(ragas_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n=== 数据提取完成 ===")
            print(f"✅ 成功提取 {len(ragas_data)} 条RAGAS评测数据")
            print(f"📁 数据已保存到: {filename}")
            
            # 统计信息
            method_counts = {}
            for item in ragas_data:
                method = item['inference_method']
                method_counts[method] = method_counts.get(method, 0) + 1
            
            print(f"📊 推理方法分布:")
            for method, count in method_counts.items():
                print(f"   {method}: {count} 条")
            
            # 显示示例数据
            if ragas_data:
                print(f"\n📋 示例数据:")
                example = ragas_data[0]
                print(f"   问题: {example['question'][:100]}...")
                print(f"   答案: {example['answer'][:100]}...")
                print(f"   上下文数量: {len(example['contexts'])}")
                
            return filename
        else:
            print("\n❌ 未能提取到任何有效的RAGAS数据")
            return None
            
    except Exception as e:
        print(f"提取数据时出错: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    extract_ragas_data()