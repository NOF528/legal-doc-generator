"""
测试夹具

提供典型变更记录样本，用于验证事件分类和草稿生成。
"""

# 样本1：明确的股权转让（老股东退出，新股东进入）
EQUITY_TRANSFER_CHANGES = [
    {
        "seq": "1",
        "date": "2020-08-14",
        "project": "投资人变更",
        "before": "李红京（持股51.4647%）；张三（持股10%）",
        "after": "李红京（持股42.1075%）；成转鹏（持股2.0000%）",
        "source": "工商公示",
    }
]

# 样本2：注册资本增加（但缺少出资方信息）
CAPITAL_INCREASE_CHANGES = [
    {
        "seq": "1",
        "date": "2020-08-15",
        "project": "注册资本变更",
        "before": "84,059.1737万元",
        "after": "102,738.99万元",
        "source": "工商公示",
    }
]

# 样本3：注册资本减少
CAPITAL_DECREASE_CHANGES = [
    {
        "seq": "1",
        "date": "2020-11-06",
        "project": "注册资本变更",
        "before": "102,738.99万元",
        "after": "12,222.2222万元",
        "source": "工商公示",
    }
]

# 样本4：同日多项变更（资本变更 + 投资人变更）
COMBINED_CHANGES = [
    {
        "seq": "1",
        "date": "2020-09-16",
        "project": "注册资本变更",
        "before": "100万元",
        "after": "500万元",
        "source": "工商公示",
    },
    {
        "seq": "2",
        "date": "2020-09-16",
        "project": "投资人变更",
        "before": "王五（持股100%）",
        "after": "王五（持股20%）；赵六（持股80%）",
        "source": "工商公示",
    }
]

# 样本5：无法判断的股东变更
UNDETERMINED_CHANGES = [
    {
        "seq": "1",
        "date": "2020-08-14",
        "project": "投资人变更",
        "before": "",
        "after": "",
        "source": "工商公示",
    }
]


if __name__ == "__main__":
    from app.services.qcc_extractor import extract_history_evolution

    print("=" * 60)
    print("测试样本1：明确股权转让")
    print("=" * 60)
    result = extract_history_evolution(EQUITY_TRANSFER_CHANGES, "测试公司")
    print(result["text"])
    print()

    print("=" * 60)
    print("测试样本2：注册资本增加")
    print("=" * 60)
    result = extract_history_evolution(CAPITAL_INCREASE_CHANGES, "测试公司")
    print(result["text"])
    print()

    print("=" * 60)
    print("测试样本3：同日多项变更")
    print("=" * 60)
    result = extract_history_evolution(COMBINED_CHANGES, "测试公司")
    print(result["text"])
