"""
股东差异分析器

从变更记录文本中提取股东变更信息，输出进出方快照。
重要：不推断转让配对关系，只陈述文本中实际出现的进出信息。
"""

import re
from typing import List, Tuple, Dict
from .models import ShareholderSnapshot


def _clean_text(text: str) -> str:
    """清洗文本"""
    if not text:
        return ""
    text = str(text)
    # 去除企查查页面噪音（截断提示、国别列、串入的其他变更项目名等）
    text = re.sub(r'此维度共计.{0,40}?查询[。.]?', '', text)
    text = re.sub(r'(当前报告中显示|如需更多|官方网站)[^,，;；]*', '', text)
    text = re.sub(r'国别\s*[（(]?\s*地区\s*[）)]?\s*[:：]?\s*中国', '', text)
    text = re.sub(r'章程修正案备案|章程备案', '', text)
    # 主要人员记录串入：「姓名+职务」（如“戴文渊董事”），姓名按2-4个汉字处理
    text = re.sub(r'[\u4e00-\u9fa5]{2,4}(?:法定代表人|执行董事|董事|监事|总经理|经理)', '', text)
    # 页脚与报告标识
    text = re.sub(r'工商公示|企查查科技股份有限公司', '', text)
    text = re.sub(r'联系电话\s*[:：]?\s*[\d\-]+', '', text)
    # 括号内职务：（董事）（执行事务合伙人）等
    text = re.sub(r'[（(][^（）()]{0,12}(?:董事|监事|经理|合伙人|法定代表人)[）)]', '', text)
    # 单位与变动注释：「(万元)」及其跨行变体「(万 元)」「（持股-5%）」「（-1980）」「（+1466.4）」
    text = re.sub(r'[（(]\s*万\s*元\s*[）)]', '万元', text)
    text = re.sub(r'[（(]\s*持股\s*[+-]?[\d.]*\s*%?\s*[）)]', '', text)
    text = re.sub(r'[（(]\s*[+-]\s*[\d,.]+\s*[）)]', '', text)
    # 去除常见标记符号
    text = text.replace("【退出】", "").replace("【新进】", "")
    text = text.replace("*", "").replace("＊", "")
    text = text.replace("\n", " ")
    return text.strip()


def _extract_ratio_and_amount(text: str) -> Tuple[str, str]:
    """
    从文本中提取持股比例和出资额
    返回 (ratio, amount)
    """
    ratio = ""
    amount = ""

    # 持股比例：xx% 或 持股 xx%
    ratio_match = re.search(r'(?:持股\s*)?(\d+(?:\.\d+)?)\s*%', text)
    if ratio_match:
        ratio = ratio_match.group(1)

    # 出资额：xx 万元 / 认缴 xx 万元
    amount_match = re.search(r'(?:认缴|出资|注册资本)?\s*([\d,]+(?:\.\d+)?)\s*万元', text)
    if not amount_match:
        # 企查查格式：认缴出资额:4200（无单位，默认万元）
        amount_match = re.search(r'出资额[:：]\s*([\d,.]+)', text)
    if amount_match:
        amount = amount_match.group(1)

    return ratio, amount


def _split_shareholder_entries(text: str) -> List[str]:
    """
    把 '张三 30% 李四 20%' 这类文本拆成单个股东条目
    """
    if not text:
        return []

    # 企查查格式条目间无分隔符：
    # "张三持股比例:70%认缴出资额:4200李四持股比例:16.5%..."
    # 在「数值结束后紧跟新姓名」处补分隔符（同一条目内的字段标签后不断开）
    text = re.sub(
        r'((?:持股比例|出资额)[:：]\s*[\d,.]+%?)\s*(?!认缴出资额|持股比例|出资额)(?=[\u4e00-\u9fa5A-Za-z(（])',
        r'\1;',
        text,
    )

    # 先尝试按逗号、顿号、分号分割
    parts = re.split(r'[,，;；、]', text)
    entries = []
    for part in parts:
        part = part.strip()
        if part:
            entries.append(part)
    return entries


