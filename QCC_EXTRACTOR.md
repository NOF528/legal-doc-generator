# 企查查 PDF 报告提取器

## 概述

企查查提取器是法律文档生成器的子模块，用于从企查查企业信用报告 PDF 中提取结构化数据，支持自动生成法律意见书的历史沿革部分。

## 架构设计

```
backend/app/services/qcc_extractor/
├── __init__.py          # 模块入口，暴露 QCCReportExtractor
├── cleaner.py           # 页眉页脚清洗
├── structure.py         # 文档结构解析（目录树、章节定位）
├── tables.py            # 表格解析器（股东、人员、投资等）
└── extractor.py         # 主提取器，组装所有组件
```

### 核心组件

| 组件 | 职责 | 关键算法 |
|------|------|----------|
| `PageHeaderCleaner` | 清洗每页页眉页脚 | 正则匹配 + 企业名称动态过滤 |
| `DocumentStructureParser` | 解析目录结构，定位章节内容 | 双层标题识别（目录vs内容） |
| `TableExtractor` | 通用表格提取 | 表头驱动 + 跨行缓冲合并 |
| `TableRowBuffer` | 处理跨页断行 | 智能新行判断（非纯数字序号） |

## 使用方法

### 1. 后端 API

```bash
# 提取完整数据
POST /api/v1/qcc/extract
Content-Type: multipart/form-data
file: <PDF文件>

# 提取精简数据（推荐）
POST /api/v1/qcc/extract-basic
Content-Type: multipart/form-data
file: <PDF文件>
```

### 2. Python 直接调用

```python
from app.services.qcc_extractor import QCCReportExtractor

extractor = QCCReportExtractor()
result = extractor.extract("/path/to/qcc_report.pdf")

# 输出结构
print(result['report_meta']['company_name'])
print(result['basic_info']['shareholders'])
print(result['basic_info']['key_persons'])
```

### 3. 前端界面

访问 `http://localhost:3000`，点击"企查查提取"标签页，上传 PDF 即可。

## 输出数据格式

```json
{
  "report_meta": {
    "company_name": "深圳华云信息系统科技股份有限公司",
    "report_type": "企业信用报告专业版",
    "report_date": "2026年03月30日10:27:41",
    "report_no": "1774837661475885",
    "total_pages": 90,
    "producer": "QCC-PDFCreator-1.0.0"
  },
  "company_profile": {
    "contact_info": {
      "phone": "0755-86125889",
      "email": "xiangjb@hwawan.com",
      "website": "https://www.huayunsoft.com",
      "address": "深圳市南山区..."
    }
  },
  "basic_info": {
    "registration": {
      "统一社会信用代码": "914403006626860999",
      "法定代表人": "郭国峰",
      "注册资本": "7200 万元",
      ...
    },
    "shareholders": [
      {"seq": "1", "name": "郭国峰", "ratio": "25.0000%", "amount": "1800", ...},
      ...
    ],
    "key_persons": [
      {"seq": "1", "name": "郭国峰", "position": "董事长,总经理", ...},
      ...
    ],
    "investments": [...],
    "branches": [...],
    "change_history": [...]
  },
  "legal_risks": {
    "judicial_cases_count": 6,
    "judgment_documents_count": 2,
    ...
  },
  "business_risks": {...},
  "intellectual_property": {
    "trademarks": 13,
    "patents": 72,
    "software_copyrights": 302
  }
}
```

## 支持的表格类型

| 表格 | 支持度 | 说明 |
|------|--------|------|
| 工商注册信息 | ✅ 完全支持 | 统一信用代码、法人、注册资本等 |
| 股东信息 | ✅ 完全支持 | 已处理跨页断行问题 |
| 主要人员 | ✅ 完全支持 | 董事、监事、高管 |
| 对外投资 | ✅ 完全支持 | 持股比例、状态 |
| 分支机构 | ⚠️ 部分支持 | 简单格式OK，复杂跨页需优化 |
| 变更记录 | ⚠️ 部分支持 | 变更项目简单提取，详细内容需优化 |
| 资质证书 | ✅ 数量统计 | 详细列表待完善 |
| 司法风险 | ✅ 数量统计 | 案件数、文数等 |

## 已知限制与优化建议

### PDF 文本提取的固有限制

1. **跨页表格断行**：PDF 分页会导致表格行被截断（如 "3新余华云" 在第7页末尾，"13.4380%" 在第8页开头）
   - 当前方案：`TableRowBuffer` 智能判断合并
   - 优化建议：对于关键表格，建议结合页码信息做二次验证

2. **长文本跨行**：公司名称、经营范围等长文本可能跨多行
   - 当前方案：正则合并连续行
   - 优化建议：利用字体大小/位置信息（需要 pdfplumber）

3. **页眉残片嵌入**：跨页时页眉可能嵌入表格数据中
   - 当前方案：`_clean_embedded_header` 正则清理
   - 优化建议：建立更完整的页眉关键词库

### 未来优化方向

1. **多报告类型适配**：目前针对"专业版"优化，简版/标准版可能有格式差异
   - 建议：增加 `ReportTypeDetector` 自动识别版本

2. **增量更新**：对比新旧报告提取变更
   - 建议：增加 `QCCReportComparator` 组件

3. **数据验证**：与工商官网数据交叉验证
   - 建议：集成第三方 API 做校验

4. **表格精确解析**：使用 pdfplumber 获取位置信息
   - 权衡：增加依赖 vs 提升精度

## 扩展开发指南

### 添加新的表格解析器

在 `tables.py` 中添加：

```python
def parse_new_table_line(line: str) -> Optional[Dict]:
    """解析新表格类型"""
    # 1. 修正序号粘连："3名称" -> "3 名称"
    line = re.sub(r"^(\d+)([^\s\d])", r"\1 \2", line)
    
    # 2. 分割字段
    parts = line.strip().split()
    
    # 3. 验证格式
    if not parts[0].isdigit():
        return None
    
    # 4. 返回结构化数据
    return {
        "seq": parts[0],
        "field1": parts[1] if len(parts) > 1 else "",
        ...
    }
```

在 `extractor.py` 中调用：

```python
block = self.structure.get_content_block("章节编号")
lines = [l.strip() for l in block.split("\n") if l.strip()]
extractor = TableExtractor(lines, ["表头关键词1", "表头关键词2"])
info["new_data"] = extractor.extract(parse_new_table_line)
```

### 添加 API 接口

在 `api/v1/qcc.py` 中添加：

```python
@router.post("/new-endpoint")
async def new_endpoint(file: UploadFile = File(...)):
    # 实现逻辑
    ...
```

## 测试验证

```bash
# 后端单元测试
cd backend
python3 -c "
from app.services.qcc_extractor import QCCReportExtractor
ext = QCCReportExtractor()
result = ext.extract('test.pdf')
print(f\"股东数: {len(result['basic_info']['shareholders'])}\")
"

# API 测试
curl -X POST -F "file=@test.pdf" http://localhost:8000/api/v1/qcc/extract-basic
```

## 集成到文档生成流程

用户上传企查查报告 → 提取数据 → 自动填充模板占位符：

```
{{company_name}} -> 深圳华云信息系统科技股份有限公司
{{legal_representative}} -> 郭国峰
{{shareholder_structure}} -> 生成表格
{{change_history_summary}} -> 生成变更简述
```

后续将开发 `HistoryGenerator` 组件，自动将提取的数据转换为法律意见书的历史沿革章节。
