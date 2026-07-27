"""
商标图案抽取（PyMuPDF）

思路：
1. 定位 8.1 商标表所在页：含「商标图案」表头的页为起始页，到 8.2 节前结束
2. 每页用 get_text("words") 找到申请号词（6~9位数字可带字母），取其 y 坐标为行锚点
3. get_image_info() 拿每页图片 bbox，图片中心 y 落在某行锚点区间内即属于该行
4. 直接用 extract_image(xref) 取原始图片字节（不重渲染，质量最好）

返回 {申请号: 图片字节}，查不到图案的行不进字典（Word 端用【**】占位）。
"""
import re
from typing import Dict, List, Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

_APP_NO_WORD = re.compile(r'^\d{6,9}[A-Z]?$')
_TABLE_HEADER = "商标图案"
_NEXT_SECTION = "8.2 专利信息"


def _find_table_pages(doc) -> List[int]:
    """商标表所在页：从含表头页开始，到含 8.2 节标题的页为止（含边界页，
    边界页上 8.2 标题之上的商标行仍然有效）"""
    start = None
    pages = []
    for pno in range(len(doc)):
        text = doc[pno].get_text()
        if start is None:
            if _TABLE_HEADER in text and "商标名称" in text:
                start = pno
                pages.append(pno)
            continue
        pages.append(pno)
        if _NEXT_SECTION in text:
            break
    return pages


def _section_heading_y(page, keyword: str) -> Optional[float]:
    """8.2 节标题在该页的 y 坐标（用于裁掉边界页上属于专利节的内容）"""
    for w in page.get_text("words"):
        if keyword in w[4]:
            return w[1]
    return None


def extract_trademark_images(
    pdf_path: str,
    app_nos: Optional[List[str]] = None,
) -> Dict[str, bytes]:
    """
    抽取商标图案列图片。

    Args:
        pdf_path: PDF 文件路径
        app_nos: 需要的申请号列表（已注册商标）；None 表示全部行

    Returns:
        {申请号: 图片字节(PNG/JPEG 原始流)}
    """
    if fitz is None:
        return {}
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return {}

    wanted = set(app_nos) if app_nos else None
    result: Dict[str, bytes] = {}

    try:
        for pno in _find_table_pages(doc):
            page = doc[pno]
            words = page.get_text("words")
            # 边界页：8.2 标题之下的内容属于专利节，排除
            cut_y = _section_heading_y(page, "专利信息")
            # 行锚点：申请号词的 y 区间
            anchors = [
                (w[1], w[3], w[4])  # y0, y1, text
                for w in words
                if _APP_NO_WORD.match(w[4])
                and (cut_y is None or w[3] < cut_y)
            ]
            if not anchors:
                continue
            anchors.sort()
            for info in page.get_image_info(xrefs=True):
                bbox = info.get("bbox")
                xref = info.get("xref", 0)
                if not bbox or not xref:
                    continue
                cy = (bbox[1] + bbox[3]) / 2
                # 找中心 y 落在哪个行锚点的 y 区间（上下各放宽半行）
                for y0, y1, app_no in anchors:
                    if y0 - 6 <= cy <= y1 + 6:
                        if wanted is not None and app_no not in wanted:
                            break
                        if app_no in result:
                            break
                        try:
                            img = doc.extract_image(xref)
                            result[app_no] = img["image"]
                        except Exception:
                            pass
                        break
    finally:
        doc.close()
    return result
