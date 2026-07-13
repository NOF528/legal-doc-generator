from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    LEGAL_OPINION = "legal_opinion"  # 法律意见书
    BOARD_RULES = "board_rules"      # 三会制度
    WORK_REPORT = "work_report"      # 律师工作报告
    CONTRACT = "contract"            # 合同
    CUSTOM = "custom"                # 自定义


class TemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    document_type: DocumentType
    

class TemplateCreate(TemplateBase):
    pass


class TemplateResponse(TemplateBase):
    id: str
    file_path: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DocumentGenerateRequest(BaseModel):
    template_id: str
    form_data: Dict[str, Any]  # 表单填写的数据
    use_knowledge_base: bool = True  # 是否使用知识库


class DocumentGenerateResponse(BaseModel):
    document_id: str
    download_url: str
    generated_at: datetime


class KnowledgeItemBase(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    tags: List[str] = []


class KnowledgeItemCreate(KnowledgeItemBase):
    pass


class KnowledgeItemResponse(KnowledgeItemBase):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class SOPBase(BaseModel):
    name: str
    description: Optional[str] = None
    steps: List[str]
    document_type: DocumentType


class SOPCreate(SOPBase):
    pass


class SOPResponse(SOPBase):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True
