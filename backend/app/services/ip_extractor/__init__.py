"""
知识产权抽取模块（商标 + 专利）

从企查查专业版报告第 8 章抽取：
- 8.1 商标信息：只保留状态为「已注册」的商标，图案列图片用 PyMuPDF 按行裁剪
- 8.2 专利信息：只保留法律状态为「授权」的专利，
  专利类型归一为 发明/实用新型/外观设计（发明公布、发明授权统一记为发明）
"""
from .trademark_parser import parse_trademarks
from .patent_parser import parse_patents
from .service import extract_ip_assets, IPExtractionResult

__all__ = [
    "parse_trademarks",
    "parse_patents",
    "extract_ip_assets",
    "IPExtractionResult",
]
