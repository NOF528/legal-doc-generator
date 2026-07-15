"""
企查查报告处理流水线服务（重构后）

流程：upload -> extract -> normalize -> classify -> draft -> review -> export
API 层只负责请求校验和响应，不直接写业务逻辑。
"""

import os
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.models.pipeline import (
    Report,
    PipelineStatus,
    ExtractedChange,
    ChangeGroupModel,
    ChangeType as ModelChangeType,
    ShareholderSnapshot,
    HistoryDraft as PipelineHistoryDraft,
    ReviewIssue as PipelineReviewIssue,
    ReviewSeverity,
)
from app.services.qcc_extractor import QCCReportExtractor
from app.services.qcc_extractor.models import (
    ChangeType,
    ClassificationLevel,
    ChangeFact,
    ChangeEvent,
    HistoryDraft,
    ReviewIssue,
)
from app.services.qcc_extractor.change_record_parser import parse_change_records, normalize_date, format_date
from app.services.qcc_extractor.event_classifier import classify_events
from app.services.qcc_extractor.history_draft_renderer import render_qcc_drafts, combine_drafts
from app.services.qcc_extractor.review_rules import full_review
from app.services.qcc_extractor.history_docx_generator import generate_history_word_document


class QCCProcessingService:
    """
    企查查报告处理流水线
    """

    def __init__(self):
        self.extractor = QCCReportExtractor()

    # ================================================================
    # Step 1: Upload
    # ================================================================
    def upload(self, temp_path: str, filename: str) -> Report:
        """初始化 Report"""
        return Report(
            filename=filename,
            status=PipelineStatus.UPLOADED,
        )

    # ================================================================
    # Step 2: Extract
    # ================================================================
    def extract(self, report: Report, pdf_path: str) -> Report:
        """从 PDF 提取所有结构化数据"""
        start = time.time()
        raw = self.extractor.extract(pdf_path)
        elapsed_ms = int((time.time() - start) * 1000)

        report.company_name = raw.get("report_meta", {}).get("company_name", "")
        report.total_pages = raw.get("report_meta", {}).get("total_pages", 0)
        report.raw_extraction = raw
        report.extract_time_ms = elapsed_ms

        basic = raw.get("basic_info", {})
        report.registration = basic.get("registration", {})

        # 当前股东
        for sh in basic.get("shareholders", []):
            report.current_shareholders.append(
                ShareholderSnapshot(
                    name=sh.get("name", ""),
                    amount=sh.get("amount", "【**】"),
                    ratio=sh.get("ratio", "【**】"),
                    capital=sh.get("amount", "【**】"),
                    change_type=None,
                )
            )

        # 变更记录 -> ExtractedChange
        raw_changes = basic.get("change_history", [])
        for idx, rc in enumerate(raw_changes):
            source_records = []
            if rc.get("before"):
                source_records.append(f"变更前: {rc['before']}")
            if rc.get("after"):
                source_records.append(f"变更后: {rc['after']}")

            warnings = []
            if not rc.get("before") and not rc.get("after"):
                warnings.append("变更前后内容均为空，可能为格式解析异常")
            if not rc.get("project"):
                warnings.append("变更项目为空")

            report.extracted_changes.append(
                ExtractedChange(
                    seq=rc.get("seq", str(idx + 1)),
                    date=format_date(rc.get("date", "")),
                    raw_date=normalize_date(rc.get("date", "")),
                    project=rc.get("project", ""),
                    before=rc.get("before", ""),
                    after=rc.get("after", ""),
                    source=rc.get("source", ""),
                    source_records=source_records,
                    page_nos=rc.get("page_nos", []) or [],
                    parser_version="2.0.0",
                    confidence=0.9 if not warnings else 0.6,
                    warnings=warnings,
                )
            )

        report.status = PipelineStatus.EXTRACTED
        return report

    # ================================================================
    # Step 3: Normalize
    # ================================================================
    def normalize(self, report: Report) -> Report:
        """清洗和规范化"""
        # 去重
        seen = set()
        deduped = []
        for ch in report.extracted_changes:
            key = (ch.raw_date, ch.project, ch.before, ch.after)
            if key not in seen:
                seen.add(key)
                deduped.append(ch)
            else:
                ch.warnings.append("检测到重复记录，已去重")
        report.extracted_changes = deduped

        report.status = PipelineStatus.NORMALIZED
        return report

    # ================================================================
    # Step 4: Classify
    # ================================================================
    def classify(self, report: Report) -> Report:
        """对变更记录分类为事件"""
        raw_changes = [
            {
                "seq": ch.seq,
                "date": ch.raw_date,
                "project": ch.project,
                "before": ch.before,
                "after": ch.after,
                "source": ch.source,
                "page_nos": ch.page_nos,
            }
            for ch in report.extracted_changes
        ]

        facts = parse_change_records(raw_changes)
        events = classify_events(facts, report.company_name)

        # 转换回 pipeline 模型
        for event in events:
            records = [
                ch for ch in report.extracted_changes
                if ch.raw_date == event.raw_date
            ]

            report.change_groups.append(
                ChangeGroupModel(
                    date=event.date,
                    raw_date=event.raw_date,
                    records=records,
                    change_types=[self._map_change_type(event.event_type)],
                    exits=[s.__dict__ for s in event.exits],
                    enters=[s.__dict__ for s in event.enters],
                    capital_before=event.capital_before,
                    capital_after=event.capital_after,
                )
            )

        report.status = PipelineStatus.CLASSIFIED
        return report

    # ================================================================
    # Step 5: Draft
    # ================================================================
    def draft(self, report: Report) -> Report:
        """生成历史沿革草稿"""
        raw_changes = [
            {
                "seq": ch.seq,
                "date": ch.raw_date,
                "project": ch.project,
                "before": ch.before,
                "after": ch.after,
                "source": ch.source,
                "page_nos": ch.page_nos,
            }
            for ch in report.extracted_changes
        ]

        facts = parse_change_records(raw_changes)
        events = classify_events(facts, report.company_name)
        drafts = render_qcc_drafts(events, report.company_name)

        # 转换为 pipeline 模型
        report.history_drafts = [
            PipelineHistoryDraft(
                date=d.date,
                sequence_title=d.sequence_title,
                draft_text=d.draft_text,
                missing_fields=d.missing_fields,
                warnings=d.warnings,
                source_records=[ev.__dict__ for ev in d.evidence],
                is_confirmed=d.is_confirmed,
            )
            for d in drafts
        ]

        report.history_text_combined = combine_drafts(drafts)
        report.status = PipelineStatus.DRAFTED
        return report

    # ================================================================
    # Step 6: Review
    # ================================================================
    def review(self, report: Report) -> Report:
        """自动复核"""
        raw_changes = [
            {
                "seq": ch.seq,
                "date": ch.raw_date,
                "project": ch.project,
                "before": ch.before,
                "after": ch.after,
                "source": ch.source,
                "page_nos": ch.page_nos,
            }
            for ch in report.extracted_changes
        ]

        facts = parse_change_records(raw_changes)
        events = classify_events(facts, report.company_name)
        drafts = render_qcc_drafts(events, report.company_name)
        issues = full_review(events, drafts)

        report.review_issues = [
            PipelineReviewIssue(
                severity=ReviewSeverity(issue.severity),
                category=issue.category,
                description=issue.description,
                source_change_date=issue.source_change_date,
                suggested_fix=issue.suggested_fix,
            )
            for issue in issues
        ]

        report.review_passed = not any(
            i.severity == ReviewSeverity.CRITICAL for i in report.review_issues
        )

        report.status = PipelineStatus.REVIEWED
        return report

    # ================================================================
    # Step 7: Export
    # ================================================================
    def export(
        self,
        report: Report,
        output_path: str,
        template_path: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """导出为 Word 文档"""
        category_stats = {}
        for cg in report.change_groups:
            key = "、".join([t.value for t in cg.change_types]) if cg.change_types else "其他变更"
            category_stats[key] = category_stats.get(key, 0) + 1

        history_result = {
            "text": report.history_text_combined,
            "markdown": report.history_text_combined,
            "combined_text": report.history_text_combined,
            "changes_count": len(report.change_groups),
            "changes": [
                {
                    "date": cg.date,
                    "category": "、".join([t.value for t in cg.change_types]),
                    "type": "、".join([t.value for t in cg.change_types]),
                    "project": "、".join([r.project for r in cg.records]),
                    "transfer_from": cg.exits[0].get("name", "") if cg.exits else "",
                    "transfer_to": cg.enters[0].get("name", "") if cg.enters else "",
                    "transfer_ratio": cg.exits[0].get("ratio", "") if cg.exits else "",
                    "capital_before": cg.capital_before,
                    "capital_after": cg.capital_after,
                    "exits": cg.exits,
                    "enters": cg.enters,
                    "sequence": f"{cg.date} " + "、".join([t.value for t in cg.change_types]),
                }
                for cg in report.change_groups
            ],
            "category_stats": category_stats,
        }

        generate_history_word_document(
            company_name=report.company_name,
            history_result=history_result,
            output_path=output_path,
            template_path=template_path,
            extra_data=extra_data,
        )

        report.exported_file_path = output_path
        report.exported_at = datetime.now()
        report.status = PipelineStatus.EXPORTED
        return output_path

    # ================================================================
    # 便捷方法
    # ================================================================
    def process_full(self, pdf_path: str, filename: str) -> Report:
        """一键跑完完整流水线"""
        report = self.upload(pdf_path, filename)
        report = self.extract(report, pdf_path)
        report = self.normalize(report)
        report = self.classify(report)
        report = self.draft(report)
        report = self.review(report)
        return report

    # ================================================================
    # 内部工具方法
    # ================================================================
    @staticmethod
    def _map_change_type(event_type: ChangeType) -> ModelChangeType:
        """将 qcc_extractor 的 ChangeType 映射为 pipeline 模型的 ChangeType"""
        mapping = {
            ChangeType.EQUITY_TRANSFER: ModelChangeType.EQUITY_TRANSFER,
            ChangeType.CAPITAL_INCREASE: ModelChangeType.CAPITAL_INCREASE,
            ChangeType.CAPITAL_DECREASE: ModelChangeType.CAPITAL_DECREASE,
            ChangeType.SHAREHOLDER_CHANGE: ModelChangeType.OTHER,
            ChangeType.CAPITAL_CHANGE: ModelChangeType.OTHER,
            ChangeType.NAME_CHANGE: ModelChangeType.NAME_CHANGE,
            ChangeType.LEGAL_REP_CHANGE: ModelChangeType.LEGAL_REP_CHANGE,
            ChangeType.ADDRESS_CHANGE: ModelChangeType.ADDRESS_CHANGE,
            ChangeType.SCOPE_CHANGE: ModelChangeType.SCOPE_CHANGE,
            ChangeType.OTHER: ModelChangeType.OTHER,
        }
        return mapping.get(event_type, ModelChangeType.OTHER)
