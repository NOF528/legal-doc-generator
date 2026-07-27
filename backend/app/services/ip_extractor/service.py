"""
知识产权抽取服务：编排 章节定位 → 表格解析 → 图案抽取
"""
from dataclasses import dataclass, field
from typing import Dict, List

from app.services.qcc_extractor.extractor import QCCReportExtractor
from .trademark_parser import parse_trademarks, detect_truncation
from .patent_parser import parse_patents
from .image_extractor import extract_trademark_images


@dataclass
class IPExtractionResult:
    """知识产权抽取结果"""
    company_name: str
    trademarks: List[Dict] = field(default_factory=list)
    patents: List[Dict] = field(default_factory=list)
    trademark_images: Dict[str, bytes] = field(default_factory=dict)  # {申请号: 图片字节}
    warnings: List[str] = field(default_factory=list)

    @property
    def patent_type_stats(self) -> Dict[str, int]:
        stats: Dict[str, int] = {}
        for p in self.patents:
            t = p["patent_type"]
            stats[t] = stats.get(t, 0) + 1
        return stats

    def summary(self) -> Dict:
        return {
            "trademark_count": len(self.trademarks),
            "patent_count": len(self.patents),
            "patent_type_stats": self.patent_type_stats,
        }

    def patent_summary_text(self) -> str:
        stats = self.patent_type_stats
        return (
            f"公司共有授权专利{len(self.patents)}件，"
            f"其中发明{stats.get('发明', 0)}件、"
            f"实用新型{stats.get('实用新型', 0)}件、"
            f"外观设计{stats.get('外观设计', 0)}件，详情如下。"
        )

    def trademark_summary_text(self) -> str:
        return f"公司共有已注册商标{len(self.trademarks)}件，详情如下。"


def extract_ip_assets(pdf_path: str, with_images: bool = True) -> IPExtractionResult:
    """
    从企查查专业版报告 PDF 抽取知识产权（商标 + 专利）。

    Args:
        pdf_path: PDF 文件路径
        with_images: 是否抽取商标图案（docx 生成时需要；纯 JSON 预览可关）
    """
    extractor = QCCReportExtractor()
    extractor.extract(pdf_path)

    tm_block = extractor.structure.get_content_block("8.1")
    pt_block = extractor.structure.get_content_block("8.2")

    trademarks = parse_trademarks(tm_block)
    patents = parse_patents(pt_block)

    warnings: List[str] = []
    # 报告维度截断（如商标共280条仅展示100条），提示律师抽取范围受限
    tm_trunc = detect_truncation(tm_block)
    if tm_trunc and tm_trunc[0] > tm_trunc[1]:
        warnings.append(
            f"商标信息共{tm_trunc[0]}条，报告仅展示前{tm_trunc[1]}条，本次仅抽取展示部分")
    pt_trunc = detect_truncation(pt_block)
    if pt_trunc and pt_trunc[0] > pt_trunc[1]:
        warnings.append(
            f"专利信息共{pt_trunc[0]}条，报告仅展示前{pt_trunc[1]}条，本次仅抽取展示部分")

    images: Dict[str, bytes] = {}
    if with_images and trademarks:
        images = extract_trademark_images(
            pdf_path, [t["app_no"] for t in trademarks]
        )
        missing = len(trademarks) - len(images)
        if missing > 0:
            warnings.append(f"有{missing}件商标未能从PDF中抽取到图案，已用【**】占位")

    return IPExtractionResult(
        company_name=extractor.company_name,
        trademarks=trademarks,
        patents=patents,
        trademark_images=images,
        warnings=warnings,
    )
