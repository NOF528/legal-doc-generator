"""
变更后股权结构计算器

两条信息源（企查查专业版信用报告）：
- 2.2 股东信息：最新股东结构（名称、比例、出资额），作为倒推的起点
- 2.7 变更记录：变更前列/变更后列文本，带【新进】【退出】（持股±x%）标注
  注意：企查查 PDF 提取后 before/after 两列经常粘连在一起，且股东名册
  会被页脚（工商公示/联系电话/企查查科技股份有限公司+页码）截断，
  因此解析时把 project+before+after 合并后按标注区分进出方。

计算逻辑：
- 逻辑一（倒推）：以 2.2 为最新状态，沿变更记录从近到远逐日倒推：
  删除【新进】、加回【退出】、把（持股±x%）反向作用到在册股东比例上。
- 逻辑二（直读）：直接解析每条投资人变更记录文本，取变更后值（带
  （持股±x%）标注的条目优先），得到当期股东名册；比例合计不足 100% 时
  用逻辑一的状态补齐缺失股东（跨页截断场景）。
"""

import re
from typing import Dict, List, Optional, Tuple


# ================================================================
# 文本清洗
# ================================================================

def _clean_change_text(text: str) -> str:
    """清洗变更记录文本，保留【新进】【退出】和（持股±x%）标注"""
    if not text:
        return ""
    text = str(text).replace("\n", " ")
    # 项目头（如 "投资人变更（包括…）"/"投资人（股权）变更"）
    text = re.sub(r'[一-龥]{2,12}变更[（(]包括[^）)]*[）)]', '', text)
    text = re.sub(r'投资人[（(]股权[）)]变更', '', text)
    # 断裂的字段标签（跨行拆字：持股比 例 / 认缴出 资额）
    text = re.sub(r'持\s*股\s*比\s*例', '持股比例', text)
    text = re.sub(r'认\s*缴\s*出\s*资\s*额', '认缴出资额', text)
    # 裸 "比例 x%" / "出资额 x"（部分报告版式无 "持股"/"认缴" 前缀）
    text = re.sub(r'(?<!持股)比\s*例\s*[:：]?\s*([\d.]+)\s*%', r'持股比例:\1%', text)
    text = re.sub(r'(?<!认缴)出\s*资\s*额\s*[:：]?\s*([\d,.]+)', r'认缴出资额:\1', text)
    # 页脚与报告标识（含紧随的页码）
    text = re.sub(r'企查查科技股份有限公司\s*\d*', '', text)
    text = re.sub(r'工商公示|国家企业信用信息公示系统', '', text)
    text = re.sub(r'联系电话\s*[:：]?\s*[\d\-]+', '', text)
    # 泄漏进来的日期碎片（如相邻记录残留的 "2020-12-02"）
    text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)
    # 截断提示
    text = re.sub(r'此维度共计.{0,40}?查询[。.]?', '', text)
    text = re.sub(r'(当前报告中显示|如需更多|官方网站)[^,，;；]*', '', text)
    # 国别列
    text = re.sub(r'国别\s*[（(]?\s*地区\s*[）)]?\s*[:：]?\s*中国', '', text)
    # 裸国别名（部分版式直接以 "，中国，"/"，香港（持股…" 形式出现，可能跨行断开）
    text = re.sub(
        r'(?<=[，,\s])(中\s*国\s*香\s*港|中\s*国|香\s*港|英\s*国|美\s*国|开\s*曼\s*群?\s*岛?|新\s*加\s*坡|日\s*本|德\s*国)(?=[，,;；(（]|$)',
        '', text)
    # 出资额变动注释，如 （-199.8）（+1466.4）
    text = re.sub(r'[（(]\s*[+-]\s*[\d,.]+\s*[）)]', '', text)
    # 单位：（万元）/（万 元）/数字后的 万元 —— 直接删除，避免与后续股东名粘连
    text = re.sub(r'[（(]\s*万\s*元\s*[）)]', '', text)
    text = re.sub(r'(?<=\d)\s*万元', '', text)
    return text.strip()


# ================================================================
# 股东条目解析
# ================================================================

