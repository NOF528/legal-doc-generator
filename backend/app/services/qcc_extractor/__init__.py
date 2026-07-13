"""
企查查 PDF 报告提取器

使用示例：
    from app.services.qcc_extractor import QCCReportExtractor
    
    extractor = QCCReportExtractor()
    result = extractor.extract("/path/to/qcc_report.pdf")
"""

from .extractor import QCCReportExtractor
from .changes import extract_history_evolution, ChangeType
from .history_docx_generator import generate_history_word_document

__all__ = ["QCCReportExtractor", "extract_history_evolution", "ChangeType", "generate_history_word_document"]
