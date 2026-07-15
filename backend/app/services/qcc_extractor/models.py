"""
qcc_extractor 领域模型

设计原则：
- 原始证据（EvidenceRef）与推断分离
- 变更事件（ChangeEvent）必须标注置信度等级
- 历史沿革草稿（HistoryDraft）只陈述企查查能证明的事实
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any


class ChangeType(Enum):
    """变更事件类型"""
    EQUITY_TRANSFER = "股权转让"
    CAPITAL_INCREASE = "增资"
    CAPITAL_DECREASE = "减资"
    SHAREHOLDER_CHANGE = "股东变更"          # 投资人变更但无法确认转让关系
    CAPITAL_CHANGE = "注册资本变更"          # 资本变化但无法确认增/减性质
    NAME_CHANGE = "名称变更"
    LEGAL_REP_CHANGE = "法定代表人变更"
    ADDRESS_CHANGE = "地址变更"
    SCOPE_CHANGE = "经营范围变更"
    OTHER = "其他变更"


class ClassificationLevel(Enum):
    """事件分类置信度"""
    CONFIRMED = "confirmed"      # 有直接证据支持
    INFERRED = "inferred"        # 有间接证据，需要律师确认
    UNDETERMINED = "undetermined"  # 无法判断，需要补充材料


@dataclass
class EvidenceRef:
    """原始证据引用"""
    seq: str = ""                      # 变更记录序号
    raw_date: str = ""                 # 原始日期
    project: str = ""                  # 变更项目
    before: str = ""                   # 变更前文本
    after: str = ""                    # 变更后文本
    source: str = ""                   # 来源
    page_nos: List[int] = field(default_factory=list)  # 页码


@dataclass
class ShareholderSnapshot:
    """股东快照"""
    name: str
    amount: str = ""           # 出资额（万元）
    ratio: str = ""            # 持股比例
    capital: str = ""          # 认缴/实缴资本
    change_type: Optional[str] = None  # 相对上一快照：新进/退出/增持/减持/不变


@dataclass
class ChangeFact:
    """单条可归一化的事实"""
    date: str                          # 格式化后日期，如 "2024年1月15日"
    raw_date: str                      # 标准化日期，如 "2024-01-15"
    project: str                       # 变更项目
    before: str = ""
    after: str = ""
    evidence: EvidenceRef = field(default_factory=EvidenceRef)
    confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)


@dataclass
class ChangeEvent:
    """变更事件 = 一个或多个事实归一化后的业务事件"""
    date: str
    raw_date: str
    event_type: ChangeType
    classification_level: ClassificationLevel
    facts: List[ChangeFact] = field(default_factory=list)
    evidence: List[EvidenceRef] = field(default_factory=list)
    known_facts: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # 股东变更相关
    exits: List[ShareholderSnapshot] = field(default_factory=list)
    enters: List[ShareholderSnapshot] = field(default_factory=list)

    # 资本变更相关
    capital_before: str = ""
    capital_after: str = ""


@dataclass
class HistoryDraft:
    """历史沿革草稿段落"""
    date: str
    sequence_title: str = ""
    draft_text: str = ""
    event_type: ChangeType = ChangeType.OTHER
    classification_level: ClassificationLevel = ClassificationLevel.UNDETERMINED
    missing_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    evidence: List[EvidenceRef] = field(default_factory=list)
    is_confirmed: bool = False


@dataclass
class ReviewIssue:
    """复核问题"""
    category: str
    severity: str  # critical / warning / info
    description: str
    source_change_date: Optional[str] = None
    suggested_fix: str = ""


@dataclass
class HistoryEvolutionResult:
    """历史沿革生成结果（兼容旧 API）"""
    text: str = ""
    markdown: str = ""
    combined_text: str = ""
    changes_count: int = 0
    changes: List[Dict[str, Any]] = field(default_factory=list)
    category_stats: Dict[str, int] = field(default_factory=dict)
    drafts: List[HistoryDraft] = field(default_factory=list)
    review_issues: List[ReviewIssue] = field(default_factory=list)
    review_passed: bool = False
