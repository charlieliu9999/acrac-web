#!/usr/bin/env python3
"""
API测试演示脚本

快速演示向量搜索API的连通性和基本功能
"""

import asyncio
import aiohttp
import time
import json
from datetime import datetime

# 测试配置
API_BASE_URL = "http://localhost:8001"
TEST_QUERIES = [
    "45岁女性，慢性反复头痛3年",
    "突发剧烈头痛",
    "胸痛伴气促"
]

class QuickAPITester:
    """快速API测试器"""
    
    def __init__(self):
        self.base_url = API_BASE_URL
        self.results = []
    
    async def test_health_check(self):
        """测试健康检查"""
        print("🔍 测试健康检查...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ 健康检查通过: {data}")
                        return True
                    else:
                        print(f"❌ 健康检查失败: HTTP {response.status}")
                        return False
        except Exception as e:
            print(f"❌ 健康检查异常: {str(e)}")
            return False
    
    async def test_vector_search_comprehensive(self, query):
        """测试综合向量搜索"""
        print(f"🔍 测试综合向量搜索: '{query}'")
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/api/v1/acrac/vector/v2/search/comprehensive"
                payload = {
                    "query_text": query,
                    "top_k": 5,
                    "similarity_threshold": 0.0
                }
                
                start_time = time.time()
                async with session.post(url, json=payload) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ 搜索成功 - 响应时间: {response_time:.2f}ms")
                        print(f"   📊 结果统计:")
                        print(f"   - 科室: {len(data.get('panels', []))}条")
                        print(f"   - 主题: {len(data.get('topics', []))}条")
                        print(f"   - 临床场景: {len(data.get('scenarios', []))}条")
                        print(f"   - 检查项目: {len(data.get('procedures', []))}条")
                        print(f"   - 临床推荐: {len(data.get('recommendations', []))}条")
                        print(f"   - 总结果: {data.get('total_results', 0)}条")
                        
                        # 显示前几个推荐
                        if data.get('recommendations'):
                            print(f"   🏥 热门推荐:")
                            for i, rec in enumerate(data['recommendations'][:3], 1):
                                procedure_name = rec.get('procedure_name', 'N/A')
                                similarity = rec.get('similarity_score', 0)
                                rating = rec.get('appropriateness_rating', 'N/A')
                                print(f"      {i}. {procedure_name} (相似度: {similarity:.3f}, 评分: {rating})")
                        
                        return True
                    else:
                        print(f"❌ 搜索失败: HTTP {response.status}")
                        error_data = await response.text()
                        print(f"   错误详情: {error_data}")
                        return False
                        
        except Exception as e:
            print(f"❌ 搜索异常: {str(e)}")
            return False
    
    async def test_database_stats(self):
        """测试数据库统计"""
        print("🔍 测试数据库统计...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/v1/acrac/vector/v2/stats") as response:
                    if response.status == 200:
                        data = await response.json()
                        print("✅ 数据库统计获取成功:")
                        
                        for key, value in data.items():
                            if key.endswith('_count'):
                                print(f"   📊 {key}: {value}")
                            elif key.endswith('_coverage'):
                                print(f"   📈 {key}: {value:.2%}")
                        
                        return True
                    else:
                        print(f"❌ 统计获取失败: HTTP {response.status}")
                        return False
        except Exception as e:
            print(f"❌ 统计获取异常: {str(e)}")
            return False
    
    async def run_quick_tests(self):
        """运行快速测试"""
        print("🚀 开始API快速连通性测试")
        print("=" * 50)
        
        test_results = []
        
        # 1. 健康检查
        print("\n1️⃣ 健康检查测试")
        health_result = await self.test_health_check()
        test_results.append(health_result)
        
        if not health_result:
            print("❌ 健康检查失败，跳过后续测试")
            print("\n💡 请确保API服务已启动:")
            print("   cd backend")
            print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
            return
        
        # 2. 数据库统计
        print("\n2️⃣ 数据库统计测试")
        stats_result = await self.test_database_stats()
        test_results.append(stats_result)
        
        # 3. 向量搜索测试
        print("\n3️⃣ 向量搜索功能测试")
        for i, query in enumerate(TEST_QUERIES, 1):
            print(f"\n3.{i} 测试查询 {i}")
            search_result = await self.test_vector_search_comprehensive(query)
            test_results.append(search_result)
        
        # 测试总结
        successful_tests = sum(test_results)
        total_tests = len(test_results)
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        print("\n" + "=" * 50)
        print("🎯 测试完成摘要")
        print("=" * 50)
        print(f"📊 成功测试: {successful_tests}/{total_tests}")
        print(f"📈 成功率: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 API连通性测试通过！系统运行正常")
            print("\n💡 现在可以运行完整测试:")
            print("   python tests/run_all_tests.py")
        elif success_rate >= 50:
            print("⚠️ API基本可用，但存在部分问题")
            print("\n💡 建议检查:")
            print("   - 数据库服务是否正常")
            print("   - 向量嵌入服务配置")
            print("   - API路由和依赖")
        else:
            print("❌ API存在严重问题，需要检查配置")
            print("\n💡 排查建议:")
            print("   1. 检查API服务启动状态")
            print("   2. 检查数据库连接")
            print("   3. 检查依赖服务配置")
        
        return success_rate

async def main():
    """主函数"""
    print(f"🏥 ACRAC API连通性快速测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 API地址: {API_BASE_URL}")
    print()
    
    tester = QuickAPITester()
    await tester.run_quick_tests()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试执行异常: {str(e)}")