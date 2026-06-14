# Workflow Profiles（声明式任务 DAG）

## 当前：`产品规划方案`（v2.2 · Work–Review + 质量评审）

| 阶段 | Agent | 说明 |
|------|-------|------|
| loop · work（R1） | product | 首次撰写第三章 |
| loop · review | main | **内容质量**：合理性/准确性/可交付性（不以字数放行） |
| FAIL 后 | product ↔ main | **项目群定点对齐**改稿清单（`ALIGN: OK`） |
| loop · work（R2+） | product | **仅 PATCH** 清单中的 ### 小节（基线自动复制） |
| loop · review（R2+） | main | 核对清单落实 + 清单外章节未被擅自改动 |
| 退出 | — | review 末行 `REVIEW: PASS` |

```bash
export MYTEAM_ROOT="$PWD" PYTHONPATH=backend

venv/bin/python3 backend/common/run_kernel.py tds-ch3-plan \
  --workflow 产品规划方案 \
  --goal "$(cat business/workflows/可信数据空间-第三章-goal.txt)" \
  --budget 800000 --backend claude
```

Goal 示例：`business/workflows/可信数据空间-第三章-goal.txt`
