#!/usr/bin/env python3
"""
简化的查询已存储推理数据脚本
直接使用SQL查询，避免复杂的配置问题
"""

import os
import json
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

def main():
    """主函数：查询并显示已存储的推理数据"""
    
    # 加载环境变量
    load_dotenv()
    
    # 获取数据库连接参数
    db_params = {
        'host': os.getenv('PGHOST', '127.0.0.1'),
        'port': os.getenv('PGPORT', '5432'),
        'database': os.getenv('PGDATABASE', 'acrac_db'),
        'user': os.getenv('PGUSER', 'postgres'),
        'password': os.getenv('PGPASSWORD', 'password')
    }
    
    try:
        # 连接数据库
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        
        print("=== 查询已存储的推理数据 ===\n")
        
        # 1. 查询最近的评测任务
        print("1. 最近的评测任务:")
        cursor.execute("""
            SELECT task_id, status, created_at, progress_percentage, evaluation_config
            FROM evaluation_tasks 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        tasks = cursor.fetchall()
        if not tasks:
            print("   未找到任何评测任务")
        else:
            for i, (task_id, status, created_at, progress, config) in enumerate(tasks, 1):
                print(f"   任务 {i}:")
                print(f"     Task ID: {task_id}")
                print(f"     Status: {status}")
                print(f"     Created: {created_at}")
                print(f"     Progress: {progress}%")
                if config:
                    try:
                        config_dict = json.loads(config) if isinstance(config, str) else config
                        print(f"     Model: {config_dict.get('model_name', 'N/A')}")
                    except:
                        print(f"     Config: {str(config)[:50]}...")
                print()
        
        # 2. 查询已完成的推理结果
        print("2. 已完成的推理结果:")
        cursor.execute("""
            SELECT scenario_id, task_id, status, overall_score, created_at, 
                   inference_data, ragas_scores
            FROM scenario_results 
            WHERE status = 'completed'
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        results = cursor.fetchall()
        if not results:
            print("   未找到已完成的推理结果")
        else:
            for i, (scenario_id, task_id, status, score, created_at, inference_data, ragas_scores) in enumerate(results, 1):
                print(f"   结果 {i}:")
                print(f"     Scenario ID: {scenario_id}")
                print(f"     Task ID: {task_id}")
                print(f"     Status: {status}")
                print(f"     Overall Score: {score}")
                print(f"     Created: {created_at}")
                
                # 显示推理数据的关键信息
                if inference_data:
                    try:
                        data = json.loads(inference_data) if isinstance(inference_data, str) else inference_data
                        print(f"     推理数据:")
                        print(f"       Query: {data.get('query', 'N/A')[:100]}...")
                        print(f"       Answer: {data.get('answer', 'N/A')[:100]}...")
                        
                        # 显示上下文信息
                        contexts = data.get('contexts', [])
                        if contexts:
                            print(f"       Contexts: {len(contexts)} 个上下文")
                            for j, ctx in enumerate(contexts[:2], 1):  # 只显示前2个
                                print(f"         Context {j}: {str(ctx)[:80]}...")
                    except Exception as e:
                        print(f"     推理数据解析错误: {e}")
                
                # 显示RAGAS评分
                if ragas_scores:
                    try:
                        scores = json.loads(ragas_scores) if isinstance(ragas_scores, str) else ragas_scores
                        print(f"     RAGAS评分:")
                        for metric, score in scores.items():
                            print(f"       {metric}: {score}")
                    except Exception as e:
                        print(f"     RAGAS评分解析错误: {e}")
                
                print()
        
        # 3. 统计信息
        print("3. 数据统计:")
        cursor.execute("SELECT COUNT(*) FROM evaluation_tasks")
        total_tasks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM evaluation_tasks WHERE status = 'completed'")
        completed_tasks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM scenario_results")
        total_results = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM scenario_results WHERE status = 'completed'")
        completed_results = cursor.fetchone()[0]
        
        print(f"   总评测任务数: {total_tasks}")
        print(f"   已完成任务数: {completed_tasks}")
        print(f"   总推理结果数: {total_results}")
        print(f"   已完成结果数: {completed_results}")
        
        # 4. 选择一个具体的推理结果进行详细分析
        if results:
            print("\n4. 选择第一个推理结果进行详细分析:")
            selected_result = results[0]
            scenario_id, task_id, status, score, created_at, inference_data, ragas_scores = selected_result
            
            print(f"   选中结果: Scenario ID {scenario_id}")
            
            # 提取用于RAGAS评测的数据
            if inference_data:
                try:
                    data = json.loads(inference_data) if isinstance(inference_data, str) else inference_data
                    
                    print("\n   === 提取的RAGAS评测数据 ===")
                    print(f"   Question: {data.get('query', 'N/A')}")
                    print(f"   Answer: {data.get('answer', 'N/A')}")
                    
                    contexts = data.get('contexts', [])
                    print(f"   Contexts ({len(contexts)} 个):")
                    for i, ctx in enumerate(contexts, 1):
                        print(f"     {i}. {str(ctx)[:200]}...")
                    
                    # 如果有ground_truth，也显示
                    ground_truth = data.get('ground_truth')
                    if ground_truth:
                        print(f"   Ground Truth: {ground_truth}")
                    
                    # 保存这个数据样本到文件，供后续RAGAS评测使用
                    sample_data = {
                        'scenario_id': scenario_id,
                        'task_id': task_id,
                        'question': data.get('query', ''),
                        'answer': data.get('answer', ''),
                        'contexts': contexts,
                        'ground_truth': ground_truth
                    }
                    
                    # 保存到JSON文件
                    output_file = 'extracted_inference_sample.json'
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(sample_data, f, ensure_ascii=False, indent=2)
                    
                    print(f"\n   数据样本已保存到: {output_file}")
                    return scenario_id, task_id, sample_data
                    
                except Exception as e:
                    print(f"   数据提取错误: {e}")
        
    except Exception as e:
        print(f"查询数据时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
    
    return None, None, None

if __name__ == "__main__":
    scenario_id, task_id, sample_data = main()
    if scenario_id and task_id:
        print(f"\n可用于评测的数据: Scenario ID {scenario_id}, Task ID {task_id}")
        print("数据样本已准备就绪，可以进行RAGAS评测")