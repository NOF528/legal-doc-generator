from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.api.v1 import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    redirect_slashes=False
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API路由
app.include_router(api_router, prefix=settings.API_V1_STR)

# 静态文件服务（用于下载生成的文档）
os.makedirs(settings.GENERATED_DIR, exist_ok=True)
app.mount("/generated", StaticFiles(directory=settings.GENERATED_DIR), name="generated")


@app.get("/")
async def root():
    return {
        "message": "法律文档生成器 API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
