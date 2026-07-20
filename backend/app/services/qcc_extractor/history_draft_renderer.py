"""
历史沿革草稿渲染器

按素材模板风格输出三种变更：
- 股权转让
- 增资
- 减资

规则：
- 企查查能证明的事实直接写入（登记日期、变更前后注册资本、股东名称）
- 企查查不能证明的字段用【**】占位，并列入 missing_fields
- 绝不编造决议日期、对价、协议签署、验资报告等内容
"""

from typing import List
from .models import ChangeEvent, HistoryDraft, ChangeType


PLACEHOLDER = "【**】"
DATE_PLACEHOLDER = "【**年**月**日】"


def render_qcc_drafts(events: List[ChangeEvent], company_name: str = "公司") -> List[HistoryDraft]:
    """把事件列表渲染为历史沿革草稿段落"""
    drafts = []
    for event in events:
        if event.event_type == ChangeType.EQUITY_TRANSFER:
            drafts.append(_render_equity_transfer(event, company_name))
        elif event.event_type == ChangeType.CAPITAL_INCREASE:
            drafts.append(_render_capital_increase(event, company_name))
        elif event.event_type == ChangeType.CAPITAL_DECREASE:
            drafts.append(_render_capital_decrease(event, company_name))
        # 其他类型不进入历史沿革
    return drafts


def _render_equity_transfer(event: ChangeEvent, company_name: str) -> HistoryDraft:
    """股权转让（按素材模板表述）"""
    registration_date = event.date  # 企查查记录的是工商变更登记日期
    missing = []

    # 决议日期无法从企查查证明
    meeting_date = DATE_PLACEHOLDER
    missing.append("股东会决议日期")

    # 转让语句：企查查无法证明转让双方的具体配对关系，不做配对组合。
    # 决议段按模板给出占位明细，另附一段说明本次变更实际涉及的退出方/新进方（企查查可证明）。
    lines = [
        f"{meeting_date}，公司召开股东会并作出决议，同意以下股权转让事项：",
        f"股东{PLACEHOLDER}将其持有的公司{PLACEHOLDER}%的股权"
        f"（对应注册资本人民币{PLACEHOLDER}万元）以人民币{PLACEHOLDER}万元的对价转让给{PLACEHOLDER}；",
        "（请根据股东会决议及《股权转让协议》按上述格式逐笔补充）",
        "",
    ]
    missing.append("转让对价")
    missing.append("转让双方配对及各笔转让比例")

    # 企查查可证明的事实：本次变更涉及的转让方（变更前→变更后持股）与受让方（变更后持股）
    transferors = event.known_facts.get("转让方", [])
    transferees = event.known_facts.get("受让方", [])

    full_name = _name_fixer(event)

    transfer_parts = []
    for s in event.exits:
        name = full_name(s.name)
        if s.ratio:
            transfer_parts.append(f"{name}（变更前持股{s.ratio}%，变更后不再持股）")
        else:
            transfer_parts.append(f"{name}（变更后不再持股）")
    for t in transferors:
        name = full_name(t["name"])
        if t.get("before") and t.get("after"):
            transfer_parts.append(f"{name}（变更前持股{t['before']}%，变更后持股{t['after']}%）")
        else:
            transfer_parts.append(name)
    if transfer_parts:
        lines.append("本次变更涉及的转让方及其持股变动情况：" + "、".join(transfer_parts) + "。")

    def _describe(s) -> str:
        parts = []
        if s.ratio:
            parts.append(f"持股{s.ratio}%")
        if s.amount:
            parts.append(f"认缴出资额{s.amount}万元")
        return f"{full_name(s.name)}（{'，'.join(parts)}）" if parts else full_name(s.name)

    transferee_parts = [_describe(s) for s in event.enters]
    for t in transferees:
        name = full_name(t["name"])
        if t.get("after"):
            transferee_parts.append(f"{name}（变更后持股{t['after']}%）")
        else:
            transferee_parts.append(name)
    if transferee_parts:
        lines.append("本次变更涉及的受让方及其变更后持股情况：" + "、".join(transferee_parts) + "。")
    lines.append("")

    # 协议签署日期无法证明（一侧名单缺失时用占位符）
    transferor_names = "、".join(dict.fromkeys(
        [full_name(s.name) for s in event.exits] + [full_name(t["name"]) for t in transferors]
    )) or PLACEHOLDER
    transferee_names = "、".join(dict.fromkeys(
        [full_name(s.name) for s in event.enters] + [full_name(t["name"]) for t in transferees]
    )) or PLACEHOLDER
    lines.append(
        f"{DATE_PLACEHOLDER}，{transferor_names}与{transferee_names}"
        f"分别就上述股权转让事项签署了《股权转让协议》。"
    )
    missing.append("股权转让协议签署日期")
    lines.append("")

    # 变更后股权结构表
    lines.append(f"本次股权转让完成后，{company_name}的股权结构如下：")
    lines.append("")
    lines.extend(_build_shareholder_table(event))
    lines.append("")

    # 工商登记日期（企查查可证明）
    lines.append(f"{registration_date}，{company_name}完成了上述股权转让的工商变更登记程序。")

    # 去重 missing
    missing = list(dict.fromkeys(missing + event.missing_fields))

    return HistoryDraft(
        date=registration_date,
        sequence_title=f"{registration_date} 股权转让",
        draft_text="\n".join(lines),
        event_type=ChangeType.EQUITY_TRANSFER,
        classification_level=event.classification_level,
        missing_fields=missing,
        warnings=event.warnings,
        evidence=event.evidence,
    )


