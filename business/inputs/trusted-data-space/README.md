# 可信数据空间 · 参考输入

原 Word 稿提取稿，可在 Goal 中作为只读材料引用。

| 文件 | 说明 |
|------|------|
| `source_ch1_overview.md` | 第一章 产品概述 |
| `source_ch2_market.md` | 第二章 市场与客户需求 |
| `source_ch3_current.md` | 第三章 现状 |
| `source_full_extract.md` | 全文纯文本提取 |

当前 MVP 使用 **Workflow「产品需求」** + 交付模板 **`prd-standard`**。

```bash
cd "$MYTEAM_ROOT"
export PYTHONPATH=backend
venv/bin/python3 backend/common/run_kernel.py tds-prd \
  --workflow 产品需求 \
  --title "可信数据空间·产品需求" \
  --goal "见 business/workflows/产品需求-goal示例.txt 或自拟 PRD 目标" \
  --budget 800000
```
