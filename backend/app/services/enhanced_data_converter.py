#!/usr/bin/env python3
"""
推理数据转换器
专门从推理数据中提取检查项目推荐相关的评测输入数据
忠于原始数据，不进行额外处理
"""
import json
import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime

try:
    from ragas.dataset_schema import SingleTurnSample
    RAGAS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"RAGAS相关依赖未安装: {e}")
    RAGAS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """转换结果"""
    success: bool
    sample: Optional[SingleTurnSample] = None
    error_message: Optional[str] = None
    processing_info: Dict[str, Any] = None
    medical_terms: List[str] = None
    chinese_processing: Dict[str, Any] = None


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = None
    warnings: List[str] = None
    suggestions: List[str] = None


class BaseDataConverter(ABC):
    """数据转换器基类"""
    
    @abstractmethod
    async def convert_rag_result(self, rag_result: Dict[str, Any]) -> ConversionResult:
        """转换 RAG 推理结果"""
        pass
    
    @abstractmethod
    async def convert_excel_data(self, excel_data: List[Dict[str, Any]]) -> List[ConversionResult]:
        """转换 Excel 数据"""
        pass
    
    @abstractmethod
    async def validate_sample(self, sample: SingleTurnSample) -> ValidationResult:
        """验证样本数据"""
        pass


