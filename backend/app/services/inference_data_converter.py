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
    extracted_fields: Dict[str, Any] = None
    processing_info: Dict[str, Any] = None


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = None
    warnings: List[str] = None


class BaseInferenceDataConverter(ABC):
    """推理数据转换器基类"""
    
    @abstractmethod
    async def convert_inference_data(self, inference_data: Dict[str, Any]) -> ConversionResult:
        """转换推理数据"""
        pass
    
    @abstractmethod
    async def convert_batch_inference_data(self, inference_data_list: List[Dict[str, Any]]) -> List[ConversionResult]:
        """批量转换推理数据"""
        pass
    
    @abstractmethod
    async def validate_inference_data(self, inference_data: Dict[str, Any]) -> ValidationResult:
        """验证推理数据"""
        pass


class InferenceDataConverter(BaseInferenceDataConverter):
    """推理数据转换器"""
    
    def __init__(self):
        """初始化转换器"""
        self.required_fields = ['question', 'answer', 'contexts']
        self.optional_fields = ['ground_truth', 'reference', 'id']
        logger.info("推理数据转换器初始化完成")
    
    async def convert_inference_data(self, inference_data: Dict[str, Any]) -> ConversionResult:
        """转换推理数据"""
        try:
            # 验证推理数据
            validation = await self.validate_inference_data(inference_data)
            if not validation.is_valid:
                return ConversionResult(
                    success=False,
                    error_message=f"推理数据验证失败: {'; '.join(validation.errors)}",
                    extracted_fields={},
                    processing_info={'validation_errors': validation.errors}
                )
            
            # 提取推理字段
            extracted_fields = self._extract_inference_fields(inference_data)
            
            # 创建 RAGAS 样本
            sample = self._create_ragas_sample(extracted_fields)
            
            # 收集处理信息
            processing_info = {
                'original_inference_data': inference_data,
                'extracted_fields': extracted_fields,
                'field_mapping': self._get_field_mapping(),
                'conversion_timestamp': datetime.now().isoformat()
            }
            
            return ConversionResult(
                success=True,
                sample=sample,
                extracted_fields=extracted_fields,
                processing_info=processing_info
            )
            
        except Exception as e:
            logger.error(f"推理数据转换失败: {e}")
            return ConversionResult(
                success=False,
                error_message=str(e),
                extracted_fields={},
                processing_info={'error': str(e)}
            )
    
    def _extract_inference_fields(self, inference_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取推理字段"""
        extracted = {}
        
        # 提取问题（检查项目推荐的问题）
        extracted['question'] = self._extract_question(inference_data)
        
        # 提取答案（推荐的检查项目）
        extracted['answer'] = self._extract_answer(inference_data)
        
        # 提取上下文（推理依据）
        extracted['contexts'] = self._extract_contexts(inference_data)
        
        # 提取标准答案（如果有）
        extracted['ground_truth'] = self._extract_ground_truth(inference_data)
        
        # 提取ID
        extracted['id'] = self._extract_id(inference_data)
        
        return extracted
    
    def _extract_question(self, inference_data: Dict[str, Any]) -> str:
        """提取问题字段"""
        # 可能的字段名
        question_fields = [
            'question', 'query', 'user_input', 'clinical_query',
            'inference_question', 'recommendation_question'
        ]
        
        for field in question_fields:
            if field in inference_data and inference_data[field]:
                return str(inference_data[field]).strip()
        
        # 如果没有找到问题字段，返回空字符串
        return ""
    
    def _extract_answer(self, inference_data: Dict[str, Any]) -> str:
        """提取答案字段（推荐的检查项目）"""
        # 可能的字段名
        answer_fields = [
            'answer', 'response', 'result', 'recommendation',
            'recommended_procedures', 'suggested_tests', 'inference_result'
        ]
        
        for field in answer_fields:
            if field in inference_data and inference_data[field]:
                answer = inference_data[field]
                
                # 如果答案是列表，转换为字符串
                if isinstance(answer, list):
                    return '\n'.join([str(item) for item in answer])
                
                # 如果答案是字典，尝试提取文本内容
                if isinstance(answer, dict):
                    text_fields = ['text', 'content', 'description', 'name']
                    for text_field in text_fields:
                        if text_field in answer:
                            return str(answer[text_field]).strip()
                    # 如果没有找到文本字段，返回整个字典的字符串表示
                    return str(answer)
                
                return str(answer).strip()
        
        # 如果没有找到答案字段，返回空字符串
        return ""
    
    def _extract_contexts(self, inference_data: Dict[str, Any]) -> List[str]:
        """提取上下文字段（推理依据）"""
        # 可能的字段名
        context_fields = [
            'contexts', 'retrieved_contexts', 'context', 'evidence',
            'inference_context', 'reasoning_context', 'supporting_evidence'
        ]
        
        for field in context_fields:
            if field in inference_data and inference_data[field]:
                contexts = inference_data[field]
                
                # 确保是列表
                if isinstance(contexts, str):
                    contexts = [contexts]
                elif not isinstance(contexts, list):
                    contexts = [str(contexts)]
                
                # 过滤空上下文
                contexts = [str(ctx).strip() for ctx in contexts if ctx and str(ctx).strip()]
                
                if contexts:
                    return contexts
        
        # 如果没有找到上下文字段，返回空列表
        return []
    
    def _extract_ground_truth(self, inference_data: Dict[str, Any]) -> str:
        """提取标准答案字段"""
        # 可能的字段名
        ground_truth_fields = [
            'ground_truth', 'reference', 'expected_answer', 'correct_answer',
            'standard_answer', 'reference_answer'
        ]
        
        for field in ground_truth_fields:
            if field in inference_data and inference_data[field]:
                return str(inference_data[field]).strip()
        
        # 如果没有找到标准答案字段，返回空字符串
        return ""
    
    def _extract_id(self, inference_data: Dict[str, Any]) -> str:
        """提取ID字段"""
        # 可能的字段名
        id_fields = ['id', 'sample_id', 'inference_id', 'record_id']
        
        for field in id_fields:
            if field in inference_data and inference_data[field]:
                return str(inference_data[field])
        
        # 如果没有找到ID字段，生成一个
        return f"inference_{hash(str(inference_data))}"
    
    def _create_ragas_sample(self, extracted_fields: Dict[str, Any]) -> SingleTurnSample:
        """创建 RAGAS 样本"""
        return SingleTurnSample(
            user_input=extracted_fields.get('question', ''),
            response=extracted_fields.get('answer', ''),
            retrieved_contexts=extracted_fields.get('contexts', []),
            reference=extracted_fields.get('ground_truth', '')
        )
    
    def _get_field_mapping(self) -> Dict[str, List[str]]:
        """获取字段映射信息"""
        return {
            'question_fields': ['question', 'query', 'user_input', 'clinical_query'],
            'answer_fields': ['answer', 'response', 'result', 'recommendation'],
            'context_fields': ['contexts', 'retrieved_contexts', 'context', 'evidence'],
            'ground_truth_fields': ['ground_truth', 'reference', 'expected_answer']
        }
    
    async def convert_batch_inference_data(self, inference_data_list: List[Dict[str, Any]]) -> List[ConversionResult]:
        """批量转换推理数据"""
        results = []
        
        for i, inference_data in enumerate(inference_data_list):
            try:
                logger.info(f"转换推理数据 {i+1}/{len(inference_data_list)}")
                result = await self.convert_inference_data(inference_data)
                results.append(result)
            except Exception as e:
                logger.error(f"推理数据 {i+1} 转换失败: {e}")
                results.append(ConversionResult(
                    success=False,
                    error_message=f"推理数据 {i+1} 转换失败: {str(e)}",
                    extracted_fields={},
                    processing_info={'row_index': i, 'error': str(e)}
                ))
        
        return results
    
    async def validate_inference_data(self, inference_data: Dict[str, Any]) -> ValidationResult:
        """验证推理数据"""
        errors = []
        warnings = []
        
        # 检查必需字段
        question = self._extract_question(inference_data)
        if not question:
            errors.append("缺少问题字段（question/query/user_input等）")
        
        answer = self._extract_answer(inference_data)
        if not answer:
            errors.append("缺少答案字段（answer/response/result等）")
        
        contexts = self._extract_contexts(inference_data)
        if not contexts:
            warnings.append("缺少上下文字段（contexts/retrieved_contexts等）")
        
        # 检查数据质量
        if question and len(question.strip()) < 3:
            warnings.append("问题过短，可能影响评测质量")
        
        if answer and len(answer.strip()) < 5:
            warnings.append("答案过短，可能影响评测质量")
        
        if contexts and len(contexts) > 10:
            warnings.append("上下文数量过多，可能影响处理效率")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    async def get_conversion_statistics(self, results: List[ConversionResult]) -> Dict[str, Any]:
        """获取转换统计信息"""
        if not results:
            return {}
        
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        
        # 统计字段提取情况
        field_stats = {
            'question_extracted': 0,
            'answer_extracted': 0,
            'contexts_extracted': 0,
            'ground_truth_extracted': 0
        }
        
        for result in results:
            if result.success and result.extracted_fields:
                if result.extracted_fields.get('question'):
                    field_stats['question_extracted'] += 1
                if result.extracted_fields.get('answer'):
                    field_stats['answer_extracted'] += 1
                if result.extracted_fields.get('contexts'):
                    field_stats['contexts_extracted'] += 1
                if result.extracted_fields.get('ground_truth'):
                    field_stats['ground_truth_extracted'] += 1
        
        return {
            'total_samples': total,
            'successful_conversions': successful,
            'failed_conversions': failed,
            'success_rate': successful / total if total > 0 else 0,
            'field_extraction_stats': field_stats
        }


# 兼容性函数
def create_inference_data_converter() -> InferenceDataConverter:
    """创建推理数据转换器实例"""
    return InferenceDataConverter()


if __name__ == "__main__":
    # 测试推理数据转换器
    print("🚀 测试推理数据转换器")
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    async def test_converter():
        try:
            # 创建转换器
            converter = create_inference_data_converter()
            print("✅ 推理数据转换器创建成功")
            
            # 测试数据 - 检查项目推荐推理数据
            test_inference_data = {
                "id": "inference_001",
                "question": "患者出现胸痛症状，需要推荐哪些检查项目？",
                "answer": "建议进行以下检查：1. 心电图 2. 胸部X光 3. 心肌酶谱 4. 血常规",
                "contexts": [
                    "胸痛是常见症状，需要排除心脏疾病",
                    "心电图可以检测心律异常",
                    "胸部X光可以观察肺部情况"
                ],
                "ground_truth": "胸痛患者应进行心电图、胸部X光、心肌酶谱检查"
            }
            
            # 转换推理数据
            result = await converter.convert_inference_data(test_inference_data)
            
            if result.success:
                print("✅ 推理数据转换成功")
                print(f"   提取的字段: {result.extracted_fields}")
                print(f"   处理信息: {result.processing_info}")
                
                # 验证数据
                validation = await converter.validate_inference_data(test_inference_data)
                print(f"   验证结果: {'通过' if validation.is_valid else '失败'}")
                if validation.warnings:
                    print(f"   警告: {validation.warnings}")
            else:
                print(f"❌ 推理数据转换失败: {result.error_message}")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test_converter())























