"""
表格解析模块
"""
import re
from typing import List, Dict, Optional, Callable


class TableRowBuffer:
    """
    处理跨页/跨行断行的表格行缓冲器
    """
    def __init__(self):
        self.buffer = ""
    
    def append(self, line: str) -> bool:
        """
        追加一行，如果该行以序号开头则返回 True（表示上一行已完整）
        """
        line = line.strip()
        line = self._clean_embedded_header(line)
        
        if not line:
            return False, ""
        
        # 判断是否是新行的开始
        is_new_row = self._is_new_row_start(line)
        
        if is_new_row:
            return True, line
        
        self.buffer += " " + line
        return False, ""
    
    def flush(self) -> str:
        """取出当前缓冲内容"""
        result = self.buffer.strip()
        self.buffer = ""
        return result
    
    def _clean_embedded_header(self, line: str) -> str:
        """清理嵌入在行中的页眉残片"""
        line = re.sub(r"联系电话：\d{3}-\d{8}", "", line)
        line = re.sub(r"企查查科技股份有限公司\s+\d+", "", line)
        line = re.sub(r"企业信用报告专业版", "", line)
        line = re.sub(r"---PAGE_\d+---", "", line)
        # 注意：不再硬编码清洗特定企业名。页眉中的企业名应由 PageHeaderCleaner
        # 根据传入的 company_name 统一处理，避免误删正文中的同名企业。
        return line.strip()
      
    
    def _is_new_row_start(self, line: str) -> bool:
        """
        智能判断一行是否是新表格行的开始
        """
        # 情况1：明显是百分比断片（如 "13.4380%"）-> 不是新行
        if re.match(r"^\d+\.\d+%", line):
            return False
        
        # 情况2：以数字+空格+非数字开头（如 "1 郭国峰" "3 名称"）-> 是新行
        if re.match(r"^\d+\s+[^\s\d%]", line):
            return True
        
        # 情况3：以数字紧接非数字开头（如 "3名称"）-> 是新行
        if re.match(r"^\d+[^\s\d%.]", line):
            return True
        
        # 情况4：如果 buffer 里还没有百分比，而新行看起来是百分比或金额 -> 不是新行
        if self.buffer and not re.search(r"\d+\.?\d*%", self.buffer):
            # 以数字开头且很短（如 "13 "）或紧跟百分比
            if re.match(r"^\d+\.?\d*\s*$", line) or re.match(r"^\d+\.?\d*%", line):
                return False
        
        # 情况5：以数字开头但后面跟着已知的表格内容特征
        # 比如 buffer 以公司名结尾，新行是日期或状态
        if self.buffer:
            # 如果 buffer 里有完整的百分比+日期，新行又只是纯数字 -> 可能是新序号
            has_ratio = re.search(r"\d+\.?\d*%", self.buffer)
            has_date = re.search(r"\d{4}-\d{2}-\d{2}", self.buffer)
            
            # 但如果新行只是一个数字（如13），而buffer里还没有完整行，可能是断片
            if re.match(r"^\d+\s*$", line) and not (has_ratio and has_date):
                return False
        
        # 默认：如果前面没有 buffer，且以数字开头，可能是新行
        if not self.buffer and re.match(r"^\d+", line):
            return True
        
        return False


class TableExtractor:
    """
    通用表格提取器
    """
    
    def __init__(self, lines: List[str], header_markers: List[str]):
        """
        :param lines: 区块内所有行
        :param header_markers: 表头识别关键词，如 ["序号", "发起人名称", "持股比例"]
        """
        self.lines = lines
        self.header_markers = header_markers
        self.data_start_idx = self._find_header_index()
    
    def _find_header_index(self) -> int:
        """找到表头所在行索引"""
        for i, line in enumerate(self.lines):
            if all(marker in line for marker in self.header_markers):
                return i
            # 放宽条件：匹配大部分关键词
            matches = sum(1 for m in self.header_markers if m in line)
            if matches >= max(2, len(self.header_markers) - 1):
                return i
        return -1
    
    def extract(self, parser_func: Callable[[str], Optional[Dict]]) -> List[Dict]:
        """
        提取表格数据
        :param parser_func: 单行解析函数
        """
        if self.data_start_idx == -1:
            return []
        
        results = []
        buffer = TableRowBuffer()
        
        for line in self.lines[self.data_start_idx + 1:]:
            if not line.strip():
                continue
            
            # 跳过表头重复出现
            if all(m in line for m in self.header_markers):
                continue
            
            is_new_row, clean_line = buffer.append(line)
            
            if is_new_row:
                # 先处理上一行
                prev = buffer.flush()
                if prev:
                    parsed = parser_func(prev)
                    if parsed:
                        results.append(parsed)
                # 开始新行
                buffer.buffer = clean_line
        
        # 处理最后一行
        last = buffer.flush()
        if last:
            parsed = parser_func(last)
            if parsed:
                results.append(parsed)
        
        return results


