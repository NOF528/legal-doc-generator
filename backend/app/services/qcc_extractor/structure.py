"""
文档结构解析模块
负责：识别目录结构、定位章节内容区块、区分目录引用和实际内容
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class Section:
    """文档章节节点"""
    number: str           # 如 "2.2"
    title: str            # 如 "股东信息"
    page: int = 0         # 目录中标注的页码
    count: int = 0        # 括号里的数量，如 (12)
    children: List['Section'] = field(default_factory=list)
    content_start: int = 0  # 在全文中的实际内容起始位置
    content_end: int = 0    # 在全文中的实际内容结束位置


class DocumentStructureParser:
    """
    解析企查查报告的目录结构和章节位置
    """
    
    # 目录行匹配："2.2 股东信息 (12)................................................ 6"
    TOC_PATTERN = re.compile(
        r"^(\d+(?:\.\d+)+)\s+([^\.\n]{2,50}?)\s*(?:\((\d+)\))?\s*\.{3,}\s*(\d+)\s*$"
    )
    
    # 内容页章节标题："2.2 股东信息  (12)"
    CONTENT_SECTION_PATTERN = re.compile(
        r"^(\d+(?:\.\d+)+)\s+([^\(]{2,50}?)\s*(?:\((\d+)\))?\s*$"
    )
    
    def __init__(self, full_text: str):
        self.full_text = full_text
        self.sections: List[Section] = []
        self._build_toc()
        self._locate_content()
    
    def _build_toc(self):
        """
        从文本中提取目录结构
        企查查目录通常在前5页
        """
        # 找到目录区域（从第一个 "1 " 开始到 "1 企业概要" 之前）
        # 实际上目录可能跨多页，我们用正则逐行匹配
        lines = self.full_text.split("\n")
        
        for line in lines:
            line = line.strip()
            m = self.TOC_PATTERN.match(line)
            if m:
                section = Section(
                    number=m.group(1).strip(),
                    title=m.group(2).strip(),
                    page=int(m.group(4)) if m.group(4) else 0,
                    count=int(m.group(3)) if m.group(3) else 0,
                )
                self.sections.append(section)
    
    def _locate_content(self):
        """
        为每个目录章节找到实际内容在全文中的位置
        """
        for i, section in enumerate(self.sections):
            # 找该章节在全文中的所有出现位置
            positions = self._find_section_positions(section)
            
            if not positions:
                continue
            
            # 策略：选择不是目录引用、且后面紧跟实际数据/描述的位置
            best_pos = self._select_best_position(section, positions)
            section.content_start = best_pos
            
            # 结束位置：下一个章节的开始位置，或全文末尾
            if i + 1 < len(self.sections):
                next_positions = self._find_section_positions(self.sections[i + 1])
                if next_positions:
                    next_best = self._select_best_position(self.sections[i + 1], next_positions)
                    section.content_end = next_best
                else:
                    section.content_end = len(self.full_text)
            else:
                section.content_end = len(self.full_text)
    
    def _find_section_positions(self, section: Section) -> List[int]:
        """找到章节标题在全文中的所有位置"""
        # 构建多种可能的标题格式
        patterns = [
            f"{section.number} {section.title}",
        ]
        
        positions = []
        for pat in patterns:
            start = 0
            while True:
                idx = self.full_text.find(pat, start)
                if idx == -1:
                    break
                positions.append(idx)
                start = idx + 1
        
        # 去重排序
        return sorted(list(set(positions)))
    
    def _select_best_position(self, section: Section, positions: List[int]) -> int:
        """
        从多个出现位置中选择最可能是实际内容页的位置
        """
        if len(positions) == 1:
            return positions[0]
        
        scored = []
        for pos in positions:
            score = 0
            preview = self.full_text[pos:pos + 300]
            
            # 加分项：后面有表头关键词
            if "序号" in preview:
                score += 10
            if "企业名称" in preview or "股东" in preview:
                score += 5
            if "日期" in preview or "状态" in preview:
                score += 3
            
            # 加分项：不在目录页特征区域（后面紧跟大量点号）
            if "...." not in preview[:100]:
                score += 8
            
            # 加分项：附近没有 "---PAGE_X---" 且X很小（目录通常在前面几页）
            page_markers = re.findall(r"---PAGE_(\d+)---", self.full_text[max(0, pos-200):pos+300])
            if page_markers:
                page_no = int(page_markers[-1])
                if page_no > 5:  # 内容通常在5页以后
                    score += 5
            
            scored.append((score, pos))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]
    
    def get_section(self, number: str) -> Optional[Section]:
        """按章节编号获取"""
        for s in self.sections:
            if s.number == number:
                return s
        return None
    
    def get_section_by_title(self, title_keyword: str) -> Optional[Section]:
        """按标题关键词模糊匹配"""
        for s in self.sections:
            if title_keyword in s.title:
                return s
        return None
    
    def get_content_block(self, number: str) -> str:
        """获取指定章节的实际内容文本"""
        section = self.get_section(number)
        if not section or section.content_start == 0:
            return ""
        return self.full_text[section.content_start:section.content_end]
    
    def get_all_sections(self) -> List[Section]:
        return self.sections