def _render_capital_increase(event: ChangeEvent, company_name: str) -> HistoryDraft:
    """增资（按素材模板表述）"""
    registration_date = event.date
    missing = []

    meeting_date = DATE_PLACEHOLDER
    missing.append("股东会决议日期")

    original_capital = event.capital_before or PLACEHOLDER
    new_capital = event.capital_after or PLACEHOLDER

    lines = [
        f"{meeting_date}，公司召开股东会并作出决议："
        f"公司注册资本由人民币{original_capital}变更为人民币{new_capital}。",
    ]

    # 认购方信息：企查查只能看到新进股东，认购金额无法证明
    if event.enters:
        subscribe_statements = []
        for enter_sh in event.enters:
            capital = enter_sh.amount or PLACEHOLDER
            subscribe_statements.append(
                f"同意{enter_sh.name}以人民币{PLACEHOLDER}万元认购公司新增的注册资本人民币{capital}万元"
            )
        lines.append("；".join(subscribe_statements) + "。")
    else:
        lines.append(
            f"同意{PLACEHOLDER}以人民币{PLACEHOLDER}万元认购公司新增的注册资本人民币{PLACEHOLDER}万元。"
        )
    missing.append("增资认购方及认购金额")
    lines.append("")

    # 变更后股权结构表
    lines.append(f"本次增资完成后，{company_name}的股权结构如下：")
    lines.append("")
    lines.extend(_build_shareholder_table(event))
    lines.append("")

    # 工商登记日期
    lines.append(f"{registration_date}，{company_name}完成了上述增资的工商变更登记程序。")

    # 验资报告占位（素材模板为可选段）
    lines.append("")
    lines.append(
        f"{DATE_PLACEHOLDER}，{PLACEHOLDER}出具了《验资报告》（{PLACEHOLDER}），"
        f"截至{DATE_PLACEHOLDER}，公司已收到{PLACEHOLDER}缴纳的新增注册资本人民币{PLACEHOLDER}万元，"
        f"计入资本公积{PLACEHOLDER}万元。"
    )
    missing.extend(["验资报告编号", "验资机构", "出资缴付截止日期", "计入资本公积金额"])

    missing = list(dict.fromkeys(missing + event.missing_fields))

    return HistoryDraft(
        date=registration_date,
        sequence_title=f"{registration_date} 增资",
        draft_text="\n".join(lines),
        event_type=ChangeType.CAPITAL_INCREASE,
        classification_level=event.classification_level,
        missing_fields=missing,
        warnings=event.warnings,
        evidence=event.evidence,
    )


