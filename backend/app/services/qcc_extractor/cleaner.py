"""
页眉页脚清洗模块
"""
import re
from typing import List


class PageHeaderCleaner:
    """
    清洗企查查报告每页的页眉页脚干扰内容
    """
    
    # 常见页眉模式
    HEADER_PATTERNS = [
        re.compile(r"^\s*联系电话：\d{3}-\d{8}\s*$"),
        re.compile(r"^\s*企查查科技股份有限公司\s+\d+\s*$"),
        re.compile(r"^\s*企业信用报告专业版\s*$"),
    ]
    
    # 页脚模式（二维码说明等长文本通常在首页）
    FOOTER_KEYWORDS = [
        "报告验真编号",
        "验真码说明",
        "企查查 APP扫一扫",
        "未经报告权属人同意",
    ]
    
    def __init__(self, company_name: str = None):
        self.company_name = company_name
    
    def clean(self, text: str) -> str:
        """
        清洗单页文本
        """
        lines = text.split("\n")
        cleaned = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # 跳过页眉行
            if self._is_header(stripped):
                continue
            
            # 跳过页脚说明
            if self._is_footer(stripped):
                continue
            
            cleaned.append(stripped)
        
        return "\n".join(cleaned)
    
    def clean_all(self, page_texts: List[str], include_page_markers: bool = False) -> str:
        """
        清洗所有页面并拼接
        
        :param include_page_markers: 是否包含 ---PAGE_X--- 标记（用于调试）
        """
        cleaned_pages = []
        for i, text in enumerate(page_texts):
            cleaned = self.clean(text)
            if cleaned.strip():
                if include_page_markers:
                    cleaned_pages.append(f"---PAGE_{i+1}---\n{cleaned}")
                else:
                    cleaned_pages.append(cleaned)
        return "\n".join(cleaned_pages)
    
    def _is_header(self, line: str) -> bool:
        for pattern in self.HEADER_PATTERNS:
            if pattern.match(line):
                return True
        # 如果知道企业名称，且该行就是单独的企业名称，也可能是页眉
        if self.company_name and line == self.company_name and len(line) < 40:
            return True
        return False
    
    def _is_footer(self, line: str) -> bool:
        for kw in self.FOOTER_KEYWORDS:
            if kw in line:
                return True
        return False


def remove_header_from_table_row(line: str) -> str:
    """
    清理表格行中嵌入的页眉残片
    """
    # 移除嵌入在行中的页头部份
    line = re.sub(r"联系电话：\d{3}-\d{8}", "", line)
    line = re.sub(r"企查查科技股份有限公司\s+\d+", "", line)
    line = re.sub(r"企业信用报告专业版", "", line)
    line = re.sub(r"---PAGE_\d+---", "", line)
    return line.strip()


def merge_broken_dates(text: str) -> str:
    """
    修复跨页断开的日期，如 "2024. -03-13" -> "2024-03-13"
    """
    # 修复点号+空格+横杠开头的日期
    text = re.sub(r"(\d{4})\.\s+-", r"\1-", text)
    # 修复多余的空格在日期中
    text = re.sub(r"(\d{4})\s*-\s*(\d{2})\s*-\s*(\d{2})", r"\1-\2-\3", text)
    return text