def parse_shareholder_line(line: str) -> Optional[Dict]:
    """解析股东信息单行"""
    line = re.sub(r"^(\d+)([^\s\d])", r"\1 \2", line)
    
    percent_match = re.search(r"(\d+\.?\d*)%", line)
    if not percent_match:
        return None
    
    parts = line.strip().split()
    
    if not parts[0].isdigit():
        return None
    
    percent_idx = -1
    for i, p in enumerate(parts):
        if "%" in p:
            percent_idx = i
            break
    
    if percent_idx == -1:
        return None
    
    name = " ".join(parts[1:percent_idx]).strip()
    remaining = parts[percent_idx + 1:]
    
    dates = [p for p in remaining if re.match(r"\d{4}-\d{2}-\d{2}", p)]
    non_dates = [p for p in remaining if not re.match(r"\d{4}-\d{2}-\d{2}", p)]
    
    return {
        "seq": parts[0],
        "name": name,
        "ratio": parts[percent_idx],
        "amount": non_dates[0] if non_dates else "-",
        "date": dates[0] if dates else "-",
        "first_date": dates[1] if len(dates) > 1 else "-",
    }


def parse_key_person_line(line: str) -> Optional[Dict]:
    """解析主要人员单行"""
    line = re.sub(r"^(\d+)([^\s\d])", r"\1 \2", line)
    parts = line.strip().split()
    
    if not parts[0].isdigit():
        return None
    
    return {
        "seq": parts[0],
        "name": parts[1] if len(parts) > 1 else "",
        "position": parts[2] if len(parts) > 2 else "",
        "ratio": parts[3] if len(parts) > 3 else "-",
    }


def parse_investment_line(line: str) -> Optional[Dict]:
    """解析对外投资单行"""
    line = re.sub(r"^(\d+)([^\s\d])", r"\1 \2", line)
    parts = line.strip().split()
    
    if not parts[0].isdigit():
        return None
    
    # 对外投资格式复杂，用更robust的方式
    dates = [p for p in parts if re.match(r"\d{4}-\d{2}-\d{2}", p)]
    ratio_match = re.search(r"(\d+\.?\d*)%", line)
    ratio = ratio_match.group(1) + "%" if ratio_match else "-"
    
    # 找到状态词位置
    status_keywords = ["存续", "在业", "注销", "吊销", "清算", "迁出"]
    status_idx = -1
    status_val = "-"
    for i, p in enumerate(parts):
        for kw in status_keywords:
            if kw in p:
                status_idx = i
                status_val = kw
                break
        if status_idx != -1:
            break
    
    name = " ".join(parts[1:status_idx]).strip() if status_idx > 1 else ""
    
    return {
        "seq": parts[0],
        "name": name,
        "status": status_val,
        "ratio": ratio,
        "date": dates[0] if dates else "-",
    }


def parse_branch_line(line: str) -> Optional[Dict]:
    """解析分支机构单行"""
    import re
    
    # 修复跨页断开的日期
    line = re.sub(r"(\d{4})\.\s+-", r"\1-", line)
    line = re.sub(r"(\d{4})\s*-\s*(\d{2})\s*-\s*(\d{2})", r"\1-\2-\3", line)
    
    line = re.sub(r"^(\d+)([^\s\d])", r"\1 \2", line)
    parts = line.strip().split()
    
    if not parts or not parts[0].isdigit():
        return None
    
    dates = [p for p in parts if re.match(r"\d{4}-\d{2}-\d{2}", p)]
    status_keywords = ["存续", "在业", "注销", "吊销"]
    status = "-"
    for p in parts:
        for kw in status_keywords:
            if kw in p:
                status = kw
                break
    
    # 企业名称通常以"分公司"结尾，前面是公司全称
    name_parts = []
    person = "-"
    
    # 找到"分公司"的位置
    branch_idx = -1
    for i, p in enumerate(parts):
        if "分公司" in p:
            branch_idx = i
            break
    
    if branch_idx > 0:
        # 名称从序号后到分公司
        name_parts = parts[1:branch_idx + 1]
        # 负责人通常在分公司后面，长度2-4个字符
        if branch_idx + 1 < len(parts):
            next_part = parts[branch_idx + 1]
            if 2 <= len(next_part) <= 4 and not re.match(r"\d{4}-", next_part):
                person = next_part
    else:
        # 回退策略
        for i, p in enumerate(parts[1:], 1):
            name_parts.append(p)
            if "分公司" in p:
                break
    
    name = " ".join(name_parts).strip()
    
    return {
        "seq": parts[0],
        "name": name,
        "person": person,
        "date": dates[0] if dates else "-",
        "status": status,
    }


def parse_change_record(lines: List[str]) -> List[Dict]:
    """
    解析变更记录（多行模式）
    支持新旧两种格式的企查查报告
    """
    changes = []
    i = 0
    
    # 预处理：合并跨页的金额行
    merged_lines = []
    j = 0
    while j < len(lines):
        line = lines[j].strip()
        # 检查当前行是否是金额行的一部分（如 "2740.286200 万元3052.346700 万元" 被分成两行）
        if re.match(r'^\d[\d,]*\.?\d*\s*万元$', line) and j + 1 < len(lines):
            next_line = lines[j + 1].strip()
            if re.match(r'^\d[\d,]*\.?\d*\s*万元', next_line):
                # 合并两行
                merged_lines.append(line + " " + next_line)
                j += 2
                continue
        merged_lines.append(line)
        j += 1
    
    lines = merged_lines
    
    while i < len(lines):
        line = lines[i].strip()
        if not line or "变更记录" in line or line == "数据来源":
            i += 1
            continue
        
        # 匹配变更记录格式：
        # 新格式: "12025-11-17投资人变更..." 或 "22025-10-11投资人变更..."
        # 旧格式: "2025-10-11投资人变更..."
        # 注意：日期可能被序号前缀覆盖，如 "22025-10-11" 实际是 "2025-10-11"
        m = re.match(r"^(\d+)?(\d{4}-\d{2}-\d{2})(.*)", line)
        if m:
            seq = m.group(1) if m.group(1) else str(len(changes) + 1)
            date = m.group(2)
            rest = m.group(3).strip()
            
            project = rest if rest else ""
            before = ""
            after = ""
            source = ""
            
            i += 1
            content_lines = []
            while i < len(lines):
                next_line = lines[i].strip()
                # 终止条件：新的变更记录行（日期格式）
                # 匹配 "12025-11-17" 格式：序号+日期
                if re.match(r"^\d+\d{4}-\d{2}-\d{2}", next_line) and '-' in next_line[:10]:
                    # 进一步验证：确保看起来像日期（防止数字行误匹配）
                    # 日期后面应该有变更项目或明显是新的开始
                    if re.search(r"\d{4}-\d{2}-\d{2}.*(?:变更|备案|登记)", next_line):
                        break
                # 终止条件：章节标题（如 "2.1 工商信息"）
                # 注意：不要匹配金额行（如 "2740.286200 万元"）
                # 章节标题通常是 "数字.数字 中文标题" 格式，且不以 "万元" 开头
                if (re.match(r"^\d+\.\d+\s+", next_line) and 
                    len(next_line) < 60 and 
                    not re.search(r"万元\s*\d", next_line)):  # 排除 "万元3052..." 格式
                    break
                if "变更记录" in next_line and "(" in next_line:
                    break
                content_lines.append(next_line)
                i += 1
            
            if content_lines:
                # 最后一条通常是数据来源
                if content_lines[-1] in ["工商公示", "企查查", "国家企业信用信息公示系统"]:
                    source = content_lines[-1]
                    content_lines = content_lines[:-1]
                
                if not project and content_lines:
                    project = content_lines[0]
                    content_lines = content_lines[1:]
                
                # 变更前后内容
                # 先检查是否有连在一起的格式："数字 万元数字 万元"
                merged_line = None
                for idx, line in enumerate(content_lines):
                    # 尝试匹配 "数字 万元数字 万元" 格式
                    m = re.search(r'(\d[\d,]*\.?\d*)\s*万元\s*(\d[\d,]*\.?\d*)\s*万元', line)
                    if m:
                        merged_line = line
                        # 提取before和after
                        before = m.group(1) + "万元"
                        after = m.group(2) + "万元"
                        # 如果同一行或下一行有（+/-xxx万元），加到after里
                        extra_match = re.search(r'[（(]([+-]\d[\d,]*\.?\d*)\s*万元[）)]', line)
                        if not extra_match and idx + 1 < len(content_lines):
                            extra_match = re.search(r'[（(]([+-]\d[\d,]*\.?\d*)\s*万元[）)]', content_lines[idx + 1])
                        if extra_match:
                            after += "（" + extra_match.group(1) + "万元）"
                        break
                
                if not merged_line:
                    # 普通格式
                    if len(content_lines) >= 2:
                        after = content_lines[-1]
                        before = "\n".join(content_lines[:-1]) if len(content_lines) > 2 else content_lines[-2]
                    elif len(content_lines) == 1:
                        before = content_lines[0]
            
            changes.append({
                "seq": seq,
                "date": date,
                "project": project,
                "before": before,
                "after": after,
                "source": source,
            })
        else:
            i += 1
    
    return changes


def parse_simple_list(lines: List[str], name_field: str = "name") -> List[Dict]:
    """
    解析简单的序号列表（如资质证书、行政许可）
    格式：1 xxxx 2 yyyy
    """
    items = []
    buffer = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 新条目以数字序号开头
        if re.match(r"^\d+\s+", line):
            if buffer:
                items.append({name_field: buffer.strip()})
            buffer = re.sub(r"^\d+\s+", "", line)
        else:
            buffer += " " + line
    
    if buffer:
        items.append({name_field: buffer.strip()})
    
    return items
