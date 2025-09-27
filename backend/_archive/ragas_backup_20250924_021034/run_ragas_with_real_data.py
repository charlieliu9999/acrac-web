#!/usr/bin/env python3
"""
使用真实推理数据运行RAGAS评测
"""

import os
import json
import pandas as pd
from datetime import datetime
from datasets import Dataset

# 设置环境变量
os.environ["NUMEXPR_MAX_THREADS"] = "8"

# RAGAS相关导入
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
    answer_correctness,
    answer_similarity
)

# LangChain相关导入
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

def setup_models():
    """设置评测模型"""
    print("=== 设置评测模型 ===")
    
    # SiliconFlow API配置
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    llm_model = os.getenv("SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    embedding_model = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")
    
    if not api_key:
        raise ValueError("请设置 SILICONFLOW_API_KEY 环境变量")
    
    print(f"LLM模型: {llm_model}")
    print(f"嵌入模型: {embedding_model}")
    
    # 初始化模型
    llm = ChatOpenAI(
        model=llm_model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.1
    )
    
    embeddings = OpenAIEmbeddings(
        model=embedding_model,
        api_key=api_key,
        base_url=base_url
    )
    
    return llm, embeddings

def load_real_data(filename):
    """加载真实推理数据"""
    print(f"=== 加载真实数据: {filename} ===")
    
    if not os.path.exists(filename):
        raise FileNotFoundError(f"数据文件不存在: {filename}")
    
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"加载了 {len(data)} 条数据")
    
    # 转换为RAGAS格式
    ragas_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": []
    }
    
    for item in data:
        ragas_data["question"].append(item["question"])
        ragas_data["answer"].append(item["answer"])
        ragas_data["contexts"].append(item["contexts"])
        # 由于没有标准答案，使用answer作为ground_truth
        ragas_data["ground_truth"].append(item["answer"])
    
    return ragas_data

def run_ragas_evaluation(data, llm, embeddings):
    """运行RAGAS评测"""
    print("=== 开始RAGAS评测 ===")
    
    # 创建数据集
    dataset = Dataset.from_dict(data)
    print(f"数据集大小: {len(dataset)}")
    
    # 选择评测指标
    metrics = [
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness
    ]
    
    # 只有当有ground_truth时才使用这些指标
    if any(gt for gt in data["ground_truth"]):
        metrics.extend([
            answer_correctness,
            answer_similarity
        ])
    
    print(f"使用的评测指标: {[metric.name for metric in metrics]}")
    
    try:
        # 运行评测
        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=llm,
            embeddings=embeddings
        )
        
        print("✅ RAGAS评测完成")
        return result
        
    except Exception as e:
        print(f"❌ RAGAS评测失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def analyze_results(result, data):
    """分析评测结果"""
    if not result:
        print("❌ 没有评测结果可分析")
        return
    
    print("\n=== 评测结果分析 ===")
    
    # 转换为DataFrame便于分析
    df = result.to_pandas()
    
    print(f"评测数据条数: {len(df)}")
    print(f"评测指标: {list(df.columns)}")
    
    # 计算各指标的统计信息
    numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns
    
    print("\n📊 指标统计:")
    for col in numeric_columns:
        if col not in ['question', 'answer', 'contexts', 'ground_truth']:
            values = df[col].dropna()
            if len(values) > 0:
                print(f"  {col}:")
                print(f"    平均值: {values.mean():.4f}")
                print(f"    中位数: {values.median():.4f}")
                print(f"    标准差: {values.std():.4f}")
                print(f"    最小值: {values.min():.4f}")
                print(f"    最大值: {values.max():.4f}")
                print(f"    NaN数量: {df[col].isna().sum()}")
    
    # 检查NaN值
    print("\n🔍 NaN值检查:")
    for col in df.columns:
        nan_count = df[col].isna().sum()
        if nan_count > 0:
            print(f"  {col}: {nan_count} 个NaN值 ({nan_count/len(df)*100:.1f}%)")
    
    # 保存详细结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_filename = f"ragas_real_data_results_{timestamp}.csv"
    df.to_csv(result_filename, index=False, encoding='utf-8')
    print(f"\n📁 详细结果已保存到: {result_filename}")
    
    # 显示具体案例
    print("\n📋 具体案例分析:")
    for i, row in df.head(3).iterrows():
        print(f"\n案例 {i+1}:")
        print(f"  问题: {row['question'][:100]}...")
        print(f"  答案: {row['answer'][:100]}...")
        print(f"  上下文数量: {len(row['contexts']) if isinstance(row['contexts'], list) else 'N/A'}")
        
        for col in numeric_columns:
            if col not in ['question', 'answer', 'contexts', 'ground_truth']:
                value = row[col]
                if pd.notna(value):
                    print(f"  {col}: {value:.4f}")
                else:
                    print(f"  {col}: NaN")

def main():
    """主函数"""
    try:
        # 查找最新的数据文件
        data_files = [f for f in os.listdir('.') if f.startswith('correct_ragas_data_') and f.endswith('.json')]
        if not data_files:
            print("❌ 未找到真实推理数据文件")
            return
        
        # 使用最新的文件
        latest_file = sorted(data_files)[-1]
        print(f"使用数据文件: {latest_file}")
        
        # 设置模型
        llm, embeddings = setup_models()
        
        # 加载数据
        data = load_real_data(latest_file)
        
        # 运行评测
        result = run_ragas_evaluation(data, llm, embeddings)
        
        # 分析结果
        analyze_results(result, data)
        
        print("\n🎉 真实数据RAGAS评测完成！")
        
    except Exception as e:
        print(f"❌ 评测过程出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()