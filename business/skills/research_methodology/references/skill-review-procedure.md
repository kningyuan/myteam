# skill-review 提交指南

> 自动沉淀自 skill_review 复盘；供同类 interaction 按需 Read。

## submit_result.py 正确路径

```
backend/common/delivery/submit_result.py
```

**常见错误**：误记为 `backend/common/agent/submit_result.py`。该路径不存在，需通过 glob 搜索定位。

## 提交方式

```bash
venv/bin/python3 backend/common/delivery/submit_result.py \
  --out <workspace>/.response/<interaction_id>.response \
  --file <result_json_file>
```

## 结果 JSON 格式

```json
{
  "interaction_id": "<id>",
  "kind": "skill_review",
  "status": "ok",
  "result": {
    "action": "noop|patch|reference|create",
    "skill_id": "<umbrella_skill_id>",
    "notes": "<说明>",
    "pending_content": ""
  },
  "notes": "复盘摘要"
}
```

## Pitfalls

- `submit_result.py` 不在 `backend/common/agent/` 下，而在 `backend/common/delivery/` 下
- 提交前必须确认 `.response/` 目录存在
- `action` 为 `noop` 时仍须提交结果 JSON，不可省略

## Verification

- 提交后检查 `.response/` 目录下是否生成对应 `.response` 文件
- 文件内容应包含完整 JSON 且 `status` 为 `ok`
