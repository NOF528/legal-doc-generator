"""
商标表解析（8.1 商标信息）

表格列：序号 商标图案 商标名称 商标状态 申请/注册号 申请日期 国际分类
行形态（清洗后文本）两种：
  5\n种耘网 已注册 64243038 2022-04-25 35类 广告销售
  9\nHWAWAN已注册·商标续展核准\n11170432 2012-07-05 9类 科学仪器

解析策略：以「申请号 + 日期 + XX类」为锚点定位每行，
再向前回溯序号/名称/状态。只保留状态以「已注册」开头的行。
"""
import re
from typing import Dict, List

# 表头之后才是数据区
_HEADER = "序号 商标图案 商标名称 商标状态"

# 行锚点：申请/注册号（6~9位数字可带字母后缀）+ 申请日期 + 国际分类（含分类名）
# 分类名（如「广告销售」）一并消费掉，防止泄漏到下一行的名称里
_ANCHOR = re.compile(
    r'(\d{6,9}[A-Z]?)\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2})类\s*[一-龥]{0,6}'
)

# 状态关键字（用于把「名称 状态」粘连文本拆开）
_STATUS_KEYWORDS = [
    "已注册·商标续展核准",
    "已注册",
    "商标无效·初审驳回",
    "商标无效",
    "注册申请中",
    "初审公告",
    "驳回复审",
    "异议中",
    "撤销",
]
_STATUS_RE = re.compile("(" + "|".join(_STATUS_KEYWORDS) + ")")

# 页脚残留
_FOOTER_RE = re.compile(r'联系电话：[\d\-]+|企查查科技股份有限公司\s*\d*|工商公示')

# 截断提示：此维度共计 280条记录，当前报告中显示 100条
_TRUNC_RE = re.compile(r'此维度共计\s*(\d+)\s*条记录，当前报告中显示\s*(\d+)\s*条')


def detect_truncation(block: str) -> tuple:
    """检测报告的维度截断提示，返回 (总条数, 展示条数) 或 None"""
    if not block:
        return None
    m = _TRUNC_RE.search(block)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _strip_footer(text: str) -> str:
    return _FOOTER_RE.sub("", text)


def parse_trademarks(block: str) -> List[Dict]:
    """
    从 8.1 内容块解析商标行，只保留「已注册」状态。

    Returns:
        [{seq, name, status, app_no, app_date, intl_class}]，序号已重排
    """
    if not block or "暂未查询到" in block:
        return []
    # 只取表头之后的数据区（表头行可能拆成两段，以最后一个字段名「国际分类」为准）
    idx = block.find(_HEADER)
    if idx < 0:
        return []
    end_idx = block.find("国际分类", idx)
    if end_idx < 0:
        return []
    text = _strip_footer(block[end_idx + len("国际分类"):])

    rows: List[Dict] = []
    matches = list(_ANCHOR.finditer(text))
    prev_end = 0
    seen = set()
    for m in matches:
        app_no, app_date, intl_class = m.group(1), m.group(2), m.group(3)
        # 名称+状态区域 = 上一锚点结束 → 本锚点开始
        region = text[prev_end:m.start()].strip()
        prev_end = m.end()

        # 去掉区域开头的序号（纯数字行/词）
        region = re.sub(r'^\d{1,4}\s*', '', region).strip()
        # 拆名称与状态
        sm = _STATUS_RE.search(region)
        if not sm:
            continue
        name = region[:sm.start()].strip()
        status = re.sub(r'\s+', '', region[sm.start():])
        name = re.sub(r'\s*\n\s*', ' ', name).strip()
        if not name or not app_no or app_no in seen:
            continue
        seen.add(app_no)
        rows.append({
            "name": name,
            "status": status,
            "app_no": app_no,
            "app_date": app_date,
            "intl_class": f"{intl_class}类",
        })

    # 过滤：只保留已注册（含 已注册·商标续展核准）
    kept = [r for r in rows if r["status"].startswith("已注册")]
    for i, r in enumerate(kept, 1):
        r["seq"] = i
    return kept
