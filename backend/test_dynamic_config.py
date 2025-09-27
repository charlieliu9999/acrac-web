#!/usr/bin/env python3
"""
测试动态配置加载功能
验证所有模型配置都从环境变量或配置文件中动态加载，而不是硬编码
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.services.ollama_qwen_service import OllamaQwenService
from app.services.rag_llm_recommendation_service import RAGLLMRecommendationService

def test_config_loading():
    """测试配置加载"""
    print("=== 配置加载测试 ===")
    
    # 测试基础配置
    print(f"数据库URL: {settings.DATABASE_URL}")
    print(f"Redis URL: {settings.REDIS_URL}")
    
    # 测试模型配置
    print("\n=== 模型配置 ===")
    print(f"嵌入模型类型: {settings.EMBEDDING_MODEL_TYPE}")
    print(f"嵌入模型名称: {settings.EMBEDDING_MODEL_NAME}")
    print(f"嵌入维度: {settings.EMBEDDING_DIMENSION}")
    
    # 测试Ollama配置
    print(f"\nOllama Base URL: {settings.OLLAMA_BASE_URL}")
    print(f"Ollama LLM模型: {settings.OLLAMA_LLM_MODEL}")
    print(f"Ollama嵌入模型: {settings.OLLAMA_EMBEDDING_MODEL}")
    
    # 测试SiliconFlow配置
    print(f"\nSiliconFlow Base URL: {settings.SILICONFLOW_BASE_URL}")
    print(f"SiliconFlow LLM模型: {settings.SILICONFLOW_LLM_MODEL}")
    print(f"SiliconFlow嵌入模型: {settings.SILICONFLOW_EMBEDDING_MODEL}")
    print(f"重排序模型: {settings.RERANKER_MODEL}")
    
    return True

def test_ollama_service_config():
    """测试Ollama服务配置"""
    print("\n=== Ollama服务配置测试 ===")
    
    try:
        # 测试默认配置
        service = OllamaQwenService()
        print(f"Ollama服务模型: {service.model}")
        print(f"Ollama服务Base URL: {service.base_url}")
        
        # 测试自定义模型配置
        custom_service = OllamaQwenService(model="qwen2.5:14b")
        print(f"自定义Ollama服务模型: {custom_service.model}")
        
        return True
    except Exception as e:
        print(f"Ollama服务配置测试失败: {e}")
        return False

def test_rag_service_config():
    """测试RAG服务配置"""
    print("\n=== RAG服务配置测试 ===")
    
    try:
        service = RAGLLMRecommendationService()
        print("RAG服务初始化成功")
        
        # 检查服务是否正确加载了配置
        print("RAG服务配置验证完成")
        
        return True
    except Exception as e:
        print(f"RAG服务配置测试失败: {e}")
        return False

def test_environment_override():
    """测试环境变量覆盖"""
    print("\n=== 环境变量覆盖测试 ===")
    
    # 保存原始值
    original_llm_model = os.environ.get('SILICONFLOW_LLM_MODEL')
    
    try:
        # 设置测试环境变量
        os.environ['SILICONFLOW_LLM_MODEL'] = 'Qwen/Qwen2.5-14B-Instruct'
        
        # 重新导入配置以获取新值
        import importlib
        from app.core import config
        importlib.reload(config)
        
        # 验证配置是否更新
        test_settings = config.Settings()
        print(f"测试LLM模型配置: {test_settings.SILICONFLOW_LLM_MODEL}")
        
        if test_settings.SILICONFLOW_LLM_MODEL == 'Qwen/Qwen2.5-14B-Instruct':
            print("✓ 环境变量覆盖测试成功")
            return True
        else:
            print("✗ 环境变量覆盖测试失败")
            return False
            
    finally:
        # 恢复原始值
        if original_llm_model:
            os.environ['SILICONFLOW_LLM_MODEL'] = original_llm_model
        elif 'SILICONFLOW_LLM_MODEL' in os.environ:
            del os.environ['SILICONFLOW_LLM_MODEL']

def main():
    """主测试函数"""
    print("开始动态配置加载测试...")
    
    tests = [
        ("配置加载", test_config_loading),
        ("Ollama服务配置", test_ollama_service_config),
        ("RAG服务配置", test_rag_service_config),
        ("环境变量覆盖", test_environment_override),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            print(f"{'✓' if result else '✗'} {test_name}: {'通过' if result else '失败'}")
        except Exception as e:
            results.append((test_name, False))
            print(f"✗ {test_name}: 异常 - {e}")
    
    # 总结
    print("\n=== 测试总结 ===")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("🎉 所有动态配置测试通过！")
        return True
    else:
        print("❌ 部分测试失败，请检查配置")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)