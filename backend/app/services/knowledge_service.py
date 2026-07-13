import os
import uuid
import chromadb
from datetime import datetime
from typing import List, Optional
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.models.schemas import KnowledgeItemCreate, KnowledgeItemResponse, SOPCreate, SOPResponse, DocumentType


class KnowledgeService:
    def __init__(self):
        self.persist_dir = settings.CHROMA_PERSIST_DIR
        os.makedirs(self.persist_dir, exist_ok=True)
        
        # 初始化ChromaDB
        self.client = chromadb.Client(
            ChromaSettings(
                persist_directory=self.persist_dir,
                anonymized_telemetry=False
            )
        )
        
        # 创建集合
        self.knowledge_collection = self.client.get_or_create_collection(
            name="knowledge_base",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.sop_collection = self.client.get_or_create_collection(
            name="sop_base",
            metadata={"hnsw:space": "cosine"}
        )
        
        # 内存存储用于元数据
        self._knowledge_items: dict = {}
        self._sops: dict = {}
    
    def add_knowledge_item(self, item: KnowledgeItemCreate) -> KnowledgeItemResponse:
        """添加知识库条目"""
        item_id = str(uuid.uuid4())
        
        # 添加到ChromaDB
        self.knowledge_collection.add(
            documents=[item.content],
            metadatas=[{
                "title": item.title,
                "category": item.category or "",
                "tags": ",".join(item.tags),
                "created_at": datetime.now().isoformat()
            }],
            ids=[item_id]
        )
        
        # 持久化
        self.client.persist()
        
        response = KnowledgeItemResponse(
            id=item_id,
            title=item.title,
            content=item.content,
            category=item.category,
            tags=item.tags,
            created_at=datetime.now()
        )
        
        self._knowledge_items[item_id] = response
        return response
    
    def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        n_results: int = 5
    ) -> List[KnowledgeItemResponse]:
        """搜索知识库"""
        
        where_filter = None
        if category:
            where_filter = {"category": category}
        
        results = self.knowledge_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter
        )
        
        items = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i, item_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                content = results['documents'][0][i] if results['documents'] else ""
                
                item = KnowledgeItemResponse(
                    id=item_id,
                    title=metadata.get('title', ''),
                    content=content,
                    category=metadata.get('category') or None,
                    tags=metadata.get('tags', '').split(',') if metadata.get('tags') else [],
                    created_at=datetime.fromisoformat(metadata.get('created_at', datetime.now().isoformat()))
                )
                items.append(item)
        
        return items
    
    def get_relevant_context(
        self,
        query: str,
        document_type: Optional[DocumentType] = None,
        n_results: int = 3
    ) -> str:
        """获取相关上下文，用于AI生成"""
        
        # 搜索知识库
        knowledge_items = self.search_knowledge(query, n_results=n_results)
        
        # 搜索SOP
        sop_results = self.search_sop(query, document_type, n_results=2)
        
        context_parts = []
        
        if knowledge_items:
            context_parts.append("## 相关知识库内容:\n")
            for i, item in enumerate(knowledge_items, 1):
                context_parts.append(f"{i}. {item.title}:\n{item.content}\n")
        
        if sop_results:
            context_parts.append("## 相关SOP:\n")
            for i, sop in enumerate(sop_results, 1):
                context_parts.append(f"{i}. {sop.name}:\n")
                context_parts.append(f"   流程步骤:\n")
                for step in sop.steps:
                    context_parts.append(f"   - {step}\n")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def delete_knowledge_item(self, item_id: str) -> bool:
        """删除知识库条目"""
        try:
            self.knowledge_collection.delete(ids=[item_id])
            self.client.persist()
            if item_id in self._knowledge_items:
                del self._knowledge_items[item_id]
            return True
        except:
            return False
    
    def list_knowledge_items(
        self,
        category: Optional[str] = None
    ) -> List[KnowledgeItemResponse]:
        """列出所有知识库条目"""
        # 从ChromaDB获取所有条目
        try:
            results = self.knowledge_collection.get()
            items = []
            
            for i, item_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                content = results['documents'][i] if results['documents'] else ""
                
                if category and metadata.get('category') != category:
                    continue
                
                item = KnowledgeItemResponse(
                    id=item_id,
                    title=metadata.get('title', ''),
                    content=content,
                    category=metadata.get('category') or None,
                    tags=metadata.get('tags', '').split(',') if metadata.get('tags') else [],
                    created_at=datetime.fromisoformat(metadata.get('created_at', datetime.now().isoformat()))
                )
                items.append(item)
            
            return items
        except:
            return list(self._knowledge_items.values())
    
    # SOP管理
    def add_sop(self, sop: SOPCreate) -> SOPResponse:
        """添加SOP"""
        sop_id = str(uuid.uuid4())
        
        # 构建SOP内容
        content = f"SOP名称: {sop.name}\n"
        content += f"描述: {sop.description or ''}\n"
        content += f"文档类型: {sop.document_type}\n"
        content += "流程步骤:\n"
        for i, step in enumerate(sop.steps, 1):
            content += f"{i}. {step}\n"
        
        # 添加到ChromaDB
        self.sop_collection.add(
            documents=[content],
            metadatas=[{
                "name": sop.name,
                "description": sop.description or "",
                "document_type": sop.document_type,
                "steps": "\n".join(sop.steps),
                "created_at": datetime.now().isoformat()
            }],
            ids=[sop_id]
        )
        
        self.client.persist()
        
        response = SOPResponse(
            id=sop_id,
            name=sop.name,
            description=sop.description,
            steps=sop.steps,
            document_type=sop.document_type,
            created_at=datetime.now()
        )
        
        self._sops[sop_id] = response
        return response
    
    def search_sop(
        self,
        query: str,
        document_type: Optional[DocumentType] = None,
        n_results: int = 3
    ) -> List[SOPResponse]:
        """搜索SOP"""
        
        where_filter = None
        if document_type:
            where_filter = {"document_type": document_type}
        
        results = self.sop_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter
        )
        
        sops = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i, sop_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                
                steps = metadata.get('steps', '').split('\n') if metadata.get('steps') else []
                
                sop = SOPResponse(
                    id=sop_id,
                    name=metadata.get('name', ''),
                    description=metadata.get('description') or None,
                    steps=steps,
                    document_type=metadata.get('document_type', 'custom'),
                    created_at=datetime.fromisoformat(metadata.get('created_at', datetime.now().isoformat()))
                )
                sops.append(sop)
        
        return sops
    
    def delete_sop(self, sop_id: str) -> bool:
        """删除SOP"""
        try:
            self.sop_collection.delete(ids=[sop_id])
            self.client.persist()
            if sop_id in self._sops:
                del self._sops[sop_id]
            return True
        except:
            return False


knowledge_service = KnowledgeService()
