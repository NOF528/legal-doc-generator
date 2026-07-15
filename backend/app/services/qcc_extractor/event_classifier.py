"""
事件分类器

把 ChangeFact 归一化为 ChangeEvent，分类规则保守：
- 注册资本上升/下降 → 先只认定"注册资本变更"
- 投资人变更 → 先只认定"股东变更"
- 有明确转让双方证据时 → 才升级为"股权转让"
- 同日多项变更 → 拆分为多个事件

绝不在此层生成律师文本。
"""

import re
from typing import List, Dict, Tuple
from collections import defaultdict
from .models import ChangeFact, ChangeEvent, ChangeType, ClassificationLevel, ShareholderSnapshot
from .shareholder_diff import parse_shareholder_change


def _extract_capital_number(text: str) -> float:
    """从文本中提取资本数字（万元）"""
    if not text:
        return 0.0
    text = str(text).replace(",", "").replace("，", "")
    match = re.search(r'(\d+(?:\.\d+)?)\s*万元', text)
    if match:
        return float(match.group(1))
    numbers = re.findall(r'\d+(?:\.\d+)?', text)
    if numbers:
        return float(numbers[0])
    return 0.0


def _format_capital(text: str) -> str:
    """格式化资本显示"""
    num = _extract_capital_number(text)
    if num > 0:
        return f"{num:,.4f}".rstrip("0").rstrip(".") + "万元"
    return ""


def _is_capital_project(project: str) -> bool:
    """是否是注册资本相关项目"""
    return "注册资本" in project or "注册资金" in project


def _is_shareholder_project(project: str) -> bool:
    """是否是投资人/股东相关项目"""
    return any(k in project for k in ["投资人", "股东", "发起人", "股权"])


def classify_events(facts: List[ChangeFact], company_name: str = "公司") -> List[ChangeEvent]:
    """
    主入口：把事实列表分类为事件列表
    """
    # 按日期分组
    grouped = defaultdict(list)
    for fact in facts:
        grouped[fact.raw_date].append(fact)

    events = []
    for raw_date in sorted(grouped.keys()):
        date_facts = grouped[raw_date]
        display_date = date_facts[0].date if date_facts else ""

        # 分离资本类事实和股东类事实
        capital_facts = [f for f in date_facts if _is_capital_project(f.project)]
        shareholder_facts = [f for f in date_facts if _is_shareholder_project(f.project)]
        other_facts = [f for f in date_facts if f not in capital_facts and f not in shareholder_facts]

        # 1. 处理资本变更事件
        if capital_facts:
            event = _build_capital_event(display_date, raw_date, capital_facts, company_name)
            events.append(event)

        # 2. 处理股东变更事件（每个事实可能产生一个事件，避免强行合并）
        for fact in shareholder_facts:
            event = _build_shareholder_event(display_date, raw_date, [fact], company_name)
            events.append(event)

        # 3. 处理其他变更事件
        for fact in other_facts:
            event = _build_other_event(display_date, raw_date, fact)
            events.append(event)

    return events


def _build_capital_event(display_date: str, raw_date: str, facts: List[ChangeFact], company_name: str) -> ChangeEvent:
    """构建注册资本变更事件"""
    before_text = ""
    after_text = ""

    for f in facts:
        if f.before:
            before_text = f.before
        if f.after:
            after_text = f.after

    before_num = _extract_capital_number(before_text)
    after_num = _extract_capital_number(after_text)

    capital_before = _format_capital(before_text) if before_num > 0 else ""
    capital_after = _format_capital(after_text) if after_num > 0 else ""

    # 判断是增加还是减少，但输出保守标签
    if after_num > before_num > 0:
        event_type = ChangeType.CAPITAL_CHANGE
        inferred_type = ChangeType.CAPITAL_INCREASE
        level = ClassificationLevel.INFERRED
    elif 0 < after_num < before_num:
        event_type = ChangeType.CAPITAL_CHANGE
        inferred_type = ChangeType.CAPITAL_DECREASE
        level = ClassificationLevel.INFERRED
    else:
        event_type = ChangeType.CAPITAL_CHANGE
        inferred_type = ChangeType.CAPITAL_CHANGE
        level = ClassificationLevel.UNDETERMINED

    missing_fields = ["股东会决议日期", "章程修订情况"]
    if inferred_type == ChangeType.CAPITAL_INCREASE:
        missing_fields.extend(["增资认购方", "认购金额", "出资期限", "验资报告编号"])
    elif inferred_type == ChangeType.CAPITAL_DECREASE:
        missing_fields.extend(["减资决议日期", "减资公告刊登媒体", "公告日期", "债权人申报情况"])

    warnings = [f"根据工商公示信息，{company_name}于{display_date}完成注册资本变更登记。"
                f"变更性质（增/减）为系统推断，需律师根据股东会决议及验资/公告材料确认。"]

    return ChangeEvent(
        date=display_date,
        raw_date=raw_date,
        event_type=event_type,
        classification_level=level,
        facts=facts,
        evidence=[f.evidence for f in facts],
        known_facts={
            "登记日期": display_date,
            "变更前注册资本": capital_before,
            "变更后注册资本": capital_after,
        },
        missing_fields=missing_fields,
        warnings=warnings,
        capital_before=capital_before,
        capital_after=capital_after,
    )


