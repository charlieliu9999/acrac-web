#!/usr/bin/env python3
"""
查询已存储的推理数据脚本
用于从数据库中提取推理结果进行RAGAS评测
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.ragas_models import EvaluationTask, ScenarioResult
from app.core.config import settings

def main():
    """主函数：查询并显示已存储的推理数据"""
    
    # 加载环境变量
    load_dotenv()
    
    # 创建数据库连接
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("错误：未找到DATABASE_URL环境变量")
        return
    
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        print("=== 查询已存储的推理数据 ===\n")
        
        # 1. 查询最近的评测任务
        print("1. 最近的评测任务:")
        tasks = db.query(EvaluationTask).order_by(EvaluationTask.created_at.desc()).limit(5).all()
        
        if not tasks:
            print("   未找到任何评测任务")
        else:
            for i, task in enumerate(tasks, 1):
                print(f"   任务 {i}:")
                print(f"     Task ID: {task.task_id}")
                print(f"     Status: {task.status}")
                print(f"     Created: {task.created_at}")
                print(f"     Progress: {task.progress_percentage}%")
                if task.evaluation_config:
                    config = task.evaluation_config
                    if isinstance(config, str):
                        config = json.loads(config)
                    print(f"     Model: {config.get('model_name', 'N/A')}")
                print()
        
        # 2. 查询已完成的推理结果
        print("2. 已完成的推理结果:")
        results = db.query(ScenarioResult).filter(
            ScenarioResult.status == 'completed'
        ).order_by(ScenarioResult.created_at.desc()).limit(5).all()
        
        if not results:
            print("   未找到已完成的推理结果")
        else:
            for i, result in enumerate(results, 1):
                print(f"   结果 {i}:")
                print(f"     Scenario ID: {result.scenario_id}")
                print(f"     Task ID: {result.task_id}")
                print(f"     Status: {result.status}")
                print(f"     Overall Score: {result.overall_score}")
                print(f"     Created: {result.created_at}")
                
                # 显示推理数据的关键信息
                if result.inference_data:
                    inference_data = result.inference_data
                    if isinstance(inference_data, str):
                        inference_data = json.loads(inference_data)
                    
                    print(f"     推理数据:")
                    print(f"       Query: {inference_data.get('query', 'N/A')[:100]}...")
                    print(f"       Answer: {inference_data.get('answer', 'N/A')[:100]}...")
                    
                    # 显示上下文信息
                    contexts = inference_data.get('contexts', [])
                    if contexts:
                        print(f"       Contexts: {len(contexts)} 个上下文")
                        for j, ctx in enumerate(contexts[:2], 1):  # 只显示前2个
                            print(f"         Context {j}: {str(ctx)[:80]}...")
                
                # 显示RAGAS评分
                if result.ragas_scores:
                    scores = result.ragas_scores
                    if isinstance(scores, str):
                        scores = json.loads(scores)
                    print(f"     RAGAS评分:")
                    for metric, score in scores.items():
                        print(f"       {metric}: {score}")
                
                print()
        
        # 3. 统计信息
        print("3. 数据统计:")
        total_tasks = db.query(EvaluationTask).count()
        completed_tasks = db.query(EvaluationTask).filter(EvaluationTask.status == 'completed').count()
        total_results = db.query(ScenarioResult).count()
        completed_results = db.query(ScenarioResult).filter(ScenarioResult.status == 'completed').count()
        
        print(f"   总评测任务数: {total_tasks}")
        print(f"   已完成任务数: {completed_tasks}")
        print(f"   总推理结果数: {total_results}")
        print(f"   已完成结果数: {completed_results}")
        
        # 4. 选择一个具体的推理结果进行详细分析
        if results:
            print("\n4. 选择第一个推理结果进行详细分析:")
            selected_result = results[0]
            print(f"   选中结果: Scenario ID {selected_result.scenario_id}")
            
            # 提取用于RAGAS评测的数据
            if selected_result.inference_data:
                inference_data = selected_result.inference_data
                if isinstance(inference_data, str):
                    inference_data = json.loads(inference_data)
                
                print("\n   提取的RAGAS评测数据:")
                print(f"   Question: {inference_data.get('query', 'N/A')}")
                print(f"   Answer: {inference_data.get('answer', 'N/A')}")
                
                contexts = inference_data.get('contexts', [])
                print(f"   Contexts ({len(contexts)} 个):")
                for i, ctx in enumerate(contexts, 1):
                    print(f"     {i}. {str(ctx)[:200]}...")
                
                # 如果有ground_truth，也显示
                ground_truth = inference_data.get('ground_truth')
                if ground_truth:
                    print(f"   Ground Truth: {ground_truth}")
                
                # 返回这个结果的ID，供后续评测使用
                return selected_result.scenario_id, selected_result.task_id
        
    except Exception as e:
        print(f"查询数据时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None
    
    finally:
        db.close()
    
    return None, None

if __name__ == "__main__":
    scenario_id, task_id = main()
    if scenario_id and task_id:
        print(f"\n可用于评测的数据: Scenario ID {scenario_id}, Task ID {task_id}")