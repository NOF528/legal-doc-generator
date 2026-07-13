import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI

from app.core.config import settings


class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )
        self.model = settings.OPENAI_MODEL
    
    async def generate_document_content(
        self,
        document_type: str,
        form_data: Dict[str, Any],
        context: Optional[str] = None
    ) -> str:
        """使用AI生成文档内容"""
        
        # 构建提示词
        prompt = self._build_prompt(document_type, form_data, context)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一名专业律师，擅长撰写各类法律文书。请根据提供的信息生成专业的法律文档内容。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=8000
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"AI生成失败: {str(e)}")
    
    def _build_prompt(
        self,
        document_type: str,
        form_data: Dict[str, Any],
        context: Optional[str] = None
    ) -> str:
        """构建生成提示词"""
        
        document_type_names = {
            "legal_opinion": "法律意见书",
            "board_rules": "三会制度",
            "work_report": "律师工作报告",
            "contract": "合同",
            "custom": "自定义文档"
        }
        
        doc_type_name = document_type_names.get(document_type, "法律文档")
        
        prompt = f"""请生成一份专业的{doc_type_name}。

基本信息：
"""
        for key, value in form_data.items():
            prompt += f"- {key}: {value}\n"
        
        if context:
            prompt += f"\n参考资料/知识库内容：\n{context}\n"
        
        prompt += f"""
要求：
1. 使用专业的法律术语和格式
2. 结构清晰，逻辑严谨
3. 内容完整，符合法律规范
4. 根据提供的参考资料（如果有）增强内容的专业性

请直接输出文档正文内容。"""
        
        return prompt
    
    async def improve_content(
        self,
        content: str,
        improvement_type: str = "professional"  # professional, concise, detailed
    ) -> str:
        """改进已有内容"""
        
        improvement_prompts = {
            "professional": "请使用更专业的法律术语改写以下内容，使其更加严谨和专业：",
            "concise": "请精简以下内容，去除冗余表达，保留核心要点：",
            "detailed": "请扩展以下内容，增加更多细节和法律依据："
        }
        
        prompt = f"{improvement_prompts.get(improvement_type, improvement_prompts['professional'])}\n\n{content}"
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一名专业律师，擅长法律文书写作。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=8000
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"内容改进失败: {str(e)}")


ai_service = AIService()