def _render_capital_decrease(event: ChangeEvent, company_name: str) -> HistoryDraft:
    """减资（按素材模板表述）"""
    registration_date = event.date
    missing = []

    meeting_date = DATE_PLACEHOLDER
    missing.append("股东会决议日期")

    original_capital = event.capital_before or PLACEHOLDER
    new_capital = event.capital_after or PLACEHOLDER

    lines = [
        f"{meeting_date}，公司召开股东会并作出决议："
        f"同意将原注册资本{original_capital}变更为{new_capital}，并对公司章程进行相应修改。"
        f"{company_name}本次注册资本{original_capital}变更为{new_capital}由全体股东按照同比例减资。",
        "",
        # 减资公告段（素材模板必填，但企查查无法证明）
        f"{DATE_PLACEHOLDER}，公司就上述减资事宜于{PLACEHOLDER}刊登了减资公告："
        f"经股东会作出决议，拟将公司注册资本由人民币{original_capital}减至人民币{new_capital}。"
        f"根据《中华人民共和国公司法》等相关法律、法规的规定，公司特此通知债权人，"
        f"请公司债权人自本公告见报之日起{PLACEHOLDER}日内到本公司申报债权。"
        f"本公司承诺对原注册资本内的债务承担清偿责任，股东承担连带责任。",
        "",
    ]
    missing.extend(["减资公告刊登媒体", "减资公告日期", "债权人申报期限"])

    # 变更后股权结构表
    lines.append(f"本次减资完成后，{company_name}的股权结构如下：")
    lines.append("")
    lines.extend(_build_shareholder_table(event))
    lines.append("")

    # 工商登记日期
    lines.append(f"{registration_date}，{company_name}完成了上述减资事宜的工商变更登记程序。")

    missing = list(dict.fromkeys(missing + event.missing_fields))

    return HistoryDraft(
        date=registration_date,
        sequence_title=f"{registration_date} 减资",
        draft_text="\n".join(lines),
        event_type=ChangeType.CAPITAL_DECREASE,
        classification_level=event.classification_level,
        missing_fields=missing,
        warnings=event.warnings,
        evidence=event.evidence,
    )


def _norm_key(name: str) -> str:
    import re as _re
    return _re.sub(r'[\s;；、，,]+', '', name or '').replace('（', '(').replace('）', ')').rstrip('*＊')


def _name_fixer(event: ChangeEvent):
    """返回一个函数：把跨页截断的股东名补全为变更后名册中的全名"""
    roster_names = [s.get("name", "") for s in event.known_facts.get("shareholders_after", [])]
    keys = {_norm_key(n): n for n in roster_names if n}

    def fix(name: str) -> str:
        if not name:
            return name
        k = _norm_key(name)
        if k in keys:
            return keys[k]
        for rk, full in keys.items():
            if rk and (rk.startswith(k) or k.startswith(rk)):
                return full
        return name

    return fix


def _build_shareholder_table(event: ChangeEvent) -> List[str]:
    """
    构建变更后股权结构表。

    优先使用 equity_structure 计算的完整变更后名册（2.2 倒推 + 2.7 直读），
    缺失字段用【**】占位；无完整名册时退回只列新进方 + 其余股东占位。
    """
    def _val(v) -> str:
        return str(v) if v not in (None, "") else PLACEHOLDER

    lines = [
        "| 序号 | 股东名称/姓名 | 出资额（万元） | 出资比例 |",
        "|:---:|:---:|:---:|:---:|",
    ]

    shareholders = event.known_facts.get("shareholders_after", [])
    if shareholders:
        # 完整变更后名册（逻辑一倒推 + 逻辑二直读计算得出）
        for i, s in enumerate(shareholders, 1):
            lines.append(f"| {i} | {_val(s.get('name'))} | {_val(s.get('amount'))} | {_val(s.get('ratio'))}% |")
    else:
        # 新进方的持股为变更后状态，可列出；退出方变更后不再持股，不列入
        idx = 1
        for s in event.enters:
            ratio = s.ratio or PLACEHOLDER
            amount = s.amount or PLACEHOLDER
            lines.append(f"| {idx} | {s.name} | {amount} | {ratio}% |")
            idx += 1
        lines.append(f"| {idx} | 其余股东{PLACEHOLDER} | {PLACEHOLDER} | {PLACEHOLDER}% |")

    total = event.capital_after or PLACEHOLDER
    lines.append(f"| 合计 | - | {total} | 100.0000% |")

    return lines


def combine_drafts(drafts: List[HistoryDraft]) -> str:
    """合并草稿为完整历史沿革文本（每段前加标题，方便 Word 分节）"""
    sections = []
    for d in drafts:
        sections.append(f"【{d.sequence_title}】")
        sections.append("")
        sections.append(d.draft_text)
        sections.append("")
    return "\n".join(sections)
