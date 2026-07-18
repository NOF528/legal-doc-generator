"""
统一错误处理

所有错误响应格式：
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "人类可读的简要信息",
    "detail": "详细说明（可选）"
  }
}
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


def _error_body(code: str, message: str, detail: str = "") -> dict:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
        },
    }


def register_error_handlers(app: FastAPI):
    """注册全局错误处理器"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # 如果 detail 是结构化的 dict，直接使用
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "success": False,
                    "error": exc.detail,
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_error_body(
                code="VALIDATION_ERROR",
                message="请求参数错误",
                detail=str(exc.errors()[:3]),  # 只取前3个错误，避免过长
            ),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=_error_body(
                code="INTERNAL_ERROR",
                message="服务器内部错误",
                detail=str(exc),
            ),
        )