class Entry:
    """一条股东记录"""
    __slots__ = ("name", "ratio", "amount", "is_new", "is_exit", "delta")

    def __init__(self, name: str, ratio: Optional[float] = None,
                 amount: Optional[float] = None,
                 is_new: bool = False, is_exit: bool = False,
                 delta: Optional[float] = None):
        self.name = name
        self.ratio = ratio          # 比例数值（不带 %）
        self.amount = amount        # 出资额数值（万元）
        self.is_new = is_new
        self.is_exit = is_exit
        self.delta = delta          # （持股±x%）的带符号数值

    @property
    def has_delta(self) -> bool:
        return self.delta is not None


def _norm_name(name: str) -> str:
    """名称归一化（用于匹配）：去空白/分隔符、去实控人标记*、统一括号"""
    if not name:
        return ""
    n = re.sub(r'[\s;；、，,]+', '', name)
    n = n.rstrip('*＊')
    n = n.replace('（', '(').replace('）', ')')
    return n


def _clean_display_name(name: str) -> str:
    """名称展示清洗：去标注、去*、去职务/股东类型后缀、去项目名前缀、去首尾空白"""
    n = re.sub(r'【[^】]*】', '', name)
    n = re.sub(r'[（(]\s*持股[^）)]*[）)]', '', n)
    n = n.replace('*', '').replace('＊', '')
    n = re.sub(r'[（(]?(法定代表人|执行董事|董事|监事|总经理|经理|负责人)[）)]?$', '', n)
    n = re.sub(r'(自然人股东|内资合伙企业|企业法人|外资企业|机关法人|法人股东)$', '', n)
    n = re.sub(r'^(其他事项备案|章程备案|投资人变更|股东变更|发起人变更)', '', n)
    # 中文字符间的空白是 PDF 换行残留，去除（保留英文名内的空格）
    n = re.sub(r'(?<=[一-龥）)])\s+(?=[一-龥（(])', '', n)
    return n.strip(' ;；:：、，,')


def _is_junk_name(name: str) -> bool:
    """是否是噪音名称（其他章节泄漏/表头残留/跨页名字碎片如 "伙）"）"""
    if not name:
        return True
    n = re.sub(r'\s+', '', name)
    if len(n) < 2:
        return True
    if re.search(r'(董事|监事|信息|公示|查询|报告|电话|流通股)$', n):
        return True
    # 字段标签/国别残留开头的碎片
    if re.match(r'^(持股比例|比例|认缴出资额|出资额|出资|资额|额|例|国别|中国|中国香港|香港|英国|美国|开曼)', n):
        return True
    # 括号不成对且以右括号结尾（跨页截断的名字尾巴，如 "伙）"）
    if n.endswith(('）', ')')) and ('（' not in n and '(' not in n):
        return True
    if n.startswith(('）', ')', '（', '(')):
        return True
    # 纯数字/标点
    if not re.search(r'[一-龥A-Za-z]', n):
        return True
    # 纯通用词组合（跨页碎片如 "合伙企业（有限合伙）"），不是真实股东名
    stripped = re.sub(r'[\(（\)）\s]', '', n)
    for tok in _GENERIC_TOKENS:
        stripped = stripped.replace(tok, "")
    if not stripped:
        return True
    return False


def _extract_flags_and_delta(text: str) -> Tuple[bool, bool, Optional[float]]:
    """从条目文本提取【新进】【退出】和（持股±x%）"""
    is_new = "【新进】" in text
    is_exit = "【退出】" in text
    delta = None
    m = re.search(r'[（(]\s*持股\s*([+-])\s*([\d.]+)\s*%?\s*[）)]', text)
    if m:
        sign = 1.0 if m.group(1) == "+" else -1.0
        delta = sign * float(m.group(2))
    return is_new, is_exit, delta


def parse_shareholder_entries(text: str) -> List[Entry]:
    """
    解析股东条目（自动识别两种格式），跨页碎条已合并：
    - 格式A：名称[标记]持股比例:x%[（持股±y%）]认缴出资额:z万元
    - 格式B：名称[标记][（持股±y%）]（纯名单，比例未知）
    """
    text = _clean_change_text(text)
    if not text:
        return []

    if "持股比例" in text or "认缴出资额" in text or "出资额" in text:
        entries = _parse_entries_format_a(text)
        return _merge_fragments(entries)
    return _parse_entries_format_b(text)


