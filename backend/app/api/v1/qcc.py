"""
企查查报告提取 API
"""
import os
import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from typing import Optional

from app.services.qcc_extractor import QCCReportExtractor
from app.services.qcc_extractor.changes import extract_history_evolution
from app.services.qcc_extractor.history_docx_generator import generate_history_word_document

router = APIRouter()

# 安全配置：最大上传文件大小 50MB
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


def _save_upload_temp(upload_file: UploadFile, max_size: int = MAX_UPLOAD_SIZE) -> str:
    """安全保存上传文件到临时目录，返回临时文件路径"""
    suffix = Path(upload_file.filename).suffix if upload_file.filename else ''
    if suffix.lower() != '.pdf':
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")
    
    temp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    try:
        shutil.copyfileobj(upload_file.file, temp)
        temp.flush()
        size = os.path.getsize(temp.name)
        if size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"文件超过 {max_size // 1024 // 1024}MB 限制"
            )
        return temp.name
    except Exception:
        temp.close()
        if os.path.exists(temp.name):
            os.unlink(temp.name)
        raise
    finally:
        temp.close()


def _cleanup_temp(path: str):
    """安全删除临时文件"""
    if path and os.path.exists(path):
        os.unlink(path)


@router.post("/extract")
async def extract_qcc_report(file: UploadFile = File(...)):
    """
    上传企查查 PDF 报告，提取结构化数据
    """
    temp_path = None
    try:
        temp_path = _save_upload_temp(file)
        
        # 提取数据
        extractor = QCCReportExtractor()
        result = extractor.extract(temp_path)
        
        return {
            "success": True,
            "data": result,
            "filename": file.filename,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提取失败: {str(e)}")
    finally:
        _cleanup_temp(temp_path)


@router.post("/extract-basic")
async def extract_qcc_basic(file: UploadFile = File(...)):
    """
    提取企查查报告基础信息（精简版）
    只返回核心工商信息、股东、主要人员
    """
    temp_path = None
    try:
        temp_path = _save_upload_temp(file)
        
        extractor = QCCReportExtractor()
        result = extractor.extract(temp_path)
        
        # 精简输出
        basic = result.get("basic_info", {})
        simplified = {
            "report_meta": result.get("report_meta", {}),
            "company_profile": result.get("company_profile", {}),
            "registration": basic.get("registration", {}),
            "shareholders": basic.get("shareholders", []),
            "key_persons": basic.get("key_persons", []),
            "change_history_count": len(basic.get("change_history", [])),
            "investments_count": len(basic.get("investments", [])),
            "branches_count": len(basic.get("branches", [])),
            "legal_risks": result.get("legal_risks", {}),
            "business_risks": result.get("business_risks", {}),
        }
        
        return {
            "success": True,
            "data": simplified,
            "filename": file.filename,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提取失败: {str(e)}")
    finally:
        _cleanup_temp(temp_path)


@router.post("/history-evolution")
async def extract_history_evolution_endpoint(file: UploadFile = File(...)):
    """
    提取企查查报告并生成历史沿革
    
    返回：
    - 历史沿革文本（可直接用于法律意见书）
    - 结构化的变更记录
    - 变更分类统计
    """
    temp_path = None
    try:
        temp_path = _save_upload_temp(file)
        
        # 提取完整数据
        extractor = QCCReportExtractor()
        result = extractor.extract(temp_path)
        
        # 生成历史沿革
        company_name = result.get("report_meta", {}).get("company_name", "公司")
        raw_changes = result.get("basic_info", {}).get("change_history", [])
        
        history = extract_history_evolution(raw_changes, company_name)
        
        return {
            "success": True,
            "company_name": company_name,
            "history_evolution": history,
            "basic_info": {
                "registration": result.get("basic_info", {}).get("registration", {}),
                "current_shareholders": result.get("basic_info", {}).get("shareholders", []),
            },
            "filename": file.filename,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"提取失败: {str(e)}\n{traceback.format_exc()}")
    finally:
        _cleanup_temp(temp_path)


@router.post("/history-evolution/docx")
async def generate_history_word(
    file: UploadFile = File(...),
    law_firm_name: str = Form(""),
    lawyer_name: str = Form(""),
    use_template: bool = Form(False)
):
    """
    提取企查查报告并生成历史沿革Word文档
    
    参数：
    - file: PDF文件
    - law_firm_name: 律所名称（可选）
    - lawyer_name: 律师姓名（可选）
    - use_template: 是否使用自定义模板
    
    返回：
    - 可直接下载的Word文档(.docx)
    """
    temp_path = None
    output_path = None
    
    try:
        # 安全保存上传文件
        temp_path = _save_upload_temp(file)
        
        # 提取完整数据
        extractor = QCCReportExtractor()
        result = extractor.extract(temp_path)
        
        # 生成历史沿革
        company_name = result.get("report_meta", {}).get("company_name", "公司")
        raw_changes = result.get("basic_info", {}).get("change_history", [])
        
        history = extract_history_evolution(raw_changes, company_name)
        
        # 准备额外数据
        extra_data = {}
        if law_firm_name:
            extra_data['law_firm_name'] = law_firm_name
        if lawyer_name:
            extra_data['lawyer_name'] = lawyer_name
        
        # 确定模板路径
        template_path = None
        if use_template:
            from app.services.qcc_extractor.history_docx_generator import get_template_path
            template_path = get_template_path()
        
        # 安全生成输出临时文件
        output_fd, output_path = tempfile.mkstemp(suffix='.docx')
        os.close(output_fd)
        
        generate_history_word_document(
            company_name=company_name,
            history_result=history,
            output_path=output_path,
            template_path=template_path,
            extra_data=extra_data if extra_data else None
        )
        
        # 返回文件
        return FileResponse(
            output_path,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            filename=f"{company_name}_历史沿革.docx"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}\n{traceback.format_exc()}")
    finally:
        _cleanup_temp(temp_path)
        # 注意：output_path 在 FileResponse 后由 FastAPI 负责清理，
        # 此处不删除，避免返回前文件被删除


@router.get("/history-evolution/templates")
async def list_templates():
    """
    列出所有可用的Word模板
    """
    from app.services.qcc_extractor.history_docx_generator import list_available_templates, TEMPLATE_DIR
    
    templates = list_available_templates()
    return {
        "success": True,
        "templates": templates,
        "template_dir": TEMPLATE_DIR,
        "instructions": "将模板文件(.docx)放入上述目录即可使用。支持的占位符: {{company_name}}, {{history_content}}, {{report_date}}, {{change_count}}, {{law_firm_name}}, {{lawyer_name}}"
    }


# 工商内档扩展接口（预留）
@router.post("/archives/extract")
async def extract_business_archives(file: UploadFile = File(...)):
    """
    提取工商内档（预留接口）
    
    注意：工商内档格式因地区、公司类型、时间差异很大，
    需要针对具体情况定制解析逻辑。
    """
    raise HTTPException(
        status_code=501, 
        detail="工商内档提取功能尚未实现。请使用企查查报告提取功能。"
    )


@router.get("/extractors")
async def list_extractors():
    """
    列出所有可用的提取器类型
    """
    return {
        "success": True,
        "extractors": [
            {
                "id": "qcc",
                "name": "企查查报告",
                "status": "available",
                "description": "支持企查查企业信用报告专业版PDF"
            },
            {
                "id": "archives",
                "name": "工商内档",
                "status": "planned",
                "description": "支持各地工商局企业登记档案（开发中）"
            }
        ]
    }