def parse_shareholder_change(before: str, after: str) -> Tuple[List[ShareholderSnapshot], List[ShareholderSnapshot]]:
    """
    解析变更前后文本，输出退出方和新进方列表

    重要：
    - 如果同一人同时出现在 before 和 after 中，仅比例变化，不算退出也不算新进
    - 只在 after 中出现的是新进
    - 只在 before 中出现的是退出

    Returns:
        (exits, enters)
    """
    before_clean = _clean_text(before)
    after_clean = _clean_text(after)

    before_snaps = _parse_entries(before_clean, change_type="退出")
    after_snaps = _parse_entries(after_clean, change_type="新进")

    before_names = {s.name for s in before_snaps}
    after_names = {s.name for s in after_snaps}

    # 真正的退出：在 before 中但不在 after 中
    exits = [s for s in before_snaps if s.name not in after_names]
    # 真正的新进：在 after 中但不在 before 中
    enters = [s for s in after_snaps if s.name not in before_names]

    return exits, enters


# 条目级噪音词：企查查报告中混入的非股东内容（其他变更项目、页面提示）
_NOISE_RE = re.compile(
    r'此维度|共计|当前报告|如需更多|登录|官方网站|查询|章程|备案|国别|'
    r'主要人员|变更记录|董事|监事|经理|执行事务'
)


def _parse_entries(text: str, change_type: str) -> List[ShareholderSnapshot]:
    """解析股东条目"""
    entries = _split_shareholder_entries(text)
    snapshots = []

    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        # 去掉常见前缀
        entry = re.sub(r'^(股东|投资人|发起人)[：:：]?\s*', '', entry)

        # 提取名称：取文本中第一个不是数字、%、万元、持股等的片段
        name = _extract_name(entry)
        # 名称至少含一个汉字、长度≥2、不含噪音词
        if (not name or len(name) < 2
                or not re.search(r'[\u4e00-\u9fa5]', name)
                or _NOISE_RE.search(name)):
            continue

        ratio, amount = _extract_ratio_and_amount(entry)

        snapshots.append(ShareholderSnapshot(
            name=name,
            amount=amount,
            ratio=ratio,
            capital=amount,
            change_type=change_type,
        ))

    return snapshots


def _extract_name(entry: str) -> str:
    """从股东条目中提取名称"""
    # 先去掉企查查字段标签（长词优先，避免"出资额"被拆成"出资"+"额"）
    cleaned = re.sub(r'(?:认缴出资额|持股比例|出资额|出资比例)\s*[:：]?', '', entry)
    # 移除数字、百分比、金额单位等
    cleaned = re.sub(r'\d+(?:\.\d+)?\s*%', '', cleaned)
    cleaned = re.sub(r'[\d,]+(?:\.\d+)?\s*万元', '', cleaned)
    cleaned = re.sub(r'(?:持股|认缴|出资|比例|注册资本|股权)', '', cleaned)
    # 移除残留数字与符号
    cleaned = re.sub(r'[\d,.]+', '', cleaned)
    cleaned = cleaned.replace("万元", "")
    cleaned = cleaned.replace("（", "").replace("）", "")
    cleaned = cleaned.replace("(", "").replace(")", "")
    cleaned = cleaned.replace(":", "").replace("：", "")
    # 去除混入的职务后缀（如相邻记录串入的「戴文渊董事」）
    cleaned = re.sub(r'(法定代表人|董事|监事|经理)$', '', cleaned)
    # 去除跨行拆分残留的前缀「元」（如「(万 元)卢香」→「元卢香」）
    cleaned = re.sub(r'^(万元|元)', '', cleaned)
    cleaned = cleaned.strip()

    # 取剩余文本中最长的非空片段作为名称
    parts = [p.strip() for p in re.split(r'[\s,，;；、]+', cleaned) if p.strip()]
    if not parts:
        return ""

    # 选择长度在 2-50 之间的最长片段
    candidates = [p for p in parts if 2 <= len(p) <= 50]
    if candidates:
        return max(candidates, key=len)
    return ""


def _dedup_snapshots(snapshots: List[ShareholderSnapshot]) -> List[ShareholderSnapshot]:
    """按名称去重，保留第一个"""
    seen = set()
    result = []
    for s in snapshots:
        key = s.name
        if key and key not in seen:
            seen.add(key)
            result.append(s)
    return result
