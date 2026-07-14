"""
企查查报告处理流水线服务

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
    ChangeType,
    ShareholderSnapshot,
    HistoryDraft,
    ReviewIssue,
    ReviewSeverity,
)
from app.services.qcc_extractor import QCCReportExtractor
from app.services.qcc_extractor.changes import (
    ChangeGrouper,
    ChangeTypeAnalyzer,
    HistoryEvolutionGenerator,
    ChangeType,
    ChangeGroup,
)
from app.services.qcc_extractor.history_docx_generator import generate_history_word_document


class QCCProcessingService:
    """
    企查查报告处理流水线

    使用方式：
        service = QCCProcessingService()
        report = service.upload(temp_path, filename)
        report = service.extract(report)
        report = service.normalize(report)
        report = service.classify(report)
        report = service.draft(report)
        report = service.review(report)
        output_path = service.export(report, ...)

    每个步骤都会更新 report.status，便于前端跟踪进度。
    """

    def __init__(self):
        self.extractor = QCCReportExtractor()
        self.grouper = ChangeGrouper()
        self.analyzer = ChangeTypeAnalyzer()

    # ================================================================
    # Step 1: Upload
    # ================================================================
    def upload(self, temp_path: str, filename: str) -> Report:
        """初始化 Report，记录上传信息"""
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

        # 填充基础信息
        report.company_name = raw.get("report_meta", {}).get("company_name", "")
        report.total_pages = raw.get("report_meta", {}).get("total_pages", 0)
        report.raw_extraction = raw
        report.extract_time_ms = elapsed_ms

        # 工商注册信息
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

        # 变更记录 -> ExtractedChange（带证据链）
        raw_changes = basic.get("change_history", [])
        for idx, rc in enumerate(raw_changes):
            # 构建证据链
            source_records = []
            if rc.get("before"):
                source_records.append(f"变更前: {rc['before']}")
            if rc.get("after"):
                source_records.append(f"变更后: {rc['after']}")

            warnings = []
            # 如果变更前后内容都为空，标记异常
            if not rc.get("before") and not rc.get("after"):
                warnings.append("变更前后内容均为空，可能为格式解析异常")
            # 如果变更项目为空
            if not rc.get("project"):
                warnings.append("变更项目为空")

            report.extracted_changes.append(
                ExtractedChange(
                    seq=rc.get("seq", str(idx + 1)),
                    date=rc.get("date", ""),
                    raw_date=rc.get("date", ""),
                    project=rc.get("project", ""),
                    before=rc.get("before", ""),
                    after=rc.get("after", ""),
                    source=rc.get("source", ""),
                    source_records=source_records,
                    page_nos=[],  # TODO: 后续从 structure.py 传入 page markers
                    parser_version="1.0.0",
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
        """清洗和规范化：日期格式化、空值处理、去重"""
        # 日期统一格式化为 "YYYY-MM-DD"
        for ch in report.extracted_changes:
            ch.raw_date = self._normalize_date(ch.raw_date)

        # 去重：同一天同一项目的重复记录
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
        """对变更记录按日期分组并分类"""
        # 将 ExtractedChange 转回 Dict 以便复用现有 grouper/analyzer
        raw_changes = [
            {
                "seq": ch.seq,
                "date": ch.raw_date,
                "project": ch.project,
                "before": ch.before,
                "after": ch.after,
                "source": ch.source,
            }
            for ch in report.extracted_changes
        ]

        groups = self.grouper.group_by_date(raw_changes)
        for group in groups:
            self.analyzer.analyze(group)

        # 转回模型
        for g in groups:
            if not g.is_history_relevant:
                continue

            records = [
                ch for ch in report.extracted_changes
                if ch.raw_date == g.raw_date
            ]

            # 映射 change_types
            model_types = []
            for ct in g.change_types:
                if ct == ChangeType.EQUITY_TRANSFER:
                    model_types.append(ChangeType.EQUITY_TRANSFER)
                elif ct == ChangeType.CAPITAL_INCREASE:
                    model_types.append(ChangeType.CAPITAL_INCREASE)
                elif ct == ChangeType.CAPITAL_DECREASE:
                    model_types.append(ChangeType.CAPITAL_DECREASE)
                else:
                    model_types.append(ChangeType.OTHER)

            report.change_groups.append(
                ChangeGroupModel(
                    date=g.date,
                    raw_date=g.raw_date,
                    records=records,
                    change_types=model_types,
                    exits=g.exits,
                    enters=g.enters,
                    capital_before=g.capital_before,
                    capital_after=g.capital_after,
                )
            )

        report.status = PipelineStatus.CLASSIFIED
        return report

    # ================================================================
    # Step 5: Draft
    # ================================================================
    def draft(self, report: Report) -> Report:
        """生成历史沿革草稿——不输出最终法律事实"""
        generator = HistoryEvolutionGenerator(report.company_name)

        # 将 change_groups 转回 ChangeGroup 以便复用现有生成器
        raw_groups = []
        for cg in report.change_groups:
            g = ChangeGroup(
                date=cg.date,
                raw_date=cg.raw_date,
                records=[
                    {"seq": r.seq, "date": r.raw_date, "project": r.project,
                     "before": r.before, "after": r.after, "source": r.source}
                    for r in cg.records
                ],
                change_types=[self._map_change_type(t) for t in cg.change_types],
                exits=cg.exits,
                enters=cg.enters,
                capital_before=cg.capital_before,
                capital_after=cg.capital_after,
                is_history_relevant=True,
            )
            raw_groups.append(g)

        # 复用现有生成器生成文本
        text = generator.generate_text(raw_groups)

        # 将文本拆分为按日期分段的 HistoryDraft
        # 简单策略：按 "【YYYY年M月D日 ...】" 分割
        report.history_drafts = self._split_into_drafts(
            text, report.change_groups
        )
        report.history_text_combined = text

        report.status = PipelineStatus.DRAFTED
        return report

    # ================================================================
    # Step 6: Review
    # ================================================================
    def review(self, report: Report) -> Report:
        """自动复核，生成 ReviewIssue 列表"""
        issues = []

        # 规则 1：检测事实推断过度（旧代码残留的自动断言）
        for idx, hd in enumerate(report.history_drafts):
            if "召开股东会并作出决议" in hd.draft_text:
                issues.append(
                    ReviewIssue(
                        severity=ReviewSeverity.CRITICAL,
                        category="fact_inferred",
                        description="草稿中包含'召开股东会并作出决议'，企查查无法证明该事实",
                        source_change_date=hd.date,
                        suggested_fix="改为'根据企查查报告，公司于该日完成工商变更登记'，并提示律师补充股东会决议",
                    )
                )
            if "签署了《股权转让协议》" in hd.draft_text:
                issues.append(
                    ReviewIssue(
                        severity=ReviewSeverity.CRITICAL,
                        category="fact_inferred",
                        description="草稿中包含'签署了股权转让协议'，企查查无法证明该事实",
                        source_change_date=hd.date,
                        suggested_fix="删除该句，提示律师根据实际协议补充",
                    )
                )

        # 规则 2：检测数据缺失
        for cg in report.change_groups:
            if ChangeType.EQUITY_TRANSFER in cg.change_types:
                for r in cg.records:
                    if not r.before or not r.after:
                        issues.append(
                            ReviewIssue(
                                severity=ReviewSeverity.WARNING,
                                category="data_missing",
                                description=f"{cg.date} 股权转让记录缺少变更前或变更后内容",
                                source_change_date=cg.date,
                                suggested_fix="核对企查查 PDF 原文，手动补充",
                            )
                        )

            if ChangeType.CAPITAL_INCREASE in cg.change_types or \
               ChangeType.CAPITAL_DECREASE in cg.change_types:
                if not cg.capital_before or not cg.capital_after:
                    issues.append(
                        ReviewIssue(
                            severity=ReviewSeverity.WARNING,
                            category="data_missing",
                            description=f"{cg.date} 注册资本变更但未能解析变更前后金额",
                            source_change_date=cg.date,
                            suggested_fix="核对企查查 PDF 原文，手动补充注册资本",
                        )
                    )

        # 规则 3：检测股权结构不完整
        has_structure = any("股权结构" in hd.draft_text for hd in report.history_drafts)
        if has_structure:
            issues.append(
                ReviewIssue(
                    severity=ReviewSeverity.INFO,
                    category="legal_risk",
                    description="草稿中包含股权结构表，但企查查只显示变更涉及股东，未显示未变更股东",
                    suggested_fix="在股权结构表前添加提示：'以上为本次变更涉及股东，完整结构需根据工商档案补充'",
                )
            )

        # 规则 4：检测 low confidence 的解析结果
        for ch in report.extracted_changes:
            if ch.confidence < 0.8:
                issues.append(
                    ReviewIssue(
                        severity=ReviewSeverity.WARNING,
                        category="format_error",
                        description=f"{ch.date} {ch.project} 解析置信度较低 ({ch.confidence})",
                        source_change_date=ch.date,
                        suggested_fix=f"核对原文: {' | '.join(ch.warnings)}",
                    )
                )

        report.review_issues = issues
        report.review_passed = len([i for i in issues if i.severity == ReviewSeverity.CRITICAL]) == 0

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
        # 使用已生成的 history_text_combined
        history_result = {
            "text": report.history_text_combined,
            "markdown": report.history_text_combined,
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
            "category_stats": {},
        }
        # 统计
        for cg in report.change_groups:
            key = "、".join([t.value for t in cg.change_types]) if cg.change_types else "其他变更"
            history_result["category_stats"][key] = history_result["category_stats"].get(key, 0) + 1

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
    # 便捷方法：一次性跑完流水线
    # ================================================================
    def process_full(
        self,
        pdf_path: str,
        filename: str,
    ) -> Report:
        """一键跑完完整流水线（upload -> extract -> normalize -> classify -> draft -> review）"""
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
    def _normalize_date(date_str: str) -> str:
        """统一日期格式为 YYYY-MM-DD"""
        import re
        m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        return date_str

    @staticmethod
    def _map_change_type(model_type: ChangeType):
        """将模型层的 ChangeType 映射回业务层的 ChangeType"""
        from app.services.qcc_extractor.changes import ChangeType as BizChangeType
        mapping = {
            ChangeType.EQUITY_TRANSFER: BizChangeType.EQUITY_TRANSFER,
            ChangeType.CAPITAL_INCREASE: BizChangeType.CAPITAL_INCREASE,
            ChangeType.CAPITAL_DECREASE: BizChangeType.CAPITAL_DECREASE,
        }
        return mapping.get(model_type, BizChangeType.EQUITY_TRANSFER)

    @staticmethod
    def _split_into_drafts(text: str, change_groups: List[ChangeGroupModel]) -> List[HistoryDraft]:
        """将合并文本按变更组拆分为独立的 HistoryDraft"""
        drafts = []
        if not text.strip():
            return drafts

        import re
        # 按日期标题分割：【YYYY年M月D日 ...】
        # 保留分割符
        parts = re.split(r'(【\d{4}年\d{1,2}月\d{1,2}日[^】]*】)', text)

        current_date = ""
        current_text = ""
        group_idx = 0

        for part in parts:
            if not part.strip():
                continue
            m = re.match(r'【(\d{4}年\d{1,2}月\d{1,2}日[^】]*)】', part)
            if m:
                # 保存上一个
                if current_text.strip():
                    cg = change_groups[group_idx] if group_idx < len(change_groups) else None
                    drafts.append(_build_draft(current_date, current_text, cg))
                    group_idx += 1
                current_date = m.group(1)
                current_text = part + "\n"
            else:
                current_text += part

        # 最后一个
        if current_text.strip():
            cg = change_groups[group_idx] if group_idx < len(change_groups) else None
            drafts.append(_build_draft(current_date, current_text, cg))

        return drafts


def _build_draft(date: str, text: str, cg: Optional[ChangeGroupModel]) -> HistoryDraft:
    """从文本片段和变更组构建 HistoryDraft"""
    missing_fields = []
    warnings = []
    source_records = []

    if cg:
        # 根据变更类型推断 missing_fields
        if ChangeType.EQUITY_TRANSFER in cg.change_types:
            missing_fields.extend(["转让对价", "股权转让协议签署日期", "股东会决议日期"])
        if ChangeType.CAPITAL_INCREASE in cg.change_types:
            missing_fields.extend(["验资报告编号", "出资期限", "股东会决议日期"])
        if ChangeType.CAPITAL_DECREASE in cg.change_types:
            missing_fields.extend(["减资公告刊登媒体", "减资公告日期", "债权人申报情况"])

        # 从 records 提取 warnings
        for r in cg.records:
            warnings.extend(r.warnings)
            source_records.append({
                "seq": r.seq,
                "date": r.raw_date,
                "project": r.project,
                "before": r.before,
                "after": r.after,
                "confidence": r.confidence,
            })

    # 检测文本中的推断过度
    if "【**】" in text:
        missing_fields.append("存在占位符【**】，需补充具体数值")
    if "召开股东会并作出决议" in text:
        warnings.append("文本中包含'召开股东会并作出决议'，该事实无法从企查查证明")
    if "签署了《股权转让协议》" in text:
        warnings.append("文本中包含'签署股权转让协议'，该事实无法从企查查证明")

    return HistoryDraft(
        date=date,
        sequence_title=date,
        draft_text=text.strip(),
        missing_fields=list(set(missing_fields)),
        warnings=list(set(warnings)),
        source_records=source_records,
    )
