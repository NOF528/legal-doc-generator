"""
企查查 PDF 报告提取器（重构后）

使用示例：
    from app.services.qcc_extractor import QCCReportExtractor, extract_history_evolution

    extractor = QCCReportExtractor()
    result = extractor.extract("/path/to/qcc_report.pdf")

    raw_changes = result["basic_info"]["change_history"]
    company_name = result["report_meta"]["company_name"]
    history = extract_history_evolution(raw_changes, company_name)
"""

from .extractor import QCCReportExtractor
from .change_record_parser import parse_change_records
from .event_classifier import classify_events
from .history_draft_renderer import render_qcc_drafts, combine_drafts
from .review_rules import full_review
from .models import (
    ChangeType,
    ClassificationLevel,
    ChangeFact,
    ChangeEvent,
    HistoryDraft,
    HistoryEvolutionResult,
)


def extract_history_evolution(raw_changes: list, company_name: str = "公司") -> dict:
    """
    兼容旧 API 的主入口

    返回字典包含：
    - text / markdown / combined_text: 合并后的草稿文本
    - changes_count: 变更事件数量
    - changes: 兼容旧前端的变更列表
    - category_stats: 分类统计
    - drafts: 新架构下的草稿段落列表
    - review_issues: 复核问题列表
    - review_passed: 是否通过复核（无 critical 问题）
    """
    facts = parse_change_records(raw_changes)
    events = classify_events(facts, company_name)
    drafts = render_qcc_drafts(events, company_name)
    review_issues = full_review(events, drafts)

    # 兼容旧前端的 changes 列表
    compatible_changes = []
    category_stats = {}
    for event in events:
        category = event.event_type.value
        category_stats[category] = category_stats.get(category, 0) + 1

        compatible_changes.append({
            "date": event.date,
            "category": category,
            "type": category,
            "project": "、".join([f.project for f in event.facts]),
            "transfer_from": event.exits[0].name if event.exits else "",
            "transfer_to": event.enters[0].name if event.enters else "",
            "transfer_ratio": event.exits[0].ratio if event.exits else "",
            "capital_before": event.capital_before,
            "capital_after": event.capital_after,
            "exits": [s.__dict__ for s in event.exits],
            "enters": [s.__dict__ for s in event.enters],
            "sequence": f"{event.date} {category}",
            "classification_level": event.classification_level.value,
            "missing_fields": event.missing_fields,
            "warnings": event.warnings,
        })

    combined_text = combine_drafts(drafts)

    review_passed = not any(
        issue.severity == "critical" for issue in review_issues
    )

    return {
        "text": combined_text,
        "markdown": combined_text,
        "combined_text": combined_text,
        "changes_count": len(events),
        "changes": compatible_changes,
        "category_stats": category_stats,
        "drafts": [d.__dict__ for d in drafts],
        "review_issues": [issue.__dict__ for issue in review_issues],
        "review_passed": review_passed,
    }


__all__ = [
    "QCCReportExtractor",
    "extract_history_evolution",
    "parse_change_records",
    "classify_events",
    "render_qcc_drafts",
    "combine_drafts",
    "full_review",
    "ChangeType",
    "ClassificationLevel",
    "ChangeFact",
    "ChangeEvent",
    "HistoryDraft",
    "HistoryEvolutionResult",
]
