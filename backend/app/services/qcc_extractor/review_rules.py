"""
复核规则

定义从"QCC 事实草稿"升级为"法律文件成稿"所需的字段契约。
"""

from typing import List
from .models import ChangeEvent, HistoryDraft, ReviewIssue, ChangeType, ClassificationLevel


# 每种事件类型升级为法律文件成稿所需的字段
FIELD_CONTRACTS = {
    ChangeType.EQUITY_TRANSFER: [
        "股东会决议日期",
        "转让方",
        "受让方",
        "转让比例",
        "对应注册资本",
        "转让对价",
        "股权转让协议签署日期",
        "优先购买权情况",
        "变更后完整股权结构",
    ],
    ChangeType.CAPITAL_INCREASE: [
        "股东会决议日期",
        "增资认购方",
        "认购金额",
        "认购新增注册资本",
        "出资期限",
        "验资报告编号",
        "验资报告日期",
        "变更后完整股权结构",
    ],
    ChangeType.CAPITAL_DECREASE: [
        "减资决议日期",
        "减资公告刊登媒体",
        "减资公告日期",
        "债权人申报情况",
        "变更后完整股权结构",
    ],
    ChangeType.SHAREHOLDER_CHANGE: [
        "变更交易性质",
        "交易对方",
        "交易对价",
        "变更后完整股权结构",
    ],
    ChangeType.CAPITAL_CHANGE: [
        "变更性质（增资/减资）",
        "股东会决议日期",
        "变更后完整股权结构",
    ],
}


def review_events(events: List[ChangeEvent]) -> List[ReviewIssue]:
    """对事件进行规则复核"""
    issues = []

    for event in events:
        # 规则1：任何 INFERRED 或 UNDETERMINED 事件都需要律师确认
        if event.classification_level == ClassificationLevel.INFERRED:
            issues.append(ReviewIssue(
                category="fact_inferred",
                severity="warning",
                description=f"{event.date} 的 {event.event_type.value} 为系统推断，需律师确认",
                source_change_date=event.date,
                suggested_fix="核对股东会决议、协议等补充材料后确认或修正事件类型",
            ))
        elif event.classification_level == ClassificationLevel.UNDETERMINED:
            issues.append(ReviewIssue(
                category="undetermined",
                severity="critical",
                description=f"{event.date} 的变更性质无法确定",
                source_change_date=event.date,
                suggested_fix="补充公司章程、工商档案或协议材料后重新分类",
            ))

        # 规则2：检测缺失字段
        required = FIELD_CONTRACTS.get(event.event_type, [])
        for field in required:
            if field not in event.known_facts or not event.known_facts[field]:
                issues.append(ReviewIssue(
                    category="data_missing",
                    severity="warning",
                    description=f"{event.date} {event.event_type.value} 缺少字段：{field}",
                    source_change_date=event.date,
                    suggested_fix=f"在律师复核时补充 {field}",
                ))

        # 规则3：股权转让必须能确认转让双方
        if event.event_type == ChangeType.EQUITY_TRANSFER:
            if not event.exits or not event.enters:
                issues.append(ReviewIssue(
                    category="data_missing",
                    severity="critical",
                    description=f"{event.date} 股权转让事件缺少退出方或新进方",
                    source_change_date=event.date,
                    suggested_fix="核对企查查原文，手动补充转让双方",
                ))

        # 规则4：资本变更必须能解析变更前后金额
        if event.event_type in (ChangeType.CAPITAL_CHANGE, ChangeType.CAPITAL_INCREASE, ChangeType.CAPITAL_DECREASE):
            if not event.capital_before or not event.capital_after:
                issues.append(ReviewIssue(
                    category="data_missing",
                    severity="warning",
                    description=f"{event.date} 注册资本变更未能解析变更前后金额",
                    source_change_date=event.date,
                    suggested_fix="核对企查查原文，手动补充注册资本",
                ))

    return issues


def review_drafts(drafts: List[HistoryDraft]) -> List[ReviewIssue]:
    """对草稿文本进行规则复核"""
    issues = []

    for draft in drafts:
        text = draft.draft_text

        # 规则：草稿中不应出现未证明的断言
        if "召开股东会并作出决议" in text:
            issues.append(ReviewIssue(
                category="fact_inferred",
                severity="critical",
                description=f"{draft.date} 草稿包含'召开股东会并作出决议'，企查查无法证明",
                source_change_date=draft.date,
                suggested_fix="删除该表述，改为'完成工商变更登记'",
            ))

        if "签署了《股权转让协议》" in text or "签署了股权转让协议" in text:
            issues.append(ReviewIssue(
                category="fact_inferred",
                severity="critical",
                description=f"{draft.date} 草稿包含'签署股权转让协议'，企查查无法证明",
                source_change_date=draft.date,
                suggested_fix="删除该表述，待律师补充协议后生成成稿",
            ))

        if "验资报告" in text and draft.event_type == ChangeType.CAPITAL_CHANGE:
            issues.append(ReviewIssue(
                category="fact_inferred",
                severity="warning",
                description=f"{draft.date} 草稿提及验资报告但事件尚未确认为增资",
                source_change_date=draft.date,
                suggested_fix="确认事件性质为增资并补充验资报告编号",
            ))

    return issues


def full_review(events: List[ChangeEvent], drafts: List[HistoryDraft]) -> List[ReviewIssue]:
    """完整复核"""
    return review_events(events) + review_drafts(drafts)
