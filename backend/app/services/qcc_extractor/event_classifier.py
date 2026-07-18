"""
事件分类器

历史沿革只包含三种变更：
- 股权转让（投资人变更且能识别进出方）
- 增资（注册资本增加）
- 减资（注册资本减少）

其他工商变更（名称、地址、法定代表人、经营范围等）不计入历史沿革。
"""

import re
from typing import List
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
    """格式化资本显示，如 84,059.1737万元"""
    if not text:
        return ""
    text = str(text)
    match = re.search(r'([\d,]+(?:\.\d+)?)\s*万元', text)
    if match:
        return match.group(1) + "万元"
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
    主入口：把事实列表分类为事件列表。
    只输出三种历史沿革事件：股权转让 / 增资 / 减资。
    按时间正序排列（先发生的在前）。
    """
    # 按日期分组
    grouped = defaultdict(list)
    for fact in facts:
        if fact.raw_date:
            grouped[fact.raw_date].append(fact)

    events = []
    for raw_date in sorted(grouped.keys()):
        date_facts = grouped[raw_date]
        display_date = date_facts[0].date if date_facts else ""

        capital_facts = [f for f in date_facts if _is_capital_project(f.project)]
        shareholder_facts = [f for f in date_facts if _is_shareholder_project(f.project)]
        # 其他项目（名称/地址/法代/经营范围等）直接忽略，不计入历史沿革

        # 1. 注册资本变更 → 增资 / 减资
        if capital_facts:
            event = _build_capital_event(display_date, raw_date, capital_facts)
            if event:
                events.append(event)

        # 2. 投资人变更 → 股权转让
        # 同一天的多条投资人记录合并为一个事件（一次交易可能在企查查里显示为多行）
        if shareholder_facts:
            event = _build_shareholder_event(display_date, raw_date, shareholder_facts)
            if event:
                events.append(event)

    return events


def _build_capital_event(display_date: str, raw_date: str, facts: List[ChangeFact]) -> ChangeEvent | None:
    """构建增资或减资事件。无法判断方向的返回 None。"""
    before_text = ""
    after_text = ""
    for f in facts:
        if f.before:
            before_text = f.before
        if f.after:
            after_text = f.after

    before_num = _extract_capital_number(before_text)
    after_num = _extract_capital_number(after_text)

    if before_num <= 0 or after_num <= 0 or before_num == after_num:
        return None

    capital_before = _format_capital(before_text)
    capital_after = _format_capital(after_text)

    if after_num > before_num:
        event_type = ChangeType.CAPITAL_INCREASE
        missing_fields = ["股东会决议日期", "增资认购方", "认购金额", "出资期限", "验资报告编号"]
        warnings = ["增资的认购方、认购金额、出资期限及验资情况，需根据股东会决议及验资报告补充。"]
    else:
        event_type = ChangeType.CAPITAL_DECREASE
        missing_fields = ["股东会决议日期", "减资公告刊登媒体", "公告日期", "债权人申报情况"]
        warnings = ["减资的股东会决议、公告刊登及债权人申报程序，需根据实际法律文件补充。"]

    return ChangeEvent(
        date=display_date,
        raw_date=raw_date,
        event_type=event_type,
        classification_level=ClassificationLevel.CONFIRMED,
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


def _build_shareholder_event(display_date: str, raw_date: str, facts: List[ChangeFact]) -> ChangeEvent | None:
    """构建股权转让事件。能识别进出方才输出，否则返回 None。"""
    exits: List[ShareholderSnapshot] = []
    enters: List[ShareholderSnapshot] = []

    for f in facts:
        e, n = parse_shareholder_change(f.before, f.after)
        exits.extend(e)
        enters.extend(n)

    # 去重
    exits = _dedup(exits)
    enters = _dedup(enters)

    # 至少识别到退出方或新进方之一才输出；另一侧缺失时由律师补充。
    # （企查查变更记录常因分页/错位导致一侧信息缺失，宁可占位提示也不丢弃真实事件）
    if not exits and not enters:
        return None

    missing_fields = [
        "股东会决议日期",
        "转让对价",
        "股权转让协议签署日期",
        "优先购买权情况",
        "变更后完整股权结构",
    ]
    if not enters:
        missing_fields.append("新进方/受让方信息（企查查记录未完整显示）")
    if not exits:
        missing_fields.append("退出方/转让方信息（企查查记录未完整显示）")
    warnings = ["转让双方的具体配对、转让对价及协议签署情况，需根据股东会决议及股权转让协议确认。"]

    return ChangeEvent(
        date=display_date,
        raw_date=raw_date,
        event_type=ChangeType.EQUITY_TRANSFER,
        classification_level=ClassificationLevel.INFERRED,
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


def _dedup(snapshots: List[ShareholderSnapshot]) -> List[ShareholderSnapshot]:
    """按名称去重"""
    seen = set()
    result = []
    for s in snapshots:
        if s.name and s.name not in seen:
            seen.add(s.name)
            result.append(s)
    return result
