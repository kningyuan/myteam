# diagram-build — Means 执行说明

**前提**：已完成 `align.md`、`plan.md`（catalog 自选 means）。  
**过程脚手架**：`bash business/playbooks/scripts/scaffold_process.sh "$DELIV"`

## 1. 探针（Launch 前）

```bash
bash business/means/diagram-build/scripts/probe.sh
# 输出追加到 verify.log
```

## 2. brief 模板

```bash
cp business/means/diagram-build/templates/diagram_brief.yaml "$DELIV/diagram_brief.yaml"
```

## 3. 生成 .drawio（plan.md 所选 means）

**A — brief_to_drawio（推荐）**

```bash
python3 business/means/diagram-build/scripts/brief_to_drawio.py \
  "$DELIV/diagram_brief.yaml" "$DELIV/diagram.drawio"
```

**B — handwrite_drawio**

按 `references/drawing_spec.md` 手写 `$DELIV/diagram.drawio`。

## 4. 渲染 PNG

```bash
bash business/means/diagram-build/scripts/build_diagram.sh \
  "$DELIV/diagram.drawio" "$DELIV/diagram.png"
```

## 5. 交付物 Markdown

按 `templates/diagram_deliverable.md` 写 `$DELIV/<task_id>_deliverable.md`。

## 6. 校验（写入 verify.log）

```bash
python3 business/means/diagram-build/scripts/verify_diagram.py \
  "$DELIV/diagram.drawio" \
  --png "$DELIV/diagram.png" \
  --deliverable "$DELIV/<task_id>_deliverable.md"
```

## 7. Learn + 交卷

填写 `ledger.entry.yaml`、`trace.manifest.yaml`，然后 `submit_result`。

## 红线

- 禁止只有 Markdown、无 `diagram.drawio` 与 `diagram.png`。
- 禁止未跑探针/verify 就 submit。