class EnhancedDataConverter(BaseDataConverter):
    """增强版数据转换器"""
    
    def __init__(self, medical_domain: bool = True, chinese_optimization: bool = True):
        self.medical_domain = medical_domain
        self.chinese_optimization = chinese_optimization
        
        # 初始化中文分词
        if chinese_optimization:
            self._init_chinese_processing()
        
        # 医学术语词典
        if medical_domain:
            self._init_medical_terms()
    
    def _init_chinese_processing(self):
        """初始化中文处理"""
        try:
            # 加载自定义词典
            jieba.load_userdict(self._get_medical_dict_path())
            logger.info("中文处理初始化完成")
        except Exception as e:
            logger.warning(f"中文处理初始化失败: {e}")
    
    def _init_medical_terms(self):
        """初始化医学术语词典"""
        self.medical_keywords = {
            # 疾病相关
            'diseases': ['糖尿病', '高血压', '心脏病', '癌症', '肿瘤', '肺炎', '肝炎', '肾炎', '胃炎', '肠炎'],
            # 症状相关
            'symptoms': ['疼痛', '发热', '咳嗽', '头痛', '头晕', '恶心', '呕吐', '腹泻', '便秘', '失眠'],
            # 治疗相关
            'treatments': ['手术', '化疗', '放疗', '药物治疗', '物理治疗', '康复训练', '饮食控制'],
            # 检查相关
            'examinations': ['CT', 'MRI', 'X光', 'B超', '心电图', '血常规', '尿常规', '生化检查'],
            # 药物相关
            'medications': ['抗生素', '止痛药', '降压药', '降糖药', '维生素', '钙片', '叶酸']
        }
        
        # 合并所有关键词
        self.all_medical_terms = []
        for category, terms in self.medical_keywords.items():
            self.all_medical_terms.extend(terms)
        
        logger.info(f"医学术语词典初始化完成，共 {len(self.all_medical_terms)} 个术语")
    
    def _get_medical_dict_path(self) -> str:
        """获取医学词典路径"""
        # 这里可以返回自定义医学词典的路径
        return ""
    
    async def convert_rag_result(self, rag_result: Dict[str, Any]) -> ConversionResult:
        """转换 RAG 推理结果"""
        try:
            # 提取基本信息
            question = self._extract_question(rag_result)
            answer = self._extract_answer(rag_result)
            contexts = self._extract_contexts(rag_result)
            ground_truth = self._extract_ground_truth(rag_result)
            
            # 中文预处理
            if self.chinese_optimization:
                question = await self.preprocess_chinese_content(question)
                answer = await self.preprocess_chinese_content(answer)
                contexts = [await self.preprocess_chinese_content(ctx) for ctx in contexts]
                if ground_truth:
                    ground_truth = await self.preprocess_chinese_content(ground_truth)
            
            # 医学术语提取
            medical_terms = []
            if self.medical_domain:
                medical_terms.extend(await self.extract_medical_terms(question))
                medical_terms.extend(await self.extract_medical_terms(answer))
                for ctx in contexts:
                    medical_terms.extend(await self.extract_medical_terms(ctx))
            
            # 上下文智能过滤
            contexts = await self.normalize_contexts(contexts)
            
            # 创建 RAGAS 样本
            sample = SingleTurnSample(
                user_input=question,
                response=answer,
                retrieved_contexts=contexts,
                reference=ground_truth
            )
            
            # 验证样本
            validation = await self.validate_sample(sample)
            
            # 收集处理信息
            processing_info = {
                'original_rag_result': rag_result,
                'medical_terms_found': len(set(medical_terms)),
                'contexts_filtered': len(contexts),
                'chinese_processing_applied': self.chinese_optimization,
                'medical_domain_processing': self.medical_domain
            }
            
            chinese_processing = {
                'is_chinese_content': any('\u4e00' <= char <= '\u9fff' for char in question + answer),
                'chinese_character_count': sum(1 for char in question + answer if '\u4e00' <= char <= '\u9fff'),
                'processing_method': 'enhanced_chinese_processing' if self.chinese_optimization else 'standard'
            }
            
            return ConversionResult(
                success=validation.is_valid,
                sample=sample if validation.is_valid else None,
                error_message=None if validation.is_valid else '; '.join(validation.errors),
                processing_info=processing_info,
                medical_terms=list(set(medical_terms)),
                chinese_processing=chinese_processing
            )
            
        except Exception as e:
            logger.error(f"RAG 结果转换失败: {e}")
            return ConversionResult(
                success=False,
                error_message=str(e),
                processing_info={'error': str(e)},
                medical_terms=[],
                chinese_processing={}
            )
    
    def _extract_question(self, rag_result: Dict[str, Any]) -> str:
        """提取问题"""
        return str(rag_result.get('question', rag_result.get('query', rag_result.get('user_input', ''))))
    
    def _extract_answer(self, rag_result: Dict[str, Any]) -> str:
        """提取答案"""
        answer = rag_result.get('answer', rag_result.get('response', rag_result.get('result', '')))
        
        # 如果答案是字典，尝试提取文本内容
        if isinstance(answer, dict):
            answer = answer.get('text', answer.get('content', str(answer)))
        
        return str(answer)
    
    def _extract_contexts(self, rag_result: Dict[str, Any]) -> List[str]:
        """提取上下文"""
        contexts = rag_result.get('contexts', rag_result.get('retrieved_contexts', rag_result.get('context', [])))
        
        if isinstance(contexts, str):
            contexts = [contexts]
        elif not isinstance(contexts, list):
            contexts = [str(contexts)]
        
        return [str(ctx) for ctx in contexts if ctx and str(ctx).strip()]
    
    def _extract_ground_truth(self, rag_result: Dict[str, Any]) -> str:
        """提取标准答案"""
        return str(rag_result.get('ground_truth', rag_result.get('reference', rag_result.get('expected_answer', ''))))
    
    async def convert_excel_data(self, excel_data: List[Dict[str, Any]]) -> List[ConversionResult]:
        """转换 Excel 数据"""
        results = []
        
        for i, row_data in enumerate(excel_data):
            try:
                # 标准化 Excel 数据格式
                standardized_data = self._standardize_excel_row(row_data)
                
                # 转换单个样本
                result = await self.convert_rag_result(standardized_data)
                results.append(result)
                
                logger.debug(f"Excel 行 {i+1} 转换完成")
                
            except Exception as e:
                logger.error(f"Excel 行 {i+1} 转换失败: {e}")
                results.append(ConversionResult(
                    success=False,
                    error_message=f"行 {i+1} 转换失败: {str(e)}",
                    processing_info={'row_index': i, 'error': str(e)},
                    medical_terms=[],
                    chinese_processing={}
                ))
        
        return results
    
    def _standardize_excel_row(self, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化 Excel 行数据"""
        # 常见的 Excel 列名映射
        column_mapping = {
            'clinical_query': 'question',
            'question': 'question',
            'query': 'question',
            'user_input': 'question',
            'answer': 'answer',
            'response': 'answer',
            'result': 'answer',
            'ground_truth': 'ground_truth',
            'reference': 'ground_truth',
            'expected_answer': 'ground_truth',
            'contexts': 'contexts',
            'retrieved_contexts': 'contexts',
            'context': 'contexts'
        }
        
        standardized = {}
        for excel_key, standard_key in column_mapping.items():
            if excel_key in row_data:
                standardized[standard_key] = row_data[excel_key]
        
        # 添加行索引作为 ID
        if 'id' not in standardized:
            standardized['id'] = f"excel_row_{hash(str(row_data))}"
        
        return standardized
    
    async def validate_sample(self, sample: SingleTurnSample) -> ValidationResult:
        """验证样本数据"""
        errors = []
        warnings = []
        suggestions = []
        
        # 验证问题
        if not sample.user_input or not sample.user_input.strip():
            errors.append("问题不能为空")
        elif len(sample.user_input.strip()) < 3:
            warnings.append("问题过短，可能影响评测质量")
        
        # 验证答案
        if not sample.response or not sample.response.strip():
            errors.append("答案不能为空")
        elif len(sample.response.strip()) < 5:
            warnings.append("答案过短，可能影响评测质量")
        
        # 验证上下文
        if not sample.retrieved_contexts:
            warnings.append("没有检索到的上下文")
        else:
            # 检查上下文质量
            for i, ctx in enumerate(sample.retrieved_contexts):
                if not ctx or not ctx.strip():
                    warnings.append(f"上下文 {i+1} 为空")
                elif len(ctx.strip()) < 10:
                    warnings.append(f"上下文 {i+1} 过短")
                elif len(ctx.strip()) > 1000:
                    warnings.append(f"上下文 {i+1} 过长，可能影响处理效率")
        
        # 验证标准答案
        if sample.reference and len(sample.reference.strip()) < 5:
            warnings.append("标准答案过短")
        
        # 中文内容检查
        if self.chinese_optimization:
            chinese_chars = sum(1 for char in sample.user_input + sample.response if '\u4e00' <= char <= '\u9fff')
            if chinese_chars > 0 and chinese_chars < 5:
                suggestions.append("检测到中文内容，建议使用中文优化处理")
        
        # 医学内容检查
        if self.medical_domain:
            medical_terms_found = await self.extract_medical_terms(sample.user_input + sample.response)
            if medical_terms_found:
                suggestions.append(f"检测到医学术语: {', '.join(medical_terms_found[:3])}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    async def preprocess_chinese_content(self, content: str) -> str:
        """预处理中文内容"""
        if not content or not self.chinese_optimization:
            return content
        
        try:
            # 清理文本
            content = content.strip()
            
            # 移除多余的空白字符
            content = re.sub(r'\s+', ' ', content)
            
            # 移除特殊字符但保留中文标点
            content = re.sub(r'[^\u4e00-\u9fff\w\s，。！？；：""''（）【】《》]', '', content)
            
            # 标准化中文标点
            content = content.replace('，', '，').replace('。', '。')
            content = content.replace('！', '！').replace('？', '？')
            
            return content
            
        except Exception as e:
            logger.warning(f"中文内容预处理失败: {e}")
            return content
    
    async def extract_medical_terms(self, text: str) -> List[str]:
        """提取医学术语"""
        if not text or not self.medical_domain:
            return []
        
        try:
            medical_terms = []
            
            # 基于词典的术语提取
            for term in self.all_medical_terms:
                if term in text:
                    medical_terms.append(term)
            
            # 使用分词提取可能的医学术语
            if self.chinese_optimization:
                try:
                    words = jieba.lcut(text)
                    for word in words:
                        if len(word) >= 2 and any(char in word for char in '病痛症治药检'):
                            medical_terms.append(word)
                except AttributeError:
                    # 如果 jieba.lcut 不可用，使用简单的字符串匹配
                    for term in ['病', '痛', '症', '治', '药', '检']:
                        if term in text:
                            medical_terms.append(term)
            
            return list(set(medical_terms))
            
        except Exception as e:
            logger.warning(f"医学术语提取失败: {e}")
            return []
    
    async def normalize_contexts(self, contexts: List[str]) -> List[str]:
        """标准化上下文"""
        if not contexts:
            return ["相关医学知识"]  # 默认上下文
        
        normalized = []
        seen = set()
        
        for ctx in contexts:
            if not ctx or not ctx.strip():
                continue
            
            # 清理上下文
            ctx = ctx.strip()
            
            # 去重
            if ctx in seen:
                continue
            
            # 长度限制
            if len(ctx) > 500:
                ctx = ctx[:500] + "..."
            
            # 质量检查
            if len(ctx) < 10:
                continue
            
            normalized.append(ctx)
            seen.add(ctx)
        
        # 限制上下文数量
        if len(normalized) > 5:
            normalized = normalized[:5]
        
        return normalized if normalized else ["相关医学知识"]
    
    async def create_enhanced_sample(self, data: Dict[str, Any]) -> SingleTurnSample:
        """创建增强版样本"""
        result = await self.convert_rag_result(data)
        
        if not result.success:
            raise ValueError(f"数据转换失败: {result.error_message}")
        
        return result.sample
    
    async def batch_convert(self, data_list: List[Dict[str, Any]]) -> Tuple[List[SingleTurnSample], List[str]]:
        """批量转换数据"""
        samples = []
        errors = []
        
        for i, data in enumerate(data_list):
            try:
                result = await self.convert_rag_result(data)
                if result.success:
                    samples.append(result.sample)
                else:
                    errors.append(f"样本 {i+1}: {result.error_message}")
            except Exception as e:
                errors.append(f"样本 {i+1}: {str(e)}")
        
        return samples, errors


# 兼容性函数
def create_enhanced_data_converter(medical_domain: bool = True, 
                                 chinese_optimization: bool = True) -> EnhancedDataConverter:
    """创建增强版数据转换器实例"""
    return EnhancedDataConverter(medical_domain, chinese_optimization)


if __name__ == "__main__":
    # 测试增强版数据转换器
    print("🚀 测试增强版数据转换器")
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    async def test_converter():
        try:
            # 创建转换器
            converter = create_enhanced_data_converter()
            print("✅ 增强版数据转换器创建成功")
            
            # 测试数据
            test_data = {
                "id": "test_001",
                "question": "糖尿病患者的饮食管理建议？",
                "answer": "糖尿病患者饮食管理：1. 控制总热量 2. 合理分配三大营养素 3. 定时定量进餐",
                "contexts": [
                    "糖尿病需要严格的饮食控制",
                    "营养均衡对血糖控制很重要"
                ],
                "ground_truth": "糖尿病患者应该控制饮食"
            }
            
            # 转换数据
            result = await converter.convert_rag_result(test_data)
            
            if result.success:
                print("✅ 数据转换成功")
                print(f"   医学术语: {result.medical_terms}")
                print(f"   中文处理: {result.chinese_processing}")
                print(f"   处理信息: {result.processing_info}")
                
                # 验证样本
                validation = await converter.validate_sample(result.sample)
                print(f"   验证结果: {'通过' if validation.is_valid else '失败'}")
                if validation.warnings:
                    print(f"   警告: {validation.warnings}")
                if validation.suggestions:
                    print(f"   建议: {validation.suggestions}")
            else:
                print(f"❌ 数据转换失败: {result.error_message}")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test_converter())
