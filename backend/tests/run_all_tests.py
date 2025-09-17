#!/usr/bin/env python3
"""
运行所有API测试的主脚本

这个脚本会依次运行：
1. 数据库向量功能测试
2. 向量搜索API测试
3. 综合API测试

并生成完整的测试报告
"""

import asyncio
import json
import time
import logging
import sys
import os
from typing import Dict, Any
from datetime import datetime

# 添加项目根目录到path
sys.path.append('/Users/charlieliu/git_project_vscode/09_medical/ACRAC-web/backend')

from tests.test_database_vector import DatabaseVectorTester
from tests.test_vector_search_api import VectorSearchAPITester
from tests.test_comprehensive_api import ComprehensiveAPITester

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_execution.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class MasterTestRunner:
    """主测试运行器"""
    
    def __init__(self):
        self.start_time = time.time()
        self.results = {
            "test_execution": {
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "total_duration_seconds": 0,
                "python_version": sys.version,
                "working_directory": os.getcwd()
            },
            "test_phases": {
                "database_vector": None,
                "vector_search_api": None,
                "comprehensive_api": None
            },
            "summary": {
                "total_tests_run": 0,
                "total_tests_passed": 0,
                "total_tests_failed": 0,
                "overall_success_rate": 0.0,
                "critical_failures": [],
                "recommendations": []
            }
        }
    
    def run_database_tests(self) -> Dict[str, Any]:
        """运行数据库测试"""
        logger.info("🔄 第一阶段: 数据库向量功能测试")
        logger.info("=" * 50)
        
        try:
            tester = DatabaseVectorTester()
            results = tester.run_all_tests()
            
            if results["overall_success"]:
                logger.info("✅ 数据库测试阶段完成 - 所有测试通过")
            else:
                logger.warning("⚠️ 数据库测试阶段完成 - 部分测试失败")
                
                # 记录关键失败
                if not results["database_connection"]["success"]:
                    self.results["summary"]["critical_failures"].append("数据库连接失败")
                
                if not results["pgvector_extension"]["pgvector_installed"]:
                    self.results["summary"]["critical_failures"].append("pgvector扩展未安装")
                
                if not results["embedding_generation"]["success"]:
                    self.results["summary"]["critical_failures"].append("向量生成失败")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 数据库测试阶段异常: {str(e)}")
            return {
                "overall_success": False,
                "error": str(e),
                "database_connection": {"success": False},
                "pgvector_extension": {"pgvector_installed": False},
                "embedding_generation": {"success": False}
            }
    
    async def run_vector_search_api_tests(self) -> Dict[str, Any]:
        """运行向量搜索API测试"""
        logger.info("\n🔄 第二阶段: 向量搜索API测试")
        logger.info("=" * 50)
        
        try:
            async with VectorSearchAPITester() as tester:
                results = await tester.run_all_tests()
                
                success_rate = results["test_summary"]["success_rate"]
                if success_rate >= 80:
                    logger.info(f"✅ 向量搜索API测试阶段完成 - 成功率: {success_rate:.1f}%")
                else:
                    logger.warning(f"⚠️ 向量搜索API测试阶段完成 - 成功率: {success_rate:.1f}%")
                    self.results["summary"]["critical_failures"].append(f"向量搜索API成功率低: {success_rate:.1f}%")
                
                return results
                
        except Exception as e:
            logger.error(f"❌ 向量搜索API测试阶段异常: {str(e)}")
            return {
                "test_summary": {
                    "success_rate": 0.0,
                    "total_tests": 0,
                    "passed_tests": 0,
                    "failed_tests": 0
                },
                "error": str(e)
            }
    
    async def run_comprehensive_api_tests(self) -> Dict[str, Any]:
        """运行综合API测试"""
        logger.info("\n🔄 第三阶段: 综合API测试")
        logger.info("=" * 50)
        
        try:
            async with ComprehensiveAPITester() as tester:
                results = await tester.run_comprehensive_tests()
                
                e2e_success_rate = results["end_to_end_scenarios"]["success_rate"]
                if e2e_success_rate >= 70:
                    logger.info(f"✅ 综合API测试阶段完成 - 端到端成功率: {e2e_success_rate:.1f}%")
                else:
                    logger.warning(f"⚠️ 综合API测试阶段完成 - 端到端成功率: {e2e_success_rate:.1f}%")
                    self.results["summary"]["critical_failures"].append(f"端到端测试成功率低: {e2e_success_rate:.1f}%")
                
                return results
                
        except Exception as e:
            logger.error(f"❌ 综合API测试阶段异常: {str(e)}")
            return {
                "end_to_end_scenarios": {
                    "success_rate": 0.0,
                    "total_scenarios": 0,
                    "successful_scenarios": 0
                },
                "error": str(e)
            }
    
    def analyze_results(self):
        """分析测试结果并生成建议"""
        logger.info("\n📊 分析测试结果...")
        
        # 计算总体统计
        db_results = self.results["test_phases"]["database_vector"]
        api_results = self.results["test_phases"]["vector_search_api"]
        comprehensive_results = self.results["test_phases"]["comprehensive_api"]
        
        total_tests = 0
        passed_tests = 0
        
        # 数据库测试统计
        if db_results:
            db_success = db_results.get("overall_success", False)
            total_tests += 6  # 数据库有6个主要测试
            if db_success:
                passed_tests += 6
        
        # API测试统计
        if api_results and "test_summary" in api_results:
            total_tests += api_results["test_summary"]["total_tests"]
            passed_tests += api_results["test_summary"]["passed_tests"]
        
        # 综合测试统计（端到端场景）
        if comprehensive_results and "end_to_end_scenarios" in comprehensive_results:
            scenarios = comprehensive_results["end_to_end_scenarios"]
            total_tests += scenarios["total_scenarios"]
            passed_tests += scenarios["successful_scenarios"]
        
        # 更新汇总信息
        self.results["summary"]["total_tests_run"] = total_tests
        self.results["summary"]["total_tests_passed"] = passed_tests
        self.results["summary"]["total_tests_failed"] = total_tests - passed_tests
        self.results["summary"]["overall_success_rate"] = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # 生成建议
        recommendations = []
        
        if not db_results or not db_results.get("overall_success", False):
            recommendations.append("🔧 检查数据库连接和pgvector扩展安装")
            recommendations.append("🔧 验证向量嵌入服务(SiliconFlow API)配置")
        
        if api_results and api_results["test_summary"]["success_rate"] < 80:
            recommendations.append("🔧 检查API服务启动状态和端口配置")
            recommendations.append("🔧 验证API路由配置和依赖服务")
        
        if comprehensive_results and comprehensive_results["end_to_end_scenarios"]["success_rate"] < 70:
            recommendations.append("🔧 优化向量搜索算法和相似度阈值")
            recommendations.append("🔧 检查临床推荐数据的完整性和质量")
        
        if self.results["summary"]["overall_success_rate"] >= 90:
            recommendations.append("🎉 系统状态优秀，可以投入生产使用")
        elif self.results["summary"]["overall_success_rate"] >= 70:
            recommendations.append("⚠️ 系统基本可用，建议解决失败的测试后投入使用")
        else:
            recommendations.append("❌ 系统存在严重问题，需要修复后才能使用")
        
        self.results["summary"]["recommendations"] = recommendations
        
        # 输出分析结果
        logger.info(f"📈 测试结果分析:")
        logger.info(f"   总测试数: {total_tests}")
        logger.info(f"   通过测试: {passed_tests}")
        logger.info(f"   失败测试: {total_tests - passed_tests}")
        logger.info(f"   成功率: {self.results['summary']['overall_success_rate']:.1f}%")
        
        if self.results["summary"]["critical_failures"]:
            logger.warning(f"🚨 关键失败项:")
            for failure in self.results["summary"]["critical_failures"]:
                logger.warning(f"   - {failure}")
        
        logger.info(f"💡 建议:")
        for rec in recommendations:
            logger.info(f"   {rec}")
    
    def generate_report(self) -> str:
        """生成测试报告文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"master_test_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        # 生成HTML报告
        html_report = self.generate_html_report()
        html_file = f"master_test_report_{timestamp}.html"
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_report)
        
        return report_file, html_file
    
    def generate_html_report(self) -> str:
        """生成HTML格式的测试报告"""
        success_rate = self.results["summary"]["overall_success_rate"]
        status_color = "green" if success_rate >= 80 else "orange" if success_rate >= 60 else "red"
        status_text = "优秀" if success_rate >= 80 else "良好" if success_rate >= 60 else "需改进"
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACRAC系统API测试报告</title>
    <style>
        body {{ font-family: 'Arial', sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 30px; }}
        .status {{ font-size: 24px; font-weight: bold; color: {status_color}; }}
        .metric {{ display: inline-block; margin: 10px 20px; text-align: center; }}
        .metric-value {{ font-size: 32px; font-weight: bold; color: #333; }}
        .metric-label {{ font-size: 14px; color: #666; }}
        .section {{ margin: 30px 0; }}
        .section-title {{ font-size: 20px; font-weight: bold; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 10px; }}
        .test-phase {{ background: #f9f9f9; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .success {{ color: green; }}
        .warning {{ color: orange; }}
        .error {{ color: red; }}
        .recommendations {{ background: #e7f3ff; padding: 15px; border-left: 4px solid #2196F3; }}
        ul {{ margin: 10px 0; padding-left: 20px; }}
        .footer {{ text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏥 ACRAC医疗影像智能推荐系统</h1>
            <h2>API端点测试报告</h2>
            <div class="status">系统状态: {status_text}</div>
            <p>测试时间: {self.results["test_execution"]["start_time"]}</p>
        </div>
        
        <div class="section">
            <div style="text-align: center;">
                <div class="metric">
                    <div class="metric-value" style="color: {status_color};">{success_rate:.1f}%</div>
                    <div class="metric-label">总体成功率</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{self.results["summary"]["total_tests_passed"]}</div>
                    <div class="metric-label">通过测试</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{self.results["summary"]["total_tests_failed"]}</div>
                    <div class="metric-label">失败测试</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{self.results["summary"]["total_tests_run"]}</div>
                    <div class="metric-label">总测试数</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">🧪 测试阶段结果</div>
            
            <div class="test-phase">
                <h3>🗄️ 第一阶段: 数据库向量功能测试</h3>
                <p><strong>状态:</strong> <span class="{'success' if self.results['test_phases']['database_vector'] and self.results['test_phases']['database_vector'].get('overall_success') else 'error'}">
                {'✅ 通过' if self.results['test_phases']['database_vector'] and self.results['test_phases']['database_vector'].get('overall_success') else '❌ 失败'}
                </span></p>
                <p><strong>测试内容:</strong> 数据库连接、pgvector扩展、数据完整性、向量生成、向量搜索</p>
            </div>
            
            <div class="test-phase">
                <h3>🔍 第二阶段: 向量搜索API测试</h3>
                <p><strong>状态:</strong> <span class="{'success' if self.results['test_phases']['vector_search_api'] and self.results['test_phases']['vector_search_api']['test_summary']['success_rate'] >= 80 else 'warning' if self.results['test_phases']['vector_search_api'] and self.results['test_phases']['vector_search_api']['test_summary']['success_rate'] >= 60 else 'error'}">
                {f"✅ 通过 ({self.results['test_phases']['vector_search_api']['test_summary']['success_rate']:.1f}%)" if self.results['test_phases']['vector_search_api'] and self.results['test_phases']['vector_search_api']['test_summary']['success_rate'] >= 80 else f"⚠️ 部分通过 ({self.results['test_phases']['vector_search_api']['test_summary']['success_rate']:.1f}%)" if self.results['test_phases']['vector_search_api'] and self.results['test_phases']['vector_search_api']['test_summary']['success_rate'] >= 60 else '❌ 失败'}
                </span></p>
                <p><strong>测试内容:</strong> 健康检查、综合搜索、实体搜索、输入验证、性能测试</p>
            </div>
            
            <div class="test-phase">
                <h3>🏥 第三阶段: 综合API测试</h3>
                <p><strong>状态:</strong> <span class="{'success' if self.results['test_phases']['comprehensive_api'] and self.results['test_phases']['comprehensive_api']['end_to_end_scenarios']['success_rate'] >= 70 else 'warning' if self.results['test_phases']['comprehensive_api'] and self.results['test_phases']['comprehensive_api']['end_to_end_scenarios']['success_rate'] >= 50 else 'error'}">
                {f"✅ 通过 ({self.results['test_phases']['comprehensive_api']['end_to_end_scenarios']['success_rate']:.1f}%)" if self.results['test_phases']['comprehensive_api'] and self.results['test_phases']['comprehensive_api']['end_to_end_scenarios']['success_rate'] >= 70 else f"⚠️ 部分通过 ({self.results['test_phases']['comprehensive_api']['end_to_end_scenarios']['success_rate']:.1f}%)" if self.results['test_phases']['comprehensive_api'] and self.results['test_phases']['comprehensive_api']['end_to_end_scenarios']['success_rate'] >= 50 else '❌ 失败'}
                </span></p>
                <p><strong>测试内容:</strong> ACRAC简化API、智能分析API、三种方法API、端到端临床场景</p>
            </div>
        </div>
        
        <div class="section recommendations">
            <div class="section-title">💡 建议和改进措施</div>
            <ul>
        """
        
        for rec in self.results["summary"]["recommendations"]:
            html += f"<li>{rec}</li>"
        
        html += f"""
            </ul>
        </div>
        
        {'<div class="section"><div class="section-title">🚨 关键失败项</div><ul>' + ''.join(f'<li class="error">{failure}</li>' for failure in self.results["summary"]["critical_failures"]) + '</ul></div>' if self.results["summary"]["critical_failures"] else ''}
        
        <div class="footer">
            <p>报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>测试总耗时: {self.results["test_execution"]["total_duration_seconds"]:.2f}秒</p>
            <p>ACRAC医疗影像智能推荐系统 v2.0</p>
        </div>
    </div>
</body>
</html>
        """
        
        return html
    
    async def run_all_tests(self):
        """运行所有测试阶段"""
        logger.info("🚀 开始ACRAC系统API端点全面测试")
        logger.info("=" * 60)
        
        try:
            # 第一阶段: 数据库测试
            self.results["test_phases"]["database_vector"] = self.run_database_tests()
            
            # 检查数据库测试是否通过，决定是否继续
            if not self.results["test_phases"]["database_vector"]["overall_success"]:
                logger.warning("⚠️ 数据库测试失败，但继续进行API测试以获取完整报告")
            
            # 第二阶段: 向量搜索API测试
            self.results["test_phases"]["vector_search_api"] = await self.run_vector_search_api_tests()
            
            # 第三阶段: 综合API测试
            self.results["test_phases"]["comprehensive_api"] = await self.run_comprehensive_api_tests()
            
        except Exception as e:
            logger.error(f"❌ 测试执行异常: {str(e)}")
            self.results["summary"]["critical_failures"].append(f"测试执行异常: {str(e)}")
        
        finally:
            # 完成测试
            self.results["test_execution"]["end_time"] = datetime.now().isoformat()
            self.results["test_execution"]["total_duration_seconds"] = round(time.time() - self.start_time, 2)
            
            # 分析结果
            self.analyze_results()
            
            # 生成报告
            json_file, html_file = self.generate_report()
            
            # 最终总结
            logger.info("\n" + "🎯" * 20)
            logger.info("测试执行完成！")
            logger.info("🎯" * 20)
            logger.info(f"📊 总体成功率: {self.results['summary']['overall_success_rate']:.1f}%")
            logger.info(f"📁 JSON报告: {json_file}")
            logger.info(f"🌐 HTML报告: {html_file}")
            logger.info(f"⏱️ 总耗时: {self.results['test_execution']['total_duration_seconds']:.2f}秒")
            
            if self.results['summary']['overall_success_rate'] >= 80:
                logger.info("🎉 系统测试结果优秀，可以投入使用！")
            elif self.results['summary']['overall_success_rate'] >= 60:
                logger.info("⚠️ 系统基本可用，建议修复失败项后投入使用")
            else:
                logger.info("❌ 系统存在严重问题，需要修复后才能使用")

async def main():
    """主函数"""
    runner = MasterTestRunner()
    await runner.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())