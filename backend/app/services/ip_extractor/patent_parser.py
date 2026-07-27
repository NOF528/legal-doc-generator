"""
专利表解析（8.2 专利信息）

表格列：序号 发明名称 专利类型 法律状态 申请号 申请日期 公开(公告)号 公开(公告)日期
行形态：
  16行情消息的延时测量方法、装置、设备和存储介质
  发明授权 授权CN202410435379.2
  2024-04-11CN118041831B
  2024-06-18

解析策略：以「专利类型 + 法律状态 + CN申请号 + 申请日期」为锚点，
名称取锚点前的文本（序号之后的部分，允许跨行拼接）。
跨页断裂的申请号（如 "CN2024106" 后半截在下一页）不匹配锚点，自然跳过。
只保留法律状态为「授权」的行；类型归一：发明公布/发明授权 → 发明。
"""
import re
from typing import Dict, List

_HEADER = "序号 发明名称 专利类型 法律状态"

# 类型 + 法律状态 + CN申请号 + 申请日期
# 申请号：CN + 9~13 位数字 + . + 数字或X（如 CN202410673406.X）
_ANCHOR = re.compile(
    r'(发明公布|发明授权|实用新型|外观设计)\s*'
    r'([^\s，,。:：]{1,12}?)\s*'
    r'(CN\d{9,13}[.．][\dX])\s*'
    r'(\d{4}-\d{2}-\d{2})'
)

# 行首「序号+名称开头」定位：数字紧跟名称字符（取最后一次出现，
# 丢弃跨页断裂行残留的碎片，如 "80617.6 46A"）
_ROW_START = re.compile(r'(?:^|\n)\s*(\d{1,4})\s*(?=[一-龥A-Za-z(（])')

_TYPE_MAP = {
    "发明公布": "发明",
    "发明授权": "发明",
    "实用新型": "实用新型",
    "外观设计": "外观设计",
}

_FOOTER_RE = re.compile(r'联系电话：[\d\-]+|企查查科技股份有限公司\s*\d*|工商公示')


def parse_patents(block: str) -> List[Dict]:
    """
    从 8.2 内容块解析专利行，只保留法律状态为「授权」的。

    Returns:
        [{seq, patent_type, legal_status, app_no, app_date}]，序号已重排
    """
    if not block or "暂未查询到" in block:
        return []
    idx = block.find(_HEADER)
    if idx < 0:
        return []
    # 表头行拆成两段（「序号 发明名称 专利类型 法律状态」+「申请号 申请日期 公开号…」），
    # 以「申请日期」为界取数据区
    end_idx = block.find("申请日期", idx)
    if end_idx < 0:
        return []
    text = _FOOTER_RE.sub("", block[end_idx + len("申请日期"):])

    kept: List[Dict] = []
    seen = set()
    prev_end = 0
    for m in _ANCHOR.finditer(text):
        raw_type, status, app_no, app_date = m.groups()
        # 名称 = 上一锚点结束 → 本锚点开始（序号 + 名称，可能跨行）
        region = text[prev_end:m.start()]
        prev_end = m.end()
        name = _extract_name(region)
        if status != "授权":
            continue
        patent_type = _TYPE_MAP.get(raw_type)
        if patent_type is None:
            continue
        if app_no in seen:
            continue
        seen.add(app_no)
        kept.append({
            "name": name,
            "patent_type": patent_type,
            "legal_status": status,
            "app_no": app_no,
            "app_date": app_date,
        })

    for i, r in enumerate(kept, 1):
        r["seq"] = i
        # 名称放在序号后面
        r_ordered = {"seq": r["seq"], "name": r.pop("name")}
        r_ordered.update(r)
        kept[i - 1] = r_ordered
    return kept


def _extract_name(region: str) -> str:
    """从锚点前的区域提取发明名称：定位最后一个「序号+名称开头」，
    去掉序号后拼接跨行文本（换行直接相连，行内空格保留）"""
    starts = list(_ROW_START.finditer(region))
    if starts:
        region = region[starts[-1].start():]
    name = re.sub(r'^\s*\d{1,4}\s*', '', region)
    name = re.sub(r'\s*\n\s*', '', name)
    return name.strip()
