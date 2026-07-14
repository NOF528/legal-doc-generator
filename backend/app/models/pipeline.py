"""
企查查报告处理流水线领域模型

设计原则：
- 每条变更保留完整的证据链（source_records, page_nos, confidence, warnings）
- 历史沿革是草稿（draft），不是最终法律事实
- 复核问题是显式的（ReviewIssue），不是隐式的断言
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class ChangeType(str, Enum):
    """变更类型"""
    EQUITY_TRANSFER = "股权转让"
    CAPITAL_INCREASE = "增资"
    CAPITAL_DECREASE = "减资"
    NAME_CHANGE = "名称变更"
    LEGAL_REP_CHANGE = "法定代表人变更"
    ADDRESS_CHANGE = "地址变更"
    SCOPE_CHANGE = "经营范围变更"
    OTHER = "其他"


class PipelineStatus(str, Enum):
    """流水线处理状态"""
    PENDING = "pending"
    UPLOADED = "uploaded"
    EXTRACTED = "extracted"
    NORMALIZED = "normalized"
    CLASSIFIED = "classified"
    DRAFTED = "drafted"
    REVIEWED = "reviewed"
    EXPORTED = "exported"


class ReviewSeverity(str, Enum):
    """复核问题严重等级"""
    CRITICAL = "critical"   # 必须修正：涉及虚假陈述风险
    WARNING = "warning"     # 建议修正：数据缺失或不一致
    INFO = "info"           # 仅供参考：可人工确认


class ExtractedChange(BaseModel):
    """
    单条变更事实，带完整证据链

    法律场景要求每条变更都能追溯到原始 PDF 中的具体位置。
    """
    seq: str
    date: str          # 格式化后日期，如 "2024年1月15日"
    raw_date: str      # 原始日期，如 "2024-01-15"
    project: str       # 变更项目，如 "投资人变更"
    before: str = ""   # 变更前内容
    after: str = ""    # 变更后内容
    source: str = ""   # 数据来源，如 "工商公示"

    # ========== 证据链 ==========
    source_records: List[str] = Field(
        default_factory=list,
        description="原始文本行，用于律师复核时对照原文"
    )
    page_nos: List[int] = Field(
        default_factory=list,
        description="该变更记录在 PDF 中的来源页码列表"
    )
    parser_version: str = "1.0.0"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    warnings: List[str] = Field(
        default_factory=list,
        description="解析过程中遇到的异常或不确定性提示"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "seq": "1",
                "date": "2024年1月15日",
                "raw_date": "2024-01-15",
                "project": "投资人变更",
                "before": "张三（持股30%）",
                "after": "李四（持股30%）【新进】",
                "source": "工商公示",
                "source_records": ["12024-01-15投资人变更", "张三（持股30%）【退出】", "李四（持股30%）【新进】"],
                "page_nos": [12],
                "parser_version": "1.0.0",
                "confidence": 0.95,
                "warnings": ["无法确认转让对价"]
            }
        }


class ChangeGroupModel(BaseModel):
    """同一日期的变更组（结构化中间态）"""
    date: str
    raw_date: str
    records: List[ExtractedChange] = Field(default_factory=list)
    change_types: List[ChangeType] = Field(default_factory=list)
    exits: List[Dict[str, Any]] = Field(default_factory=list)
    enters: List[Dict[str, Any]] = Field(default_factory=list)
    capital_before: str = ""
    capital_after: str = ""


class ShareholderSnapshot(BaseModel):
    """股东快照（某一时刻的股权状态）"""
    name: str
    amount: str = "【**】"      # 出资额（万元）
    ratio: str = "【**】"       # 持股比例
    capital: str = "【**】"     # 认缴/实缴资本
    change_type: Optional[str] = None  # 相对上一快照的变更：新进/退出/增持/减持/不变


class HistoryDraft(BaseModel):
    """
    历史沿革草稿——不是最终法律事实

    生成器只输出：
    - draft_text: 基于企查查原文的事实陈述
    - missing_fields: 需要律师补充的字段列表
    - warnings: 法律风险提示
    - source_records: 来源变更记录（可追溯到原始 PDF）

    律师确认前，draft_text 不应直接用于法律意见书。
    """
    date: str
    sequence_title: str = ""      # 如 "2024年1月15日 股权转让"
    draft_text: str = ""          # 生成的草稿文本
    missing_fields: List[str] = Field(
        default_factory=list,
        description="需要律师手动补充的字段，如 ['转让对价', '股东会决议日期']"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="法律风险提示，如 '企查查未记录股东会决议，需补充'"
    )
    source_records: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="该草稿段落对应的原始变更记录"
    )
    is_confirmed: bool = False    # 是否经律师确认
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None


class ReviewIssue(BaseModel):
    """
    复核问题——显式的质量门禁

    每条 Issue 对应一个需要律师关注的问题点，
    而不是让生成器"默默"地把推断写成事实。
    """
    id: str = Field(default_factory=lambda: f"issue_{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    severity: ReviewSeverity = ReviewSeverity.WARNING
    category: str = ""            # fact_inferred, data_missing, format_error, legal_risk, consistency
    description: str = ""         # 问题描述
    source_change_date: Optional[str] = None  # 关联的变更日期
    suggested_fix: str = ""       # 建议修正方式
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    notes: str = ""


class Report(BaseModel):
    """
    完整的上传报告处理结果

    这是整个流水线的核心数据载体，从上传开始到导出完成，
    所有中间态和最终结果都保存在这里。
    """
    # ========== 标识 ==========
    report_id: str = Field(default_factory=lambda: f"rpt_{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    company_name: str = ""
    filename: str = ""
    uploaded_at: datetime = Field(default_factory=datetime.now)
    status: PipelineStatus = PipelineStatus.PENDING

    # ========== 原始提取数据 ==========
    raw_extraction: Optional[Dict[str, Any]] = None

    # ========== 结构化结果 ==========
    registration: Optional[Dict[str, str]] = None
    current_shareholders: List[ShareholderSnapshot] = Field(default_factory=list)
    extracted_changes: List[ExtractedChange] = Field(default_factory=list)
    change_groups: List[ChangeGroupModel] = Field(default_factory=list)

    # ========== 历史沿革草稿 ==========
    history_drafts: List[HistoryDraft] = Field(default_factory=list)
    history_text_combined: str = ""  # 合并后的完整草稿文本

    # ========== 复核问题 ==========
    review_issues: List[ReviewIssue] = Field(default_factory=list)
    review_passed: bool = False

    # ========== 导出 ==========
    exported_file_path: Optional[str] = None
    exported_at: Optional[datetime] = None

    # ========== 元数据 ==========
    parser_version: str = "1.0.0"
    total_pages: int = 0
    extract_time_ms: int = 0

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
