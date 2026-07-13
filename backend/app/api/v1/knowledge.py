from fastapi import APIRouter, HTTPException
from typing import List, Optional

from app.models.schemas import (
    KnowledgeItemCreate, 
    KnowledgeItemResponse,
    SOPCreate,
    SOPResponse,
    DocumentType
)
from app.services.knowledge_service import knowledge_service

router = APIRouter()


# 知识库条目管理
@router.post("/items", response_model=KnowledgeItemResponse)
async def add_knowledge_item(item: KnowledgeItemCreate):
    """添加知识库条目"""
    return knowledge_service.add_knowledge_item(item)


@router.get("/items", response_model=List[KnowledgeItemResponse])
async def list_knowledge_items(category: Optional[str] = None):
    """列出知识库条目"""
    return knowledge_service.list_knowledge_items(category)


@router.get("/items/search")
async def search_knowledge(
    query: str,
    category: Optional[str] = None,
    n_results: int = 5
):
    """搜索知识库"""
    return knowledge_service.search_knowledge(query, category, n_results)


@router.delete("/items/{item_id}")
async def delete_knowledge_item(item_id: str):
    """删除知识库条目"""
    success = knowledge_service.delete_knowledge_item(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"message": "条目已删除"}


# SOP管理
@router.post("/sops", response_model=SOPResponse)
async def add_sop(sop: SOPCreate):
    """添加SOP"""
    return knowledge_service.add_sop(sop)


@router.get("/sops", response_model=List[SOPResponse])
async def list_sops(document_type: Optional[DocumentType] = None):
    """列出SOP"""
    # 使用搜索功能获取所有
    results = knowledge_service.search_sop("", document_type, n_results=100)
    return results


@router.get("/sops/search")
async def search_sops(
    query: str,
    document_type: Optional[DocumentType] = None,
    n_results: int = 5
):
    """搜索SOP"""
    return knowledge_service.search_sop(query, document_type, n_results)


@router.delete("/sops/{sop_id}")
async def delete_sop(sop_id: str):
    """删除SOP"""
    success = knowledge_service.delete_sop(sop_id)
    if not success:
        raise HTTPException(status_code=404, detail="SOP不存在")
    return {"message": "SOP已删除"}
