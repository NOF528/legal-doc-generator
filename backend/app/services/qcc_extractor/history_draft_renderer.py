"""
历史沿革草稿渲染器

只根据已确认字段生成 QCC 事实草稿，不编造任何未证明内容。
"""

from typing import List
from .models import ChangeEvent, HistoryDraft, ChangeType, ClassificationLevel


def _fmt_capital(val: str) -> str:
    return val if val else "【**】"


def _fmt_name(val: str) -> str:
    return val if val else "【**】"


def render_qcc_drafts(events: List[ChangeEvent], company_name: str = "公司") -> List[HistoryDraft]:
    """
    把事件列表渲染为历史沿革草稿段落
    """
    drafts = []
    for event in events:
        draft = _render_event(event, company_name)
        drafts.append(draft)
    return drafts


def _render_event(event: ChangeEvent, company_name: str) -> HistoryDraft:
    """渲染单个事件"""
    if event.event_type == ChangeType.EQUITY_TRANSFER:
        return _render_equity_transfer(event, company_name)
    elif event.event_type == ChangeType.SHAREHOLDER_CHANGE:
        return _render_shareholder_change(event, company_name)
    elif event.event_type == ChangeType.CAPITAL_CHANGE:
        return _render_capital_change(event, company_name)
    elif event.event_type == ChangeType.CAPITAL_INCREASE:
        return _render_capital_increase(event, company_name)
    elif event.event_type == ChangeType.CAPITAL_DECREASE:
        return _render_capital_decrease(event, company_name)
    else:
        return _render_other_change(event, company_name)


def _render_equity_transfer(event: ChangeEvent, company_name: str) -> HistoryDraft:
    """渲染股权转让草稿（保守）"""
    date = event.date

    exit_names = "、".join([s.name for s in event.exits if s.name]) or "【**】"
    enter_names = "、".join([s.name for s in event.enters if s.name]) or "【**】"

    lines = [
        f"根据企查查企业信用报告，{date}，{company_name}完成投资人变更登记。",
        f"本次登记涉及退出方：{exit_names}；新进方：{enter_names}。",
    ]

    # 如果有比例/金额，列出
    details = []
    for s in event.exits:
        if s.ratio or s.amount:
            details.append(f"{s.name}原持股{_fmt_name(s.ratio)}%（对应注册资本{_fmt_name(s.amount)}万元）")
    for s in event.enters:
        if s.ratio or s.amount:
            details.append(f"{s.name}持股{_fmt_name(s.ratio)}%（对应注册资本{_fmt_name(s.amount)}万元）")

    if details:
        lines.append("涉及股权情况：" + "；".join(details) + "。")

    lines.append(f"上述变更于{date}完成工商变更登记。")

    text = "\n".join(lines)

    return HistoryDraft(
        date=date,
        sequence_title=f"{date} 股权转让（待确认）",
        draft_text=text,
        event_type=ChangeType.EQUITY_TRANSFER,
        classification_level=event.classification_level,
        missing_fields=event.missing_fields,
        warnings=event.warnings + ["转让双方配对、转让对价、协议签署及股东会决议情况需律师根据实际法律文件补充。"],
        evidence=event.evidence,
    )


def _render_shareholder_change(event: ChangeEvent, company_name: str) -> HistoryDraft:
    """渲染股东变更草稿（无法确认转让关系）"""
    date = event.date
    exit_names = "、".join([s.name for s in event.exits if s.name]) or "【**】"
    enter_names = "、".join([s.name for s in event.enters if s.name]) or "【**】"

    lines = [
        f"根据企查查企业信用报告，{date}，{company_name}完成投资人变更登记。",
    ]

    if event.exits and event.enters:
        lines.append(f"登记显示退出方：{exit_names}；新进方：{enter_names}。")
    elif event.exits:
        lines.append(f"登记显示退出方：{exit_names}。")
    elif event.enters:
        lines.append(f"登记显示新进方：{enter_names}。")
    else:
        lines.append("登记显示投资人发生变更，但具体股东信息未能从报告中识别。")

    lines.append(f"上述变更于{date}完成工商变更登记。")
    lines.append("【注：本次股东结构变更的具体交易性质（股权转让/增资/减资/其他）及交易对价，需律师根据公司章程、股东会决议及股权转让协议等补充材料确认。】")

    return HistoryDraft(
        date=date,
        sequence_title=f"{date} 股东结构变更（待确认）",
        draft_text="\n".join(lines),
        event_type=ChangeType.SHAREHOLDER_CHANGE,
        classification_level=ClassificationLevel.UNDETERMINED,
        missing_fields=event.missing_fields + ["变更交易性质", "转让双方配对", "交易对价"],
        warnings=event.warnings,
        evidence=event.evidence,
    )


def _render_capital_change(event: ChangeEvent, company_name: str) -> HistoryDraft:
    """渲染注册资本变更草稿（保守，不区分增/减）"""
    date = event.date
    before = _fmt_capital(event.capital_before)
    after = _fmt_capital(event.capital_after)

    lines = [
        f"根据企查查企业信用报告，{date}，{company_name}完成注册资本变更登记。",
        f"注册资本由人民币{before}变更为人民币{after}。",
        f"上述变更于{date}完成工商变更登记。",
        "【注：本次注册资本变更的具体性质（增资/减资）、出资方/减资方、股东会决议、验资/公告程序等，需律师根据实际法律文件补充确认。】",
    ]

    return HistoryDraft(
        date=date,
        sequence_title=f"{date} 注册资本变更（待确认）",
        draft_text="\n".join(lines),
        event_type=ChangeType.CAPITAL_CHANGE,
        classification_level=event.classification_level,
        missing_fields=event.missing_fields,
        warnings=event.warnings,
        evidence=event.evidence,
    )


def _render_capital_increase(event: ChangeEvent, company_name: str) -> HistoryDraft:
    """渲染增资草稿（仅在有明确证据时使用）"""
    return _render_capital_change(event, company_name)


def _render_capital_decrease(event: ChangeEvent, company_name: str) -> HistoryDraft:
    """渲染减资草稿（仅在有明确证据时使用）"""
    return _render_capital_change(event, company_name)


def _render_other_change(event: ChangeEvent, company_name: str) -> HistoryDraft:
    """渲染其他变更草稿"""
    date = event.date
    project = event.event_type.value
    before = event.known_facts.get("变更前", "")
    after = event.known_facts.get("变更后", "")

    lines = [f"根据企查查企业信用报告，{date}，{company_name}完成{project}登记。"]
    if before and after:
        lines.append(f"变更前：{before}；变更后：{after}。")
    elif after:
        lines.append(f"变更后：{after}。")

    lines.append(f"上述变更于{date}完成工商变更登记。")

    return HistoryDraft(
        date=date,
        sequence_title=f"{date} {project}",
        draft_text="\n".join(lines),
        event_type=event.event_type,
        classification_level=event.classification_level,
        missing_fields=[],
        warnings=[],
        evidence=event.evidence,
    )


def combine_drafts(drafts: List[HistoryDraft]) -> str:
    """合并草稿为完整历史沿革文本"""
    sections = []
    for d in drafts:
        sections.append(f"【{d.sequence_title}】")
        sections.append(d.draft_text)
        if d.missing_fields:
            sections.append(f"【待补充字段】{'; '.join(d.missing_fields)}")
        sections.append("")
    return "\n".join(sections)
