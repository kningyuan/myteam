# drawing spec — diagram_brief.yaml

Agent 用 YAML 描述图；`brief_to_drawio.py` 生成 mxGraphModel XML。

## 字段

| 字段 | 说明 |
|------|------|
| `title` | 图标题（显示在顶部） |
| `nodes[].id` | 稳定 ID，edges 引用 |
| `nodes[].label` | 框内文字（`\n` 换行） |
| `nodes[].x,y,w,h` | 像素坐标与尺寸 |
| `nodes[].fill/stroke` | 可选颜色 |
| `edges[].from/to` | 节点 id |
| `edges[].label` | 可选连线文字 |

复杂图（泳道、图标库、>15 节点）可 Agent 直接编辑 `.drawio`，跳过 brief 转换。