def _build_shareholder_event(display_date: str, raw_date: str, facts: List[ChangeFact], company_name: str) -> ChangeEvent:
    """构建股东变更事件"""
    exits: List[ShareholderSnapshot] = []
    enters: List[ShareholderSnapshot] = []

    for f in facts:
        e, n = parse_shareholder_change(f.before, f.after)
        exits.extend(e)
        enters.extend(n)

    # 默认保守分类为股东变更
    event_type = ChangeType.SHAREHOLDER_CHANGE
    level = ClassificationLevel.CONFIRMED
    missing_fields = ["股东会决议日期"]
    warnings = []

    # 如果能同时识别到退出方和新进方，升级为股权转让（inferred）
    if exits and enters:
        event_type = ChangeType.EQUITY_TRANSFER
        level = ClassificationLevel.INFERRED
        missing_fields.extend(["转让对价", "股权转让协议签署日期", "优先购买权情况"])
        warnings.append(
            f"系统识别到{display_date}存在投资人退出和新进，"
            f"初步推断为股权转让，但转让双方配对、对价、协议签署情况等需律师根据"
            f"股权转让协议及股东会决议确认。"
        )
    elif exits or enters:
        warnings.append(
            f"根据工商公示信息，{company_name}于{display_date}发生投资人变更。"
            f"由于变更记录仅显示部分股东信息，转让关系、对价等需律师补充核实。"
        )
    else:
        level = ClassificationLevel.UNDETERMINED
        warnings.append(
            f"根据工商公示信息，{company_name}于{display_date}发生投资人变更登记，"
            f"但系统未能从文本中识别具体股东信息。"
        )

    return ChangeEvent(
        date=display_date,
        raw_date=raw_date,
        event_type=event_type,
        classification_level=level,
        facts=facts,
        evidence=[f.evidence for f in facts],
        known_facts={
            "登记日期": display_date,
            "退出方": [s.name for s in exits],
            "新进方": [s.name for s in enters],
        },
        missing_fields=missing_fields,
        warnings=warnings,
        exits=exits,
        enters=enters,
    )


def _build_other_event(display_date: str, raw_date: str, fact: ChangeFact) -> ChangeEvent:
    """构建其他类型事件"""
    project = fact.project

    if "名称" in project:
        event_type = ChangeType.NAME_CHANGE
    elif "法定代表人" in project or "法人" in project:
        event_type = ChangeType.LEGAL_REP_CHANGE
    elif "地址" in project or "住所" in project:
        event_type = ChangeType.ADDRESS_CHANGE
    elif "经营范围" in project:
        event_type = ChangeType.SCOPE_CHANGE
    else:
        event_type = ChangeType.OTHER

    return ChangeEvent(
        date=display_date,
        raw_date=raw_date,
        event_type=event_type,
        classification_level=ClassificationLevel.CONFIRMED,
        facts=[fact],
        evidence=[fact.evidence],
        known_facts={
            "登记日期": display_date,
            "变更项目": project,
            "变更前": fact.before,
            "变更后": fact.after,
        },
        missing_fields=[],
        warnings=[],
    )
