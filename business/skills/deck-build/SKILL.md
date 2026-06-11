---
name: deck-build
task_type: deck-build
description: 生成演示文稿 deck.pptx — WPS 增强或 python-pptx 兜底。
---

# deck-build — 演示文稿

**先读**：`business/skills/product-operations/SKILL.md`  
**WPS 增强**：`business/skills/wps-deck/SKILL.md`  
**Preflight**：`business/skills/product-operations/checklists/deck_preflight.md`

## 执行步骤

1. 从上游 strategy/PRD 提炼 **8–12 页** 结构，复制并填写 `deck_brief.yaml`（模板见 product-operations/templates/）。
2. 在交付物目录生成 PPT：

```bash
DELIV="<交付物目录>"
mkdir -p "$DELIV/evidence"
bash business/skills/product-operations/scripts/build_deck.sh \
  "$DELIV/deck_brief.yaml" \
  "$DELIV/deck.pptx"
```

3. 按 `templates/deck_deliverable.md` 写 Markdown 交付物（同目录）。
4. Gate 前：

```bash
python3 business/skills/product-operations/scripts/verify_deck.py \
  "$DELIV/deck.pptx" --deliverable "$DELIV/<task_id>_deliverable.md"
```

5. `submit_result` 中 artifact.path 指向 deliverable markdown；**deck.pptx 须在同目录且 Gate file_exists 可验**。

## 红线

- 禁止只有 Markdown 无 `deck.pptx`。
- 禁止未跑 verify_deck 就 submit。
- WPS RPC 不可用时应看到 `fallback python-pptx` 日志，而非空文件。
