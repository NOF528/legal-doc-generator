import os
import shutil
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional

from app.models.schemas import (
    TemplateCreate, 
    TemplateResponse, 
    DocumentType
)
from app.services.template_service import template_service

router = APIRouter()


@router.post("", response_model=TemplateResponse)
async def upload_template(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...)
):
    """上传模板文件"""
    
    # 检查文件类型
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="只支持 .docx 文件")
    
    # 保存上传的文件到临时位置
    temp_path = f"/tmp/{file.filename}"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建模板数据
        template_data = TemplateCreate(
            name=name,
            description=description,
            document_type=document_type
        )
        
        # 保存模板
        template = template_service.save_template(temp_path, template_data)
        return template
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    document_type: Optional[DocumentType] = None
):
    """列出所有模板"""
    return template_service.list_templates(document_type)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    """获取模板详情"""
    template = template_service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return template


@router.get("/{template_id}/placeholders")
async def get_template_placeholders(template_id: str):
    """获取模板中的占位符列表"""
    template = template_service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    placeholders = template_service.extract_placeholders(template_id)
    return {"placeholders": placeholders}


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """删除模板"""
    success = template_service.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"message": "模板已删除"}
