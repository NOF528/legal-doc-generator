"""
企查查报告提取 API（重构后）

原则：API 只负责请求校验和响应，所有业务逻辑委托给 QCCProcessingService。
"""

import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import FileResponse
from typing import Optional

from app.core.upload_guard import save_upload_temp, cleanup_temp
from app.services.qcc_pipeline import QCCProcessingService

router = APIRouter()


def _client_host(request: Request) -> str | None:
    """获取客户端 IP（考虑反向代理）"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _build_compatible_response(report):
    """构建兼容旧前端的历史沿革响应"""
    # 计算 category_stats
    category_stats = {}
    for cg in report.change_groups:
        key = "、".join([t.value for t in cg.change_types]) if cg.change_types else "其他变更"
        category_stats[key] = category_stats.get(key, 0) + 1

    # 构建兼容旧前端的 changes 列表
    compatible_changes = []
    for cg in report.change_groups:
        compatible_changes.append({
            "date": cg.date,
            "category": "、".join([t.value for t in cg.change_types]) if cg.change_types else "其他变更",
            "type": "、".join([t.value for t in cg.change_types]) if cg.change_types else "其他变更",
            "project": "、".join([r.project for r in cg.records]),
            "transfer_from": cg.exits[0].get("name", "") if cg.exits else "",
            "transfer_to": cg.enters[0].get("name", "") if cg.enters else "",
            "transfer_ratio": cg.exits[0].get("ratio", "") if cg.exits else "",
            "capital_before": cg.capital_before,
            "capital_after": cg.capital_after,
            "exits": cg.exits,
            "enters": cg.enters,
            "sequence": f"{cg.date} " + "、".join([t.value for t in cg.change_types]),
        })

    # 构建兼容旧前端的 history_evolution
    history_evolution_compat = {
        # 新字段
        "drafts": [d.model_dump() for d in report.history_drafts],
        "combined_text": report.history_text_combined,
        # 旧字段（兼容前端）
        "text": report.history_text_combined,
        "markdown": report.history_text_combined,
        "changes_count": len(report.change_groups),
        "changes": compatible_changes,
        "category_stats": category_stats,
    }

    # 汇总所有草稿的待补充字段（去重，保持顺序）
    all_missing = []
    for d in report.history_drafts:
        for m in d.missing_fields:
            if m not in all_missing:
                all_missing.append(m)

    return {
        "success": True,
        "company_name": report.company_name,
        "status": report.status.value,
        "history_evolution": history_evolution_compat,
        "changes": compatible_changes,
        "missing_fields": all_missing,
        "review_issues": [i.model_dump() for i in report.review_issues],
        "review_passed": report.review_passed,
        "filename": report.filename,
        # 兼容旧前端的 basic_info
        "basic_info": {
            "registration": report.registration or {},
            "current_shareholders": [
                {"seq": str(i+1), "name": s.name, "ratio": s.ratio, "amount": s.amount}
                for i, s in enumerate(report.current_shareholders)
            ],
        },
    }


# ================================================================
# 提取完整结构化数据（含流水线中间态）
# ================================================================
@router.post("/extract")
async def extract_qcc_report(request: Request, file: UploadFile = File(...)):
    """
    上传企查查 PDF 报告，跑完整流水线（extract -> normalize -> classify -> draft -> review）

    返回完整的 Report 模型，包含证据链、历史沿革草稿、复核问题。
    """
    temp_path = None
    try:
        temp_path, file_hash = await save_upload_temp(file, _client_host(request))

        service = QCCProcessingService()
        report = service.process_full(temp_path, file.filename)

        return {
            "success": True,
            "data": report.model_dump(),
            "filename": file.filename,
            "file_hash": file_hash,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"提取失败: {str(e)}\n{traceback.format_exc()}")
    finally:
        cleanup_temp(temp_path)


# ================================================================
# 提取基础信息（精简版）
# ================================================================
@router.post("/extract-basic")
async def extract_qcc_basic(request: Request, file: UploadFile = File(...)):
    """
    提取企查查报告基础信息（精简版）
    只返回核心工商信息、股东、主要人员
    """
    temp_path = None
    try:
        temp_path, _ = await save_upload_temp(file, _client_host(request))

        service = QCCProcessingService()
        report = service.upload(temp_path, file.filename)
        report = service.extract(report, temp_path)

        simplified = {
            "report_meta": {
                "company_name": report.company_name,
                "total_pages": report.total_pages,
                "parser_version": report.parser_version,
            },
            "registration": report.registration or {},
            "shareholders": [
                {"name": s.name, "ratio": s.ratio, "amount": s.amount}
                for s in report.current_shareholders
            ],
            "change_history_count": len(report.extracted_changes),
            "review_issues_count": len(report.review_issues),
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
        cleanup_temp(temp_path)


# ================================================================
# 生成历史沿革（完整流水线）
# ================================================================
@router.post("/history-evolution")
async def extract_history_evolution_endpoint(request: Request, file: UploadFile = File(...)):
    """
    提取企查查报告并生成历史沿革

    返回：
    - 历史沿革草稿（draft_text + missing_fields + warnings + source_records）
    - 结构化的变更记录（含证据链）
    - 复核问题列表
    """
    temp_path = None
    try:
        temp_path, file_hash = await save_upload_temp(file, _client_host(request))

        service = QCCProcessingService()
        report = service.process_full(temp_path, file.filename)

        response = _build_compatible_response(report)
        response["file_hash"] = file_hash
        return response

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"提取失败: {str(e)}\n{traceback.format_exc()}")
    finally:
        cleanup_temp(temp_path)


# ================================================================
# 生成历史沿革 Word 文档
# ================================================================
@router.post("/history-evolution/docx")
async def generate_history_word(
    request: Request,
    file: UploadFile = File(...),
    law_firm_name: str = Form(""),
    lawyer_name: str = Form(""),
    use_template: bool = Form(False)
):
    """
    提取企查查报告并生成历史沿革 Word 文档

    参数：
    - file: PDF 文件
    - law_firm_name: 律所名称（可选）
    - lawyer_name: 律师姓名（可选）
    - use_template: 是否使用自定义模板

    返回：
    - 可直接下载的 Word 文档(.docx)
    """
    temp_path = None
    output_path = None

    try:
        temp_path, _ = await save_upload_temp(file, _client_host(request))

        service = QCCProcessingService()
        report = service.process_full(temp_path, file.filename)

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

        service.export(
            report,
            output_path=output_path,
            template_path=template_path,
            extra_data=extra_data if extra_data else None,
        )

        return FileResponse(
            output_path,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            filename=f"{report.company_name}_历史沿革.docx"
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        if output_path and os.path.exists(output_path):
            os.unlink(output_path)
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}\n{traceback.format_exc()}")
    finally:
        cleanup_temp(temp_path)


# ================================================================
# 知识产权抽取（商标 + 专利）
# ================================================================
@router.post("/ip-asset")
async def extract_ip_asset_endpoint(request: Request, file: UploadFile = File(...)):
    """
    提取企查查报告的知识产权：
    - 商标：只保留「已注册」状态（图案仅在 docx 中体现，JSON 预览标注 has_image）
    - 专利：只保留法律状态为「授权」的，类型归一为 发明/实用新型/外观设计
    """
    temp_path = None
    try:
        temp_path, _ = await save_upload_temp(file, _client_host(request))

        from app.services.ip_extractor import extract_ip_assets
        result = extract_ip_assets(temp_path, with_images=True)

        return {
            "success": True,
            "company_name": result.company_name,
            "trademarks": [
                {**t, "has_image": t["app_no"] in result.trademark_images}
                for t in result.trademarks
            ],
            "patents": result.patents,
            "summary": result.summary(),
            "trademark_summary_text": result.trademark_summary_text(),
            "patent_summary_text": result.patent_summary_text(),
            "warnings": result.warnings,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"提取失败: {str(e)}\n{traceback.format_exc()}")
    finally:
        cleanup_temp(temp_path)


@router.post("/ip-asset/docx")
async def generate_ip_word(request: Request, file: UploadFile = File(...)):
    """生成知识产权 Word 文档（汇总段 + 商标表含图案 + 专利表）"""
    temp_path = None
    output_path = None

    try:
        temp_path, _ = await save_upload_temp(file, _client_host(request))

        from app.services.ip_extractor import extract_ip_assets
        from app.services.ip_extractor.ip_docx_generator import generate_ip_word_document
        result = extract_ip_assets(temp_path, with_images=True)

        output_fd, output_path = tempfile.mkstemp(suffix='.docx')
        os.close(output_fd)
        generate_ip_word_document(result, output_path)

        return FileResponse(
            output_path,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            filename=f"{result.company_name}_知识产权.docx"
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        if output_path and os.path.exists(output_path):
            os.unlink(output_path)
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}\n{traceback.format_exc()}")
    finally:
        cleanup_temp(temp_path)


# ================================================================
# 模板列表
# ================================================================
@router.get("/history-evolution/templates")
async def list_templates():
    """
    列出所有可用的 Word 模板
    """
    from app.services.qcc_extractor.history_docx_generator import list_available_templates, TEMPLATE_DIR

    templates = list_available_templates()
    return {
        "success": True,
        "templates": templates,
        "template_dir": TEMPLATE_DIR,
        "instructions": "将模板文件(.docx)放入上述目录即可使用。支持的占位符: {{company_name}}, {{history_content}}, {{report_date}}, {{change_count}}, {{law_firm_name}}, {{lawyer_name}}"
    }


# ================================================================
# 其他接口
# ================================================================
@router.post("/archives/extract")
async def extract_business_archives(file: UploadFile = File(...)):
    """
    提取工商内档（预留接口）
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