def _parse_entries_format_a(text: str) -> List[Entry]:
    """格式A：带持股比例/认缴出资额字段（无名碎片保留 name=''，交由合并处理）"""
    # 在「数值结束后紧跟新姓名/下一条目的持股比例」处补分隔符
    # （认缴出资额、持股注释是同一条目的延续，不断开）
    text = re.sub(
        r'((?:持股比例|出资额)[:：]\s*[\d,.]+%?)\s*'
        r'(?!认缴出资额|出资额|[（(]\s*持股)'
        r'(?=[一-龥A-Za-z(（])',
        r'\1;',
        text,
    )
    parts = re.split(r'[,，;；、]', text)
    # 跨页粘合拆分："黄桂林： 出     合伙企业（有限合伙）：出资额…"
    # （页脚被清洗后留下大段空白，名字: 与下一条目的名字尾巴粘在一起）
    split_parts: List[str] = []
    for part in parts:
        m = re.match(r'^([^：:]{2,15})[：:]\s*出?\s{2,}(.+)$', part)
        if m:
            split_parts.append(m.group(1))
            split_parts.append(m.group(2))
        else:
            split_parts.append(part)
    parts = split_parts
    entries: List[Entry] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 名称 = 第一个字段标签/标注之前的文本
        m = re.split(r'【|持股比例|认缴出资额|出资额|国别', part, maxsplit=1)
        raw_name = m[0].strip()
        name = _clean_display_name(raw_name)
        is_new, is_exit, delta = _extract_flags_and_delta(part)

        ratio = None
        rm = re.search(r'持股比例[:：]\s*([\d.]+)\s*%', part)
        if rm:
            ratio = float(rm.group(1))

        amount = None
        am = re.search(r'出资额[:：]\s*([\d,.]+)', part)
        if am:
            try:
                amount = float(am.group(1).replace(",", ""))
            except ValueError:
                amount = None

        if _is_junk_name(name):
            # 无名碎片（跨页断行的后半截）：保留数值/标注，由 _merge_fragments 归并
            if ratio is None and amount is None and delta is None and not is_new and not is_exit:
                continue
            entries.append(Entry("", ratio, amount, is_new, is_exit, delta))
            continue
        entries.append(Entry(name, ratio, amount, is_new, is_exit, delta))
    return entries


def _merge_fragments(entries: List[Entry]) -> List[Entry]:
    """
    把跨页无名碎片并回对应的命名条目：
    - 带（持股±x%）的碎片是「变更后列」的残留：若某命名条目满足
      条目比例 + 碎片delta ≈ 碎片比例，则归属于它，并用碎片值覆盖（变更后值）
    - 其余碎片并入最近的前一个命名条目（只补缺）
    """
    out: List[Entry] = []
    for e in entries:
        if e.name:
            out.append(e)
            continue
        target = None
        if e.delta is not None and e.ratio is not None:
            for cand in reversed(out):
                if cand.ratio is not None and abs(cand.ratio + e.delta - e.ratio) < 0.01:
                    target = cand
                    break
        if target is None and e.delta is not None and e.ratio is None and e.amount is None:
            # 纯增量注释碎片（如 "（持股-2.9556%）"）：并入最近的前一个命名条目
            for cand in reversed(out):
                if cand.name:
                    if cand.delta is None:
                        cand.delta = e.delta
                    cand.is_new = cand.is_new or e.is_new
                    cand.is_exit = cand.is_exit or e.is_exit
                    break
            continue
        if target is None and e.delta is not None and e.ratio is None:
            # 只有 delta 没有比例的碎片无法定位归属，直接丢弃，避免污染他条目
            continue
        if target is None and out:
            target = out[-1]
        if target is None:
            continue
        if e.delta is not None:
            # 变更后列值：覆盖比例/金额，保留 delta 供倒推
            target.delta = e.delta
            if e.ratio is not None:
                target.ratio = e.ratio
            if e.amount is not None:
                target.amount = e.amount
            target.is_new = target.is_new or e.is_new
            target.is_exit = target.is_exit or e.is_exit
        else:
            if target.ratio is None:
                target.ratio = e.ratio
            if target.amount is None:
                target.amount = e.amount
            target.is_new = target.is_new or e.is_new
            target.is_exit = target.is_exit or e.is_exit
    return out


