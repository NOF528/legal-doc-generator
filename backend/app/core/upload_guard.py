"""
上传安全守卫

- SHA-256 哈希校验（防篡改/重复）
- 文件大小限制
- 单 IP 每日上传次数限制
"""

import hashlib
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

from fastapi import HTTPException, UploadFile


# 限制配置
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB
MAX_UPLOADS_PER_IP_PER_DAY = 10

# 简单的内存计数器（单进程有效，重启清零）
_upload_counts: Dict[str, List[float]] = defaultdict(list)


def _get_client_ip(request_client_host: str | None) -> str:
    return request_client_host or "unknown"


def _check_rate_limit(ip: str):
    """单 IP 每日上传次数限制"""
    now = time.time()
    day_ago = now - 86400

    # 清理过期记录
    _upload_counts[ip] = [t for t in _upload_counts[ip] if t > day_ago]

    if len(_upload_counts[ip]) >= MAX_UPLOADS_PER_IP_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"每个 IP 每天最多上传 {MAX_UPLOADS_PER_IP_PER_DAY} 份文件",
                "detail": "如需更多次数，请明天再试",
            },
        )

    _upload_counts[ip].append(now)


async def save_upload_temp(
    upload_file: UploadFile,
    client_host: str | None = None,
) -> Tuple[str, str]:
    """
    安全保存上传文件到临时目录。

    返回 (临时文件路径, 文件 SHA-256 哈希)
    """
    ip = _get_client_ip(client_host)
    _check_rate_limit(ip)

    # 1. 扩展名检查
    suffix = Path(upload_file.filename or "").suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_FILE_TYPE",
                "message": "只支持 PDF 文件",
                "detail": f"收到文件类型: {suffix or '未知'}",
            },
        )

    # 2. 保存到临时文件并计算哈希
    hasher = hashlib.sha256()
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_path = temp.name

    try:
        while True:
            chunk = await upload_file.read(1024 * 1024)  # 1MB 分块读取
            if not chunk:
                break
            hasher.update(chunk)
            temp.write(chunk)
            if temp.tell() > MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "code": "FILE_TOO_LARGE",
                        "message": f"文件大小超过 {MAX_UPLOAD_SIZE // 1024 // 1024}MB 限制",
                        "detail": f"当前文件: {temp.tell() / 1024 / 1024:.1f}MB",
                    },
                )
        temp.flush()
        file_hash = hasher.hexdigest()

        # 3. PDF 魔数校验（防止伪装 PDF）
        with open(temp_path, "rb") as f:
            magic = f.read(5)
        if magic != b"%PDF-":
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_PDF",
                    "message": "文件不是有效的 PDF",
                    "detail": "文件头校验失败",
                },
            )

        return temp_path, file_hash

    except HTTPException:
        temp.close()
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    except Exception as e:
        temp.close()
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "UPLOAD_FAILED",
                "message": "文件保存失败",
                "detail": str(e),
            },
        )
    finally:
        temp.close()


def cleanup_temp(path: str | None):
    """安全删除临时文件"""
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass
