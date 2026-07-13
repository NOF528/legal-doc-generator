"""
变更记录解析与历史沿革生成模块
按日期分组，支持增资/减资/股权转让及组合情况
合并显示：同一次变更的所有股东列在一个段落中
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from .templates import (
    render_equity_transfer, 
    render_capital_increase, 
    render_capital_reduction
)


class ChangeType(Enum):
    """变更类型"""
    EQUITY_TRANSFER = "股权转让"
    CAPITAL_INCREASE = "增资"
    CAPITAL_DECREASE = "减资"


@dataclass
class ChangeGroup:
    """同一日期的变更组"""
    date: str
    raw_date: str
    records: List[Dict]
    change_types: List[ChangeType] = field(default_factory=list)
    exits: List[Dict] = field(default_factory=list)
    enters: List[Dict] = field(default_factory=list)
    capital_before: str = ""
    capital_after: str = ""
    is_history_relevant: bool = False


class ChangeGrouper:
    """变更记录分组器"""
    
    def group_by_date(self, raw_changes: List[Dict]) -> List[ChangeGroup]:
        """按日期分组"""
        date_groups = defaultdict(list)
        
        for record in raw_changes:
            raw_date = record.get("date", "")
            if raw_date:
                date_groups[raw_date].append(record)
        
        groups = []
        for raw_date, records in date_groups.items():
            formatted_date = self._format_date(raw_date)
            group = ChangeGroup(
                date=formatted_date,
                raw_date=raw_date,
                records=records
            )
            groups.append(group)
        
        groups.sort(key=lambda x: x.raw_date, reverse=True)
        return groups
    
    def _format_date(self, date_str: str) -> str:
        """格式化日期"""
        if not date_str:
            return ""
        
        match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}年{int(month)}月{int(day)}日"
        
        match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}年{int(month)}月{int(day)}日"
        
        return date_str


class ChangeTypeAnalyzer:
    """变更类型分析器"""
    
    def analyze(self, group: ChangeGroup) -> ChangeGroup:
        """分析变更组"""
        group.change_types = []
        
        # 1. 分析注册资本变更
        has_capital_change = False
        for record in group.records:
            project = record.get("project", "")
            if "注册资本" in project:
                has_capital_change = True
                before, after = self._parse_capital(record.get("before", ""), record.get("after", ""), project)
                if before and after:
                    group.capital_before = before
                    group.capital_after = after
                    
                    before_num = self._extract_number(before)
                    after_num = self._extract_number(after)
                    
                    if after_num > before_num:
                        if ChangeType.CAPITAL_INCREASE not in group.change_types:
                            group.change_types.append(ChangeType.CAPITAL_INCREASE)
                    elif after_num < before_num:
                        if ChangeType.CAPITAL_DECREASE not in group.change_types:
                            group.change_types.append(ChangeType.CAPITAL_DECREASE)
                break
        
        # 2. 分析投资人变更
        group.exits, group.enters = self._extract_shareholder_changes(group.records)
        
        # 3. 判断是否有股权转让
        has_equity_transfer = len(group.exits) > 0 and len(group.enters) > 0
        
        # 4. 确定是否为历史沿革相关
        if has_capital_change or group.exits or group.enters:
            group.is_history_relevant = True
        
        # 5. 组合判断
        if has_equity_transfer:
            if ChangeType.EQUITY_TRANSFER not in group.change_types:
                group.change_types.append(ChangeType.EQUITY_TRANSFER)
        
        # 如果只有退出方或只有新进方，但有投资人变更项目，也视为股权转让
        if (group.exits or group.enters) and ChangeType.EQUITY_TRANSFER not in group.change_types:
            has_investor_change = any("投资人" in r.get("project", "") for r in group.records)
            if has_investor_change:
                group.change_types.append(ChangeType.EQUITY_TRANSFER)
        
        # 如果没有识别到变更类型但有变更记录，默认标记为股权转让
        if not group.change_types and group.records:
            # 检查是否有投资人变更项目
            has_investor_change = any("投资人" in r.get("project", "") for r in group.records)
            if has_investor_change:
                group.change_types.append(ChangeType.EQUITY_TRANSFER)
                group.is_history_relevant = True
        
        # 6. 如果只有注册资本变更但无投资人信息，标记为需要补充投资人
        if has_capital_change and not group.exits and not group.enters:
            # 这种情况下需要后续从股东信息中补充
            pass
        
        return group
    
    def _parse_capital(self, before_text: str, after_text: str, project: str) -> Tuple[str, str]:
        """解析注册资本"""
        before_match = re.search(r'(\d[\d,]*\.?\d*)\s*万元', str(before_text))
        after_match = re.search(r'(\d[\d,]*\.?\d*)\s*万元', str(after_text))
        
        if before_match and after_match:
            return before_match.group(1) + "万元", after_match.group(1) + "万元"
        
        numbers = re.findall(r'(\d[\d,]*\.?\d*)\s*万元', project)
        if len(numbers) >= 2:
            return numbers[0] + "万元", numbers[1] + "万元"
        
        numbers = re.findall(r'\d[\d,]*\.?\d*', project.replace(',', ''))
        if len(numbers) >= 2:
            return numbers[0] + "万元", numbers[1] + "万元"
        
        return "", ""
    
    def _extract_number(self, text: str) -> float:
        """提取数字"""
        text = str(text).replace(',', '').replace('，', '')
        numbers = re.findall(r'\d+\.?\d*', text)
        if numbers:
            return float(numbers[0])
        return 0
    
    def _extract_shareholder_changes(self, records: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """提取股东变更"""
        exits = []
        enters = []
        
        for record in records:
            after = self._clean_text(record.get("after", ""))
            before = self._clean_text(record.get("before", ""))
            
            # 方式1：【退出】【新进】
            # 改进策略：先找到带标记的完整文本，然后提取最后一个完整的企业名称
            # 匹配包含【退出】或【新进】的完整文本段
            exit_matches = list(re.finditer(r"([^【】]*?)【退出】", after))
            enter_matches = list(re.finditer(r"([^【】]*?)【新进】", after))
            
            for match in exit_matches:
                text_before = match.group(1)
                # 从文本中提取最后一个完整的企业名称
                name = self._extract_last_company_name(text_before)
                if name and not self._is_invalid_name(name):
                    exits.append({"name": name})
            
            for match in enter_matches:
                text_before = match.group(1)
                # 从文本中提取最后一个完整的企业名称
                name = self._extract_last_company_name(text_before)
                if name and not self._is_invalid_name(name):
                    enters.append({"name": name})
            
            # 方式2：持股+/-%（多行格式）
            # 支持更长的名称匹配
            before_exit_pattern = r"([^\n（）]{2,100}?)（持股-([\d.]+)%\s*）"
            for match in re.findall(before_exit_pattern, before):
                name, ratio = match
                name = self._clean_name(name.strip())
                if name and len(name) > 1 and "持股" not in name and not self._is_invalid_name(name):
                    exits.append({"name": name, "ratio": str(abs(float(ratio)))})
            
            after_enter_pattern = r"([^\n（）]{2,100}?)（持股\+([\d.]+)%）"
            for match in re.findall(after_enter_pattern, after):
                name, ratio = match
                name = self._clean_name(name.strip())
                if name and len(name) > 1 and "持股" not in name and not self._is_invalid_name(name):
                    enters.append({"name": name, "ratio": ratio})
            
            # 方式3：持股+/-%（单行格式）
            # 放宽名称长度限制
            ratio_pattern = r"([^【】，、\s:：]{2,100}?)\s+出资([\d,\.]+)万元\s+持股\s*([+-]\d+\.?\d*)%"
            matches = re.findall(ratio_pattern, after)
            
            if not matches:
                # 支持更长的企业名称
                # 注意：排除【】，、　:：（）等字符，避免匹配到标记或空括号
                ratio_pattern2 = r"([^【】，、\s:：（）\(\)]{2,100}?)\s*（?\s*持股\s*([+-]\d+\.?\d*)%\s*）?"
                for match in re.findall(ratio_pattern2, after):
                    name, ratio_change = match
                    name_clean = self._clean_name(name)
                    if not name_clean or "出资" in name_clean or "持股" in name_clean or self._is_invalid_name(name_clean):
                        continue
                    
                    ratio_val = float(ratio_change)
                    info = self._extract_shareholder_info(name_clean, after, before)
                    
                    if ratio_val < 0:
                        exits.append({"name": name_clean, "ratio": str(abs(ratio_val)), "capital": info.get("capital", "")})
                    elif ratio_val > 0:
                        enters.append({"name": name_clean, "ratio": str(ratio_val), "capital": info.get("capital", "")})
            else:
                for match in matches:
                    name, capital, ratio_change = match
                    name_clean = self._clean_name(name)
                    if not name_clean or "出资" in name_clean or "持股" in name_clean:
                        continue
                    
                    ratio_val = float(ratio_change)
                    if ratio_val < 0:
                        exits.append({"name": name_clean, "ratio": str(abs(ratio_val)), "capital": capital})
                    elif ratio_val > 0:
                        enters.append({"name": name_clean, "ratio": str(ratio_val), "capital": capital})
        
        return self._deduplicate(exits), self._deduplicate(enters)
    
    def _extract_shareholder_info(self, name: str, after: str, before: str) -> Dict:
        """提取股东信息"""
        info = {}
        combined = f"{after} {before}"
        match = re.search(rf"{re.escape(name)}\s+出资([\d,\.]+)万元", combined)
        if match:
            info["capital"] = match.group(1)
        return info
    
    def _extract_all_shareholder_names(self, text: str) -> List[str]:
        """从文本中提取所有可能的股东名称（用于早期企查查格式）"""
        names = []
        if not text:
            return names
        
        # 常见的企业类型后缀
        company_suffixes = ['有限公司', '有限责任公司', '股份有限公司', '合伙企业（有限合伙）', 
                          '有限合伙）', '（有限合伙）', '普通合伙）', '（普通合伙）', '分公司']
        
        # 尝试匹配包含企业类型后缀的名称
        for suffix in company_suffixes:
            # 匹配前面有2-100个字符，后面跟着后缀的模式
            pattern = r'([^【】，、\s:：]{2,100}?' + re.escape(suffix) + r')'
            for match in re.findall(pattern, text):
                name = self._clean_name(match)
                if name and len(name) > 3:
                    names.append(name)
        
        # 尝试匹配自然人姓名（2-4个汉字）
        # 自然人姓名通常在变更记录中不带企业后缀
        # 使用更严格的匹配：2-4个汉字，后面可能跟着职位信息
        person_pattern = r'([\u4e00-\u9fa5]{2,4})(?:（(?:执行董事|监事|经理|总经理)）|$|【)'
        for match in re.findall(person_pattern, text):
            name = self._clean_name(match)
            if name and len(name) >= 2:
                names.append(name)
        
        return self._deduplicate_simple(names)
    
    def _deduplicate_simple(self, names: List[str]) -> List[str]:
        """简单去重"""
        seen = set()
        result = []
        for name in names:
            if name and name not in seen:
                seen.add(name)
                result.append(name)
        return result
    
    def _deduplicate(self, shareholders: List[Dict]) -> List[Dict]:
        """去重"""
        seen = set()
        result = []
        for s in shareholders:
            name = s.get("name", "")
            if name and name not in seen:
                seen.add(name)
                result.append(s)
        return result
    
    def _clean_name(self, name: str) -> str:
        """清洗名称"""
        if not name:
            return ""
        
        # 去掉末尾的标记（如【新进】【退出】等）
        name = re.sub(r'【[^】]*】$', '', name)
        name = re.sub(r'\[[^\]]*\]$', '', name)
        
        # 去掉职位信息
        name = re.split(r'[:：]', name)[0]
        name = re.sub(r'(监事|董事|经理|执行董事|总经理|法定代表人)$', '', name)
        
        # 清理可能的噪声字符
        name = re.sub(r'^\*+', '', name)
        name = name.strip()
        
        # 修复不完整的企业名称：如果名称以合伙企业类型结尾但没有前缀
        company_suffixes = ['合伙企业（有限合伙）', '有限合伙）', '有限公司', '有限责任公司', '股份有限公司']
        for suffix in company_suffixes:
            if name.endswith(suffix) and len(name) <= len(suffix) + 5:
                # 名称可能不完整，标记为需要补充
                pass
        
        return name
    
    def _is_invalid_name(self, name: str) -> bool:
        """检查名称是否无效（如标记、占位符等）"""
        if not name:
            return True
        
        name = name.strip()
        
        # 无效名称列表（完全匹配）
        invalid_exact = [
            '【退出】', '【新进】', '【名称变更】',
            '（有限合伙）', '有限合伙）', '普通合伙）',
            '（普通合伙）', '（有限合伙', '（', '）'
        ]
        
        # 如果名称完全匹配无效列表
        if name in invalid_exact:
            return True
        
        # 如果名称只包含标记字符
        if re.match(r'^[【】\(\)（）\[\]]+$', name):
            return True
        
        # 如果名称太短（少于2个字符）
        if len(name) < 2:
            return True
        
        # 如果名称只包含关键字而没有实际内容
        if name in ['出资', '持股', '万元', '%', '新进', '退出', '名称变更']:
            return True
        
        return False
    
    def _extract_last_company_name(self, text: str) -> str:
        """
        从文本中提取最后一个完整的企业名称
        企业名称通常以特定后缀结尾
        """
        if not text:
            return ""
        
        # 企业名称后缀（按优先级排序）
        suffixes = [
            '合伙企业（有限合伙）',
            '（有限合伙）',
            '有限合伙）',
            '有限公司',
            '有限责任公司',
            '股份有限公司',
            '普通合伙）',
            '（普通合伙）',
        ]
        
        # 尝试匹配最后一个完整的企业名称
        # 策略：从后往前找后缀，然后向前提取名称
        for suffix in suffixes:
            if suffix in text:
                # 找到最后一个后缀的位置
                last_idx = text.rfind(suffix)
                if last_idx >= 0:
                    # 从后缀向前查找名称的开始
                    # 名称开始于：空格、换行、或者字符串开头
                    name_start = 0
                    for i in range(last_idx - 1, -1, -1):
                        if text[i] in ' \n\r\t【】（）()':
                            name_start = i + 1
                            break
                    
                    name = text[name_start:last_idx + len(suffix)]
                    name = self._clean_name(name)
                    # 确保名称有效：不只包含后缀，且长度合理
                    if name and len(name) > len(suffix) + 1 and not self._is_invalid_name(name):
                        return name
        
        # 如果没有找到企业后缀，尝试匹配自然人姓名（2-4个汉字）
        # 自然人姓名通常在文本末尾，前面可能有职位信息
        person_match = re.search(r'([\u4e00-\u9fa5]{2,4})(?:（[^）]*）)?$', text.strip())
        if person_match:
            name = person_match.group(1)
            if name and len(name) >= 2 and not self._is_invalid_name(name):
                return name
        
        return ""
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        text = re.sub(r"企查查科技股份有限公司\s+\d+", "", text)
        text = re.sub(r"联系电话：\d{3}-\d{8}", "", text)
        text = re.sub(r"工商公示", "", text)
        text = text.replace("\n", " ")
        return text.strip()


class HistoryEvolutionGenerator:
    """历史沿革生成器"""
    
    def __init__(self, company_name: str = ""):
        self.company_name = company_name
        self.grouper = ChangeGrouper()
        self.analyzer = ChangeTypeAnalyzer()
    
    def process_changes(self, raw_changes: List[Dict]) -> List[ChangeGroup]:
        """处理变更记录"""
        groups = self.grouper.group_by_date(raw_changes)
        for group in groups:
            self.analyzer.analyze(group)
        return [g for g in groups if g.is_history_relevant]
    
    def generate_sequence(self, group: ChangeGroup) -> str:
        """生成序号"""
        if not group.change_types:
            return f"{group.date} 变更"
        type_names = [t.value for t in group.change_types]
        return f"{group.date} {'、'.join(type_names)}"
    
    def generate_text(self, groups: List[ChangeGroup]) -> str:
        """生成文本 - 合并显示"""
        if not groups:
            return f"{self.company_name}自设立以来，股权结构未发生重大变更。"
        
        sections = []
        for group in groups:
            sequence = self.generate_sequence(group)
            sections.append(f"【{sequence}】")
            sections.append("")
            
            if not group.change_types:
                group.change_types = [ChangeType.EQUITY_TRANSFER]
            
            # 构建合并后的股东列表（用于最后的股权结构表格）
            all_shareholders = self._build_all_shareholders(group)
            
            # 按顺序生成各类型内容
            for change_type in group.change_types:
                try:
                    if change_type == ChangeType.EQUITY_TRANSFER and group.exits and group.enters:
                        # 股权转让 - 所有转让合并成一段
                        text = self._generate_merged_equity_text(group)
                        if text:
                            sections.append(text)
                            sections.append("")
                    
                    elif change_type == ChangeType.CAPITAL_INCREASE:
                        # 增资 - 所有股东合并成一段
                        text = self._generate_merged_increase_text(group)
                        if text:
                            sections.append(text)
                            sections.append("")
                    
                    elif change_type == ChangeType.CAPITAL_DECREASE:
                        # 减资
                        text = self._generate_merged_reduction_text(group)
                        if text:
                            sections.append(text)
                            sections.append("")
                
                except Exception as e:
                    print(f"生成内容时出错: {e}")
                    continue
            
            # 最后统一显示股权结构（只显示一次）
            if all_shareholders:
                structure_text = self._generate_shareholder_structure(group.date, all_shareholders)
                sections.append(structure_text)
                sections.append("")
        
        return "\n".join(sections)
    
    def _build_all_shareholders(self, group: ChangeGroup) -> List[Dict]:
        """构建所有股东列表（变更后）"""
        shareholders = []
        
        # 如果有新进股东，使用新进股东列表
        if group.enters:
            for enter in group.enters:
                shareholders.append({
                    "name": enter.get("name", "【**】"),
                    "amount": enter.get("capital", "【**】"),
                    "ratio": enter.get("ratio", "【**】")
                })
        
        return shareholders
    
    def _generate_merged_equity_text(self, group: ChangeGroup) -> str:
        """生成合并的股权转让文本"""
        lines = [
            f"{group.date}，公司召开股东会并作出决议：",
            ""
        ]
        
        # 构建转让语句列表
        transfer_statements = []
        for exit_info in group.exits:
            # 匹配转让方和受让方
            for enter_info in group.enters:
                transferor = exit_info.get("name", "【**】")
                transferee = enter_info.get("name", "【**】")
                ratio = exit_info.get("ratio", "【**】")
                capital = exit_info.get("capital", "【**】")
                price = "【**】"
                
                stmt = f"同意股东{transferor}将其持有的公司{ratio}%的股权（对应注册资本人民币{capital}万元）以人民币{price}万元的对价转让给{transferee}"
                transfer_statements.append(stmt)
                break  # 简单一对一匹配
        
        if transfer_statements:
            lines.append("；".join(transfer_statements) + "；")
            lines.append("")
        
        # 签署协议
        if group.exits and group.enters:
            lines.append(f"{group.date}，各方分别就上述股权转让事项签署了《股权转让协议》；")
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_merged_increase_text(self, group: ChangeGroup) -> str:
        """生成合并的增资文本"""
        lines = [
            f"{group.date}，公司召开股东会并作出决议：",
            f"公司注册资本由人民币{self._extract_capital(group.capital_before)}万元变更为人民币{self._extract_capital(group.capital_after)}万元。",
            ""
        ]
        
        # 构建增资语句列表
        increase_statements = []
        
        # 如果有新进股东，使用新进股东列表
        if group.enters:
            for enter in group.enters:
                investor = enter.get("name", "【**】")
                investment = "【**】"
                capital = enter.get("capital", "【**】")
                
                stmt = f"同意{investor}以人民币{investment}万元认购公司新增的注册资本人民币{capital}万元"
                increase_statements.append(stmt)
        else:
            # 如果没有识别到投资人，但有注册资本变更，添加占位符
            # 这种情况下需要用户手动填写投资人信息
            increase_statements.append("同意【**】以人民币【**】万元认购公司新增的注册资本人民币【**】万元")
        
        if increase_statements:
            lines.append("；".join(increase_statements) + "；")
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_merged_reduction_text(self, group: ChangeGroup) -> str:
        """生成合并的减资文本"""
        lines = [
            f"{group.date}，公司召开股东会并作出决议：",
            f"同意将原注册资本{self._extract_capital(group.capital_before)}万元变更为{self._extract_capital(group.capital_after)}万元，并对公司章程进行相应修改。",
            f"{self.company_name}本次注册资本{self._extract_capital(group.capital_before)}万元变更为{self._extract_capital(group.capital_after)}万元由全体股东按照同比例减资。",
            "",
            f"{group.date}，公司就上述减资事宜于【**】刊登了减资公告：经股东会作出决议，拟将公司注册资本由人民币{self._extract_capital(group.capital_before)}万元减至人民币{self._extract_capital(group.capital_after)}万元。根据《中华人民共和国公司法》等相关法律、法规的规定，公司特此通知债权人，请公司债权人自本公告见报之日起45日内到本公司申报债权。本公司承诺对原注册资本内的债务承担清偿责任，股东承担连带责任。",
            ""
        ]
        
        return "\n".join(lines)
    
    def _generate_shareholder_structure(self, date: str, shareholders: List[Dict]) -> str:
        """生成股权结构表格"""
        lines = [
            f"本次增资和股权转让完成后，{self.company_name}的股权结构如下：",
            "",
            "| 序号 | 股东名称/姓名 | 出资额（万元） | 出资比例 |",
            "|:---:|:---:|:---:|:---:|"
        ]
        
        total_capital = "【**】"
        total_ratio = 0.0
        
        for i, s in enumerate(shareholders, 1):
            name = s.get("name", "【**】")
            amount = s.get("amount", "【**】")
            ratio = s.get("ratio", "【**】")
            lines.append(f"| {i} | {name} | {amount} | {ratio}% |")
            
            # 尝试累加比例
            try:
                total_ratio += float(ratio)
            except:
                pass
        
        lines.append(f"| 合计 | - | {total_capital} | 100.0000% |")
        lines.append("")
        lines.append(f"{date}，{self.company_name}完成了上述变更的工商变更登记程序。")
        
        return "\n".join(lines)
    
    def _extract_capital(self, text: str) -> str:
        """提取资本数字"""
        if not text:
            return "【**】"
        numbers = re.findall(r'[\d,\.]+', str(text).replace(',', ''))
        return numbers[0] if numbers else "【**】"


def extract_history_evolution(raw_changes: List[Dict], company_name: str) -> Dict:
    """主入口"""
    generator = HistoryEvolutionGenerator(company_name)
    groups = generator.process_changes(raw_changes)
    text = generator.generate_text(groups)
    
    category_stats = {}
    for g in groups:
        type_key = "、".join([t.value for t in g.change_types]) if g.change_types else "其他变更"
        category_stats[type_key] = category_stats.get(type_key, 0) + 1
    
    changes = []
    for g in groups:
        changes.append({
            "date": g.date,
            "category": "、".join([t.value for t in g.change_types]) if g.change_types else "其他变更",
            "type": "、".join([t.value for t in g.change_types]) if g.change_types else "其他变更",
            "project": "、".join([r.get("project", "") for r in g.records]),
            "transfer_from": g.exits[0].get("name", "") if g.exits else "",
            "transfer_to": g.enters[0].get("name", "") if g.enters else "",
            "transfer_ratio": g.exits[0].get("ratio", "") if g.exits else "",
            "capital_before": g.capital_before,
            "capital_after": g.capital_after,
            "exits": g.exits,
            "enters": g.enters,
            "sequence": generator.generate_sequence(g),
        })
    
    return {
        "text": text,
        "markdown": text,
        "changes_count": len(groups),
        "changes": changes,
        "category_stats": category_stats,
    }