def _parse_entries_format_b(text: str) -> List[Entry]:
    """格式B：纯名单（名称粘连，可能带【新进】【退出】（持股±x%））"""
    # 在 公司/）/* 之后切分，再把【新进】（持股±）等标注碎片并回前一条；
    # 大段空白（页脚清洗残留）也是条目边界
    raw_chunks = re.split(r'(?<=公司)|(?<=）)|(?<=\*)|(?<=\))', text)
    chunks: List[str] = []
    for c in raw_chunks:
        c = c.strip()
        if not c:
            continue
        if chunks and (c.startswith("【") or re.match(r'^[（(]\s*持股', c)):
            chunks[-1] += c
        else:
            chunks.append(c)

    entries: List[Entry] = []
    for chunk in chunks:
        # 跨页粘合：两个名字之间隔着大段空白（页脚被清洗后残留）
        sub_chunks = re.split(r'\s{2,}', chunk)
        for sub in sub_chunks:
            is_new, is_exit, delta = _extract_flags_and_delta(sub)
            name_part = re.split(r'【|[（(]\s*持股', sub, maxsplit=1)[0]
            name = _clean_display_name(name_part)
            if _is_junk_name(name):
                continue
            entries.append(Entry(name, None, None, is_new, is_exit, delta))
    return entries


def _match_key(key: str, keys) -> Optional[str]:
    """名称键匹配：精确优先；其次互为前缀（跨页截断名）；
    再次以状态名作为后缀（跨页粘合名如 "深圳市瑞正投资李乔亮" 尾部是真名）"""
    if not key:
        return None
    key_set = keys if isinstance(keys, (set, frozenset)) else set(keys)
    if key in key_set:
        return key
    for k in keys:
        if k and (k.startswith(key) or key.startswith(k)):
            return k
    for k in keys:
        if k and len(k) >= 3 and key.endswith(k) and len(key) > len(k):
            return k
    return None


def post_change_entries(text: str) -> List[Entry]:
    """
    从一条投资人变更记录的完整文本中，提取「变更后」股东列表。
    规则：
    - 【退出】条目只出现在变更前列，排除
    - 同名（含跨页截断的前缀名）条目去重时优先保留带（持股±x%）标注的
      （变更后列特征），其次带比例的，最后是普通条目
    """
    entries = [
        e for e in parse_shareholder_entries(text)
        if e.name and not e.is_exit
    ]
    return _dedup_entries(entries)


# ================================================================
# 数字工具
# ================================================================

