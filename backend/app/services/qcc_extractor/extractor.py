"""
企查查 PDF 报告主提取器
"""
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

from .cleaner import PageHeaderCleaner
from .structure import DocumentStructureParser
from .tables import (
    TableExtractor,
    parse_shareholder_line,
    parse_key_person_line,
    parse_investment_line,
    parse_branch_line,
    parse_change_record,
)


class QCCReportExtractor:
    """
    企查查报告通用提取器
    """
    
    def __init__(self):
        self.raw_text = ""
        self.structure = None
        self.company_name = ""
        self.report_meta = {}
    
    def extract(self, pdf_path: str) -> Dict:
        """
        主入口：提取 PDF 中所有结构化数据
        """
        if PdfReader is None:
            raise ImportError("请先安装 PyPDF2: pip install PyPDF2")
        
        reader = PdfReader(pdf_path)
        num_pages = len(reader.pages)
        
        # 先提取首页，获取企业名称
        first_page_text = reader.pages[0].extract_text() or ""
        self.company_name = self._extract_company_name(first_page_text)
        
        # 清洗并拼接所有页面
        cleaner = PageHeaderCleaner(company_name=self.company_name)
        page_texts = [p.extract_text() or "" for p in reader.pages]
        self.raw_text = cleaner.clean_all(page_texts, include_page_markers=False)
        
        # 解析文档结构
        self.structure = DocumentStructureParser(self.raw_text)
        
        # 提取元数据
        self.report_meta = self._extract_meta(reader.metadata or {}, num_pages)
        
        # 构建标准化输出
        result = {
            "report_meta": self.report_meta,
            "company_profile": self._extract_company_profile(),
            "basic_info": self._extract_basic_info(),
            "legal_risks": self._extract_legal_risks(),
            "business_risks": self._extract_business_risks(),
            "intellectual_property": self._extract_ip(),
            "business_info": self._extract_business_info(),
            "raw_structure": {
                "sections": [
                    {
                        "number": s.number,
                        "title": s.title,
                        "page": s.page,
                        "count": s.count,
                    }
                    for s in self.structure.get_all_sections()
                ]
            }
        }
        
        return result
    
    def _extract_company_name(self, first_page_text: str) -> str:
        """从首页提取企业名称"""
        lines = [l.strip() for l in first_page_text.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            if "企业信用报告" in line or "专业版" in line:
                if i + 1 < len(lines):
                    candidate = lines[i + 1]
                    if len(candidate) > 4 and "本报告" not in candidate:
                        return candidate
        m = re.search(r"专业版\s*\n\s*([^\n]{4,50})\s*\n", first_page_text)
        if m:
            return m.group(1).strip()
        return ""
    
    def _extract_meta(self, metadata: Dict, num_pages: int) -> Dict:
        """提取报告元数据"""
        meta = {
            "company_name": self.company_name,
            "report_type": "企业信用报告专业版",
            "report_date": None,
            "report_no": None,
            "total_pages": num_pages,
            "producer": metadata.get("/Producer") or metadata.get("Producer", ""),
            "extracted_at": datetime.now().isoformat(),
        }
        
        # 从首页提取报告生成时间和编号
        first_lines = self.raw_text.split("\n")[:30]
        text = "\n".join(first_lines)
        
        m = re.search(r"本报告生成时间为\s*(\d{4}\s*年\d{1,2}\s*月\d{1,2}\s*日\s*\d{2}:\d{2}:\d{2})", text)
        if m:
            meta["report_date"] = m.group(1).replace(" ", "")
        
        m = re.search(r"报告编号[：:]\s*(\d+)", text)
        if m:
            meta["report_no"] = m.group(1)
        
        return meta
    
    def _extract_company_profile(self) -> Dict:
        """提取企业概要（企查分、联系信息）"""
        profile = {
            "qcc_score": {},
            "contact_info": {},
        }
        
        block = self.structure.get_content_block("1")
        if not block:
            block = self.raw_text[:15000]  # 默认取前部
        
        # 联系信息
        patterns = {
            "phone": r"电\s*话[:：]\s*([^\n]+)",
            "email": r"邮\s*箱[:：]\s*([^\n]+)",
            "website": r"网\s*址[:：]\s*([^\n]+)",
            "address": r"地\s*址[:：]\s*([^\n]+)",
        }
        for key, pat in patterns.items():
            m = re.search(pat, block)
            if m:
                profile["contact_info"][key] = m.group(1).strip()
        
        return profile
    
    def _extract_basic_info(self) -> Dict:
        """提取基本信息章节（2.x）"""
        info = {
            "registration": {},
            "shareholders": [],
            "key_persons": [],
            "investments": [],
            "controlled_enterprises": [],
            "change_history": [],
            "branches": [],
            "annual_reports": [],
        }
        
        # 工商信息（2.1）
        block_21 = self.structure.get_content_block("2.1")
        if block_21:
            info["registration"] = self._parse_registration(block_21)
        
        # 股东信息（2.2）
        block_22 = self.structure.get_content_block("2.2")
        if block_22:
            lines = [l.strip() for l in block_22.split("\n") if l.strip()]
            extractor = TableExtractor(lines, ["序号", "发起人名称", "持股比例"])
            info["shareholders"] = extractor.extract(parse_shareholder_line)
        
        # 主要人员（2.3）
        block_23 = self.structure.get_content_block("2.3")
        if block_23:
            lines = [l.strip() for l in block_23.split("\n") if l.strip()]
            extractor = TableExtractor(lines, ["序号", "姓名", "职务"])
            info["key_persons"] = extractor.extract(parse_key_person_line)
        
        # 对外投资（2.4）
        block_24 = self.structure.get_content_block("2.4")
        if block_24:
            lines = [l.strip() for l in block_24.split("\n") if l.strip()]
            extractor = TableExtractor(lines, ["序号", "被投资企业名称"])
            info["investments"] = extractor.extract(parse_investment_line)
        
        # 分支机构（2.8）
        block_28 = self.structure.get_content_block("2.8")
        if block_28:
            lines = [l.strip() for l in block_28.split("\n") if l.strip()]
            extractor = TableExtractor(lines, ["序号", "企业名称", "负责人"])
            info["branches"] = extractor.extract(parse_branch_line)
        
        # 变更记录（2.7）
        block_27 = self.structure.get_content_block("2.7")
        if block_27:
            lines = [l.strip() for l in block_27.split("\n") if l.strip()]
            info["change_history"] = parse_change_record(lines)
        
        return info
    
    def _parse_registration(self, text: str) -> Dict:
        """解析工商注册信息"""
        info = {}
        patterns = {
            "企业名称": r"企业名称\s*([^\n]{4,40}?)(?=\s*曾用名|\s*统一社会信用代码|\n)",
            "统一社会信用代码": r"统一社会信用代码\s*([A-Z0-9]{18})",
            "工商注册号": r"工商注册号\s*([A-Z0-9]+)",
            "法定代表人": r"法定代表人\s*([^\n]{2,20}?)(?=\s*组织机构代码|\s*注册资本|\n)",
            "注册资本": r"注册资本\s*([^\n]{2,30}?)(?=\s*实缴资本|\s*企业类型|\n)",
            "实缴资本": r"实缴资本\s*([^\n]{2,40}?)(?=\s*企业类型|\n)",
            "成立日期": r"成立日期\s*(\d{4}-\d{2}-\d{2})",
            "企业状态": r"登记状态\s*([^\n]{2,20}?)(?=\s*成立日期|\n)",
            "企业类型": r"企业类型\s*([^\n]{2,50}?)(?=\s*登记状态|\n)",
            "登记机关": r"登记机关\s*([^\n]{2,30}?)(?=\s*人员规模|\n)",
            "参保人数": r"参保人数\s*(\d+)",
            "注册地址": r"注册地址\s*([^\n]{5,80}?)(?=\s*经营范围|\n)",
            "营业期限": r"营业期限\s*([^\n]{5,40})",
            "核准日期": r"核准日期\s*(\d{4}-\d{2}-\d{2})",
            "经营范围": r"经营范围\s*([^\n].*?)(?=\n\d+\.\d+|\n---PAGE|$)",
        }
        for key, pat in patterns.items():
            m = re.search(pat, text, re.DOTALL)
            if m:
                info[key] = m.group(1).strip().replace("\n", " ")
        return info
    
    def _extract_legal_risks(self) -> Dict:
        """提取法律风险（4.x）"""
        block = self.structure.get_content_block("4")
        if not block:
            block = self.structure.get_content_block("4.1") or ""
        
        risks = {
            "judicial_cases_count": 0,
            "dishonest_count": 0,
            "executed_persons_count": 0,
            "restricted_consumption_count": 0,
            "judgment_documents_count": 0,
            "court_announcements_count": 0,
            "court_sessions_count": 0,
            "bankruptcy_reorganization_count": 0,
            "equity_freeze_count": 0,
        }
        
        patterns = {
            "judicial_cases_count": r"司法案件\s*\((\d+)\)",
            "dishonest_count": r"失信被执行人\s*\((\d+)\)",
            "executed_persons_count": r"被执行人\s*\((\d+)\)",
            "restricted_consumption_count": r"限制高消费\s*\((\d+)\)",
            "judgment_documents_count": r"裁判文书\s*\((\d+)\)",
            "court_announcements_count": r"法院公告\s*\((\d+)\)",
            "court_sessions_count": r"开庭公告\s*\((\d+)\)",
            "bankruptcy_reorganization_count": r"破产重整\s*\((\d+)\)",
            "equity_freeze_count": r"股权冻结\s*\((\d+)\)",
        }
        
        for key, pat in patterns.items():
            m = re.search(pat, block)
            if m:
                risks[key] = int(m.group(1))
        
        return risks
    
    def _extract_business_risks(self) -> Dict:
        """提取经营风险（5.x）"""
        block = self.structure.get_content_block("5")
        if not block:
            block = self.structure.get_content_block("5.1") or ""
        
        risks = {
            "administrative_penalties_count": 0,
            "abnormal_operations_count": 0,
            "serious_violations_count": 0,
            "equity_pledge_count": 0,
            "chattel_mortgage_count": 0,
            "land_mortgage_count": 0,
        }
        
        patterns = {
            "administrative_penalties_count": r"行政处罚\s*\((\d+)\)",
            "abnormal_operations_count": r"经营异常\s*\((\d+)\)",
            "serious_violations_count": r"严重违法\s*\((\d+)\)",
            "equity_pledge_count": r"股权出质\s*\((\d+)\)",
            "chattel_mortgage_count": r"动产抵押\s*\((\d+)\)",
            "land_mortgage_count": r"土地抵押\s*\((\d+)\)",
        }
        
        for key, pat in patterns.items():
            m = re.search(pat, block)
            if m:
                risks[key] = int(m.group(1))
        
        return risks
    
    def _extract_ip(self) -> Dict:
        """提取知识产权统计（8.x）"""
        block = self.structure.get_content_block("8")
        if not block:
            block = self.structure.get_content_block("8.1") or ""
        
        ip = {
            "trademarks": 0,
            "patents": 0,
            "work_copyrights": 0,
            "software_copyrights": 0,
            "websites": 0,
        }
        
        patterns = {
            "trademarks": r"商标信息\s*\((\d+)\)",
            "patents": r"专利信息\s*\((\d+)\)",
            "work_copyrights": r"作品著作权\s*\((\d+)\)",
            "software_copyrights": r"软件著作权\s*\((\d+)\)",
            "websites": r"备案网站\s*\((\d+)\)",
        }
        
        for key, pat in patterns.items():
            m = re.search(pat, block)
            if m:
                ip[key] = int(m.group(1))
        
        return ip
    
    def _extract_business_info(self) -> Dict:
        """提取经营信息（6.x）"""
        block = self.structure.get_content_block("6")
        if not block:
            block = self.structure.get_content_block("6.1") or ""
        
        info = {
            "qualifications_count": 0,
            "bids_count": 0,
            "recruitments_count": 0,
            "customers_count": 0,
        }
        
        patterns = {
            "qualifications_count": r"资质证书\s*\((\d+)\)",
            "bids_count": r"招投标\s*\((\d+)\)",
            "recruitments_count": r"招聘\s*\((\d+)\)",
            "customers_count": r"客户\s*\((\d+)\)",
        }
        
        for key, pat in patterns.items():
            m = re.search(pat, block)
            if m:
                info[key] = int(m.group(1))
        
        return info
