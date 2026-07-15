"""
变更记录解析器

只负责把 QCC 原始变更记录解析为可追溯的 ChangeFact。
不判断交易性质，不做股东配对。
"""

import re
from typing import List, Dict
from .models import ChangeFact, EvidenceRef


def normalize_date(date_str: str) -> str:
    """统一日期格式为 YYYY-MM-DD"""
    if not date_str:
        return ""
    s = str(date_str).strip()
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s


def format_date(date_str: str) -> str:
    """格式化为 'YYYY年M月D日'"""
    raw = normalize_date(date_str)
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', raw)
    if m:
        return f"{m.group(1)}年{int(m.group(2))}月{int(m.group(3))}日"
    return date_str


def parse_change_records(raw_changes: List[Dict]) -> List[ChangeFact]:
    """
    解析原始变更记录为 ChangeFact 列表

    Args:
        raw_changes: 从 extractor 得到的 change_history 列表
    """
    facts = []
    for idx, rc in enumerate(raw_changes):
        raw_date = normalize_date(rc.get("date", ""))
        display_date = format_date(rc.get("date", ""))
        project = str(rc.get("project", "")).strip()
        before = str(rc.get("before", "")).strip()
        after = str(rc.get("after", "")).strip()

        warnings = []
        if not raw_date:
            warnings.append("变更日期为空")
        if not project:
            warnings.append("变更项目为空")
        if not before and not after:
            warnings.append("变更前后内容均为空，可能为解析异常")

        evidence = EvidenceRef(
            seq=str(rc.get("seq", idx + 1)),
            raw_date=raw_date,
            project=project,
            before=before,
            after=after,
            source=rc.get("source", "工商公示"),
            page_nos=rc.get("page_nos", []) or [],
        )

        fact = ChangeFact(
            date=display_date,
            raw_date=raw_date,
            project=project,
            before=before,
            after=after,
            evidence=evidence,
            confidence=0.9 if not warnings else 0.6,
            warnings=warnings,
        )
        facts.append(fact)

    return facts