def _to_float(text) -> Optional[float]:
    """从 '25.0000%' / '1800' / '7200 万元' 等文本提取数字"""
    if text is None:
        return None
    s = str(text)
    s = re.split(r'最新|（|\(', s)[0]
    s = s.replace("%", "").replace("万元", "").replace(",", "").replace(" ", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _fmt(num: Optional[float]) -> str:
    """数字格式化：去尾零"""
    if num is None:
        return ""
    s = f"{num:.4f}".rstrip("0").rstrip(".")
    return s


def _capital_from_project(project: str) -> Tuple[Optional[float], Optional[float]]:
    """从粘连的项目文本提取注册资本变更前后值，如 '注册资本 6000 万元 7200 万元（+1200 万元）'"""
    if not project:
        return None, None
    nums = re.findall(r'([\d,]+(?:\.\d+)?)\s*万元', str(project))
    if len(nums) >= 2:
        return float(nums[0].replace(",", "")), float(nums[1].replace(",", ""))
    return None, None


# ================================================================
# 时间线计算（逻辑一倒推 + 逻辑二直读）
# ================================================================

def compute_shareholder_timeline(
    date_records: Dict[str, List[Dict]],
    current_shareholders: List[Dict],
    current_capital: Optional[float],
) -> Dict[str, Dict]:
    """
    计算每个股权变更日期的「变更后股权结构」。

    Args:
        date_records: {raw_date: [record...]}，record 含 project/before/after
        current_shareholders: 2.2 最新股东 [{name, ratio, amount}]
        current_capital: 最新注册资本（万元）

    Returns:
        {raw_date: {"shareholders": [{name, ratio, amount}], "capital": float|None}}
        ratio/amount 为字符串（不带单位），缺失为 ""。
    """
    # 初始化状态：2.2 最新股东
    state: Dict[str, Dict] = {}
    state_order: List[str] = []
    for sh in current_shareholders:
        name = sh.get("name", "")
        key = _norm_name(name)
        if not key:
            continue
        state[key] = {
            "display": name,
            "ratio": _to_float(sh.get("ratio")),
        }
        state_order.append(key)

    capital = current_capital

    # 只处理股权相关日期（投资人变更/注册资本），按时间倒序
    equity_dates = []
    for date, records in date_records.items():
        if any(("投资人" in r.get("project", "") or "股东" in r.get("project", "")
                or "注册资本" in r.get("project", "") or "注册资金" in r.get("project", ""))
               for r in records):
            equity_dates.append(date)
    equity_dates.sort(reverse=True)

    result: Dict[str, Dict] = {}

    for date in equity_dates:
        records = date_records[date]
        sh_records = [r for r in records if "投资人" in r.get("project", "") or "股东" in r.get("project", "")]
        cap_records = [r for r in records if "注册资本" in r.get("project", "") or "注册资金" in r.get("project", "")]

        # ---- 当期「变更后」股东结构（快照，在倒推之前取） ----
        if sh_records:
            post: List[Entry] = []
            for r in sh_records:
                # 用分号分隔拼接，防止跨页/跨字段的股东名粘连成一条
                full_text = ";\n".join([r.get('project', ''), r.get('before', ''), r.get('after', '')])
                post.extend(post_change_entries(full_text))
            post = _dedup_entries(post)
            if post:
                shareholders = _fill_from_state(post, state, capital)
            else:
                shareholders = []
            # 有效性校验：名册比例合计应约为 100%
            # - 合计为 0：记录全是噪音（如上市公司流通股结构变动）
            # - 合计远超 100：记录无【新进】【退出】/增量标注，变更前后两列名单
            #   无法区分而混入（部分版式的报告），与其出错不如回退
            # 两种情况都回退到当期状态名册
            rec_ratios = [float(s["ratio"]) for s in shareholders if s["ratio"]]
            if shareholders and rec_ratios:
                rec_total = sum(rec_ratios)
                if rec_total > 105:
                    shareholders = []
            elif shareholders and not rec_ratios:
                shareholders = []
            if not shareholders:
                shareholders = _state_roster(state, state_order, capital)
            # 比例合计校验：名册明显缺人（跨页截断）时按状态补齐
            ratios = [float(s["ratio"]) for s in shareholders if s["ratio"]]
            if ratios:
                total = sum(ratios)
                if total < 98.5:
                    seen = {_norm_name(s["name"]) for s in shareholders}
                    seen_ratios = [float(s["ratio"]) for s in shareholders if s["ratio"]]
                    for key in state_order:
                        if key in state and _match_key(key, seen) is None:
                            # 更名股东去重：比例相同且名称有显著共同片段 →
                            # 与名册中某位是同一主体（改名），跳过
                            if _is_renamed_duplicate(state[key], shareholders):
                                continue
                            # 加入后合计明显超过 100% 的，多半是后期才新进、
                            # 变更记录缺失导致倒推时未能剔除，跳过
                            cand_ratio = state[key]["ratio"]
                            if cand_ratio and total + cand_ratio > 101.5:
                                continue
                            shareholders.append({
                                "name": state[key]["display"],
                                "ratio": _fmt(state[key]["ratio"]),
                                "amount": _fmt(_amount_of(state[key]["ratio"], capital)),
                            })
                            seen.add(key)
                            if state[key]["ratio"]:
                                total += state[key]["ratio"]
                            if total >= 98.5:
                                break
        else:
            # 纯注册资本变更日：股东不变，仅出资额随资本变化
            shareholders = _state_roster(state, state_order, capital)

        result[date] = {"shareholders": shareholders, "capital": capital}

        # ---- 倒推到变更前状态（逻辑一） ----
        for r in sh_records:
            full_text = ";\n".join([r.get('project', ''), r.get('before', ''), r.get('after', '')])
            for e in parse_shareholder_entries(full_text):
                if not e.name:
                    continue
                key = _norm_name(e.name)
                if not key:
                    continue
                if e.is_new:
                    # 新进方：变更前不存在
                    mk = _match_key(key, state.keys())
                    if mk is not None:
                        state.pop(mk, None)
                        if mk in state_order:
                            state_order.remove(mk)
                elif e.is_exit:
                    # 退出方：加回。（持股-x%）的 x 即其变更前比例；无 delta 时取条目前值
                    pre_ratio = abs(e.delta) if e.delta is not None else e.ratio
                    # 若与状态中现有股东是同一主体（后来的新名字），先移除新名字，
                    # 避免更名股东新旧两个名字同时出现在更早日期的名册里
                    for sk in list(state.keys()):
                        if _is_renamed_pair(e.name, pre_ratio, state[sk]["display"], state[sk]["ratio"]):
                            state.pop(sk, None)
                            if sk in state_order:
                                state_order.remove(sk)
                    state[key] = {"display": e.name, "ratio": pre_ratio}
                    if key not in state_order:
                        state_order.append(key)
                elif e.delta is not None and e.ratio is not None:
                    # 在册股东比例变动：pre = post - delta（条目比例为变更后值）
                    # 注意：仅格式A（条目自带比例）才可靠——格式B（纯名单）的
                    # （持股±x%）标注可能粘在前一个无关名字上，盲目反向会污染状态
                    mk = _match_key(key, state.keys())
                    base = e.ratio
                    if base is not None:
                        store_key = mk if mk is not None else key
                        display = state[store_key]["display"] if store_key in state else e.name
                        state[store_key] = {"display": display, "ratio": round(base - e.delta, 4)}
                        if store_key not in state_order:
                            state_order.append(store_key)

        # 注册资本倒推
        for r in cap_records:
            before_num = _to_float(r.get("before"))
            if before_num is None:
                before_num, _ = _capital_from_project(r.get("project", ""))
            if before_num:
                capital = before_num

    return result


def _dedup_entries(entries: List[Entry]) -> List[Entry]:
    """同名（含前缀/后缀匹配）去重，保留带 delta/比例的条目"""
    best: Dict[str, Entry] = {}
    order: List[str] = []
    for e in entries:
        key = _norm_name(e.name)
        if not key:
            continue
        existing = _match_key(key, order)
        if existing is None:
            best[key] = e
            order.append(key)
            continue
        best[existing] = _merge_two(best[existing], e)
    result = [best[k] for k in order]
    # 更名股东二次去重：记录变更前/后列分别列出新旧名字（无标注），
    # 名字模糊匹配为同一主体时合并（保留带 delta 者，即变更后值）
    merged: List[Entry] = []
    for e in result:
        dup = None
        for m in merged:
            if _is_renamed_pair(m.name, m.ratio, e.name, e.ratio):
                dup = m
                break
        if dup is None:
            merged.append(e)
        else:
            idx = merged.index(dup)
            merged[idx] = _merge_two(dup, e)
    return merged


def _merge_two(a: Entry, b: Entry) -> Entry:
    """合并同一主体的两条记录：delta 优先（变更后值）；
    分数相同取后出现者——拼接文本中变更后列在变更前列之后，
    无标注记录里后出现的是变更后数值。显示名取带 delta 的一方。"""
    def score(x: Entry) -> int:
        return (2 if x.has_delta else 0) + (1 if x.ratio is not None else 0) + (1 if x.is_new else 0)

    winner = b if score(b) >= score(a) else a
    loser = a if winner is b else b
    # 显示名：带 delta 的是变更后（新）名字；否则前缀关系取长者，后缀关系取短者
    n_w, n_l = _norm_name(winner.name), _norm_name(loser.name)
    if winner.has_delta and not loser.has_delta:
        display = winner.name
    elif n_w.startswith(n_l):
        display = winner.name
    elif n_l.startswith(n_w):
        display = loser.name
    elif n_w.endswith(n_l):
        display = loser.name
    else:
        display = winner.name
    return Entry(
        display,
        winner.ratio if winner.ratio is not None else loser.ratio,
        winner.amount if winner.amount is not None else loser.amount,
        winner.is_new or loser.is_new,
        winner.is_exit or loser.is_exit,
        winner.delta if winner.delta is not None else loser.delta,
    )


def _state_roster(state: Dict[str, Dict], state_order: List[str],
                  capital: Optional[float]) -> List[Dict]:
    """从当期状态生成名册（含更名股东自去重：同名主体保留后出现者，
    因为倒推中后加回的是该时点更准确的旧名字）"""
    roster = [
        {
            "name": state[key]["display"],
            "ratio": _fmt(state[key]["ratio"]),
            "amount": _fmt(_amount_of(state[key]["ratio"], capital)),
        }
        for key in state_order if key in state
    ]
    result: List[Dict] = []
    for sh in roster:
        dup = None
        for i, kept in enumerate(result):
            if _is_renamed_pair(
                    kept["name"], float(kept["ratio"]) if kept["ratio"] else None,
                    sh["name"], float(sh["ratio"]) if sh["ratio"] else None):
                dup = i
                break
        if dup is None:
            result.append(sh)
        else:
            result[dup] = sh  # 后出现的（倒推加回的旧名）覆盖
    return result


def _amount_of(ratio: Optional[float], capital: Optional[float]) -> Optional[float]:
    """按 比例 × 注册资本 估算出资额"""
    if ratio is None or capital is None:
        return None
    return round(ratio * capital / 100.0, 4)


# 更名股东模糊匹配时剔除的通用词
_GENERIC_TOKENS = [
    "有限合伙", "合伙企业", "有限公司", "有限责任", "股份", "企业",
    "基金", "科技", "创业", "咨询", "中心", "公司", "合伙",
]


def _distinctive(name: str) -> str:
    """去掉通用词后的显著名称片段"""
    n = _norm_name(name)
    for tok in _GENERIC_TOKENS:
        n = n.replace(tok, "")
    return n


def _common_substring(a: str, b: str) -> Tuple[int, int, int]:
    """最长公共子串的 (长度, a中起始, b中起始)"""
    best = (0, 0, 0)
    if not a or not b:
        return best
    for i in range(len(a)):
        for j in range(i + 1, len(a) + 1):
            if j - i <= best[0]:
                continue
            k = b.find(a[i:j])
            if k >= 0:
                best = (j - i, i, k)
    return best


# 公共片段黑名单：仅是这些通用词组合的公共片段不算显著
_GENERIC_COMMON = re.compile(
    r'^[\(（\)）]*(股权|投资|投资管理|企业管理|管理|咨询|创业|科技|基金|企业|中心|合伙)+[\(（\)）]*$'
)


def _is_renamed_pair(name_a: str, ratio_a: Optional[float],
                     name_b: str, ratio_b: Optional[float]) -> bool:
    """判断两个名字是否同一主体（股东更名）：
    - 公共片段必须显著（不能只是"股权投资"这类通用词，也不能纯是共同前缀，
      防止 "佛山市和高数科" vs "佛山市和高智行"、"深圳市怡亚通" vs "深圳市前海怡亚通" 误判）
    - 弱条件：比例近似（±0.02）且显著公共片段 ≥3 字符
    - 强条件：显著公共片段 ≥5 字符、同时延伸到两个显著名末尾、覆盖较短名 ≥80%
    """
    da, db = _distinctive(name_a), _distinctive(name_b)
    if len(da) < 3 or len(db) < 3:
        return False
    length, start_a, start_b = _common_substring(da, db)
    common = da[start_a:start_a + length]
    if length < 3 or _GENERIC_COMMON.match(common):
        return False
    # 纯共同前缀（如 "佛山市和高…"）不算显著
    if start_a == 0 and start_b == 0:
        return False
    if (ratio_a is not None and ratio_b is not None
            and abs(ratio_a - ratio_b) <= 0.02 and length >= 3):
        return True
    ends_both = (start_a + length == len(da)) and (start_b + length == len(db))
    if length >= 5 and ends_both and length >= 0.8 * min(len(da), len(db)):
        return True
    return False


def _is_renamed_duplicate(state_sh: Dict, shareholders: List[Dict]) -> bool:
    """判断 state 中的股东是否与名册中某位是同一主体（改名），补齐时跳过"""
    s_ratio = state_sh.get("ratio")
    for sh in shareholders:
        o_ratio = float(sh["ratio"]) if sh.get("ratio") else None
        if _is_renamed_pair(state_sh.get("display", ""), s_ratio,
                            sh.get("name", ""), o_ratio):
            return True
    return False


def _fill_from_state(post: List[Entry], state: Dict[str, Dict],
                     capital: Optional[float]) -> List[Dict]:
    """逻辑二直读的名单，缺比例/金额时用逻辑一的状态补齐；截断名按状态全名展示。
    无比例且无出资额、又无法匹配到状态的条目视为跨页碎片，丢弃。"""
    result = []
    for e in post:
        key = _norm_name(e.name)
        mk = _match_key(key, state.keys())
        if e.ratio is None and e.amount is None and mk is None:
            continue
        ratio = e.ratio
        if ratio is None and mk is not None:
            ratio = state[mk]["ratio"]
        amount = e.amount
        if amount is None:
            amount = _amount_of(ratio, capital)
        display = e.name
        if mk is not None and key != mk:
            # 条目名与状态名不一致（截断/粘合），以状态全名为准
            display = state[mk]["display"]
        elif mk is not None and len(_norm_name(state[mk]["display"])) > len(key):
            display = state[mk]["display"]
        result.append({
            "name": display,
            "ratio": _fmt(ratio),
            "amount": _fmt(amount),
        })
    return result
