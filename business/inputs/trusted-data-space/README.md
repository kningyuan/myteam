# 可信数据空间 · 产品说明原稿输入

本目录为 workflow **可信数据空间-产品规划完善** 的只读输入，由原 docx 提取。

| 文件 | 说明 |
|------|------|
| `副本可信数据空间.docx` | 原 Word 稿副本 |
| `source_ch1_overview.md` | 第一章 产品概述 |
| `source_ch2_market.md` | 第二章 市场分析与需求调研 |
| `source_ch3_current.md` | 第三章 现状（待 product 完善） |
| `source_full_extract.md` | 全文纯文本提取 |

## 运行

```bash
cd "$MYTEAM_ROOT"
export PYTHONPATH=backend
venv/bin/python3 backend/common/run_kernel.py p_tds_ch3 \
  --workflow 可信数据空间-产品规划完善 \
  --title "可信数据空间·第三章完善" \
  --goal "完善副本可信数据空间.docx 第三章产品整体规划，输入见 business/inputs/trusted-data-space/" \
  --budget 800000
```

产出在 `business/tasks/project/p_tds_ch3/deliverables/`。
