import os
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from app.models.schemas import DocumentGenerateRequest, DocumentGenerateResponse
from app.services.document_service import document_service
from app.services.template_service import template_service

router = APIRouter()


@router.post("/generate", response_model=DocumentGenerateResponse)
async def generate_document(
    request: DocumentGenerateRequest,
    background_tasks: BackgroundTasks
):
    """生成文档"""
    
    # 检查模板是否存在
    template = template_service.get_template(request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    try:
        # 生成文档
        document_id, output_path = await document_service.generate_document(
            template_id=request.template_id,
            form_data=request.form_data,
            use_knowledge_base=request.use_knowledge_base
        )
        
        return DocumentGenerateResponse(
            document_id=document_id,
            download_url=f"/api/v1/documents/download/{document_id}",
            generated_at=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档生成失败: {str(e)}")


@router.get("/download/{document_id}")
async def download_document(document_id: str):
    """下载生成的文档"""
    
    file_path = document_service.get_document_path(document_id)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"generated_document_{document_id}.docx"
    )


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """删除文档"""
    success = document_service.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "文档已删除"}


from datetime import datetime
