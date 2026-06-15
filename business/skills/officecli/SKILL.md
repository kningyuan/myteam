---
name: "Office 文档工具"
description: Office 文档创建、分析、修改 — .docx / .xlsx / .pptx 的 CLI 全流程操作。适用于 deck-build、content、code-writing 等需要生成或编辑 Office 文档的任务。
workflows:
  - 产品独立交付
  - 代码交付
agents:
  - product
  - developer
  - frontend
  - content
  - ops
  - docs
---
# officecli — Office 文档 Skill

**适用**：任何需要创建、读取、分析、修改 Office 文档（.docx / .xlsx / .pptx）的任务。

## 前置条件

确认 `officecli` 已安装：

```bash
officecli --version
```

若未安装：

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh | bash
```

---

## 核心原则

**L1（只读视图）→ L2（DOM 操作）→ L3（原始 XML）**。始终优先使用高层。加 `--json` 获取结构化输出。

**不确定属性名时，运行帮助而不是猜测**：

```bash
officecli help                          # 全部命令
officecli help docx paragraph           # 某元素的完整 schema
officecli help docx set paragraph       # 过滤：仅 set 可用属性
officecli pptx set shape.fill           # 单属性详情 + 示例
```

---

## 快速开始

### PPT

```bash
officecli create slides.pptx
officecli add slides.pptx / --type slide --prop title="Q4 Report" --prop background=1A1A2E
officecli add slides.pptx '/slide[1]' --type shape \
  --prop text="Revenue grew 25%" --prop x=2cm --prop y=5cm \
  --prop font=Arial --prop size=24 --prop color=FFFFFF
officecli view slides.pptx outline
```

### Word

```bash
officecli create report.docx
officecli add report.docx /body --type paragraph --prop text="Executive Summary" --prop style=Heading1
officecli add report.docx /body --type paragraph --prop text="Revenue increased by 25% year-over-year."
officecli view report.docx text
```

### Excel

```bash
officecli create data.xlsx
officecli set data.xlsx /Sheet1/A1 --prop value="Name" --prop bold=true
officecli set data.xlsx /Sheet1/A2 --prop value="Alice"
officecli set data.xlsx /Sheet1/B1 --prop value="Score" --prop bold=true
officecli set data.xlsx /Sheet1/B2 --prop value=95
```

---

## L1：创建、读取 & 检查

```bash
officecli create <file>               # 创建空白 .docx/.xlsx/.pptx
officecli view <file> <mode>          # outline | stats | issues | text | annotated | html | screenshot
officecli get <file> <path> --depth N # 获取节点及其子节点 [--json]
officecli query <file> <selector>     # CSS 类查询
officecli validate <file>             # OpenXML schema 验证
```

### view 模式

| 模式 | 说明 |
|------|------|
| `outline` | 文档结构 |
| `stats` | 统计（页数、字数、形状数） |
| `issues` | 格式/内容/结构问题 |
| `text` | 纯文本提取 |
| `annotated` | 带格式注释的文本 |
| `html` | 静态 HTML 快照 |
| `screenshot` | PNG 截图（需 headless browser） |

---

## L2：DOM 操作

### set — 修改属性

```bash
officecli set <file> <path> --prop key=value [--prop ...]
```

**值格式**：

| 类型 | 格式 | 示例 |
|------|------|------|
| 颜色 | Hex / named / RGB / theme | `FF0000`, `#FF0000`, `red`, `rgb(255,0,0)`, `accent1` |
| 间距 | 带单位 | `12pt`, `0.5cm`, `1.5x` |
| 尺寸 | EMU 或后缀 | `914400`, `2.54cm`, `1in`, `72pt` |

### find — 格式化或替换匹配文本

```bash
officecli set doc.docx '/body/p[1]' --find weather --prop bold=true --prop color=red
officecli set doc.docx / --find draft --replace final
```

### add — 添加元素

```bash
officecli add <file> <parent> --type <type> [--prop ...]
officecli add <file> <parent> --type <type> --after <path> [--prop ...]
officecli add <file> <parent> --from <path>  # 克隆
```

**元素类型**：

| 格式 | 类型 |
|------|------|
| **pptx** | slide, shape, picture, chart, table, row, connector, group, video, audio, equation, notes, comment, animation, transition |
| **docx** | paragraph, run, table, row, cell, image, header, footer, section, bookmark, comment, chart, equation, hyperlink, style, toc, watermark |
| **xlsx** | sheet, row, col, cell, chart, image, comment, table, namedrange, pivottable, sparkline, validation, autofilter |

### batch — 多操作单次保存

```bash
echo '[{"command":"set","path":"/Sheet1/A1","props":{"value":"Name","bold":"true"}}]' | officecli batch data.xlsx --json
officecli batch data.xlsx --input updates.json --force --json
```

---

## L3：原始 XML

```bash
officecli raw <file> <part>                          # 查看原始 XML
officecli raw-set <file> <part> --xpath "..." --action replace --xml '<w:p>...</w:p>'
```

---

## 常见错误

| 错误 | 正确做法 |
|------|---------|
| `--name "foo"` | 用 `--prop name="foo"` |
| 未加引号的 `[N]` 路径 | 始终加引号：`'/slide[1]'` |
| 猜测属性名 | 运行 `officecli help <fmt> <element>` |
| 修改已打开文件 | 先在 PowerPoint/WPS 中关闭 |

---

## 模板合并 — 一次生成，批量填充

```bash
officecli merge invoice-template.docx out-001.docx '{"client":"Acme","total":"$5,200"}'
officecli merge q4-template.pptx q4-acme.pptx data.json
```

---

## 验证 & 质量检查

```bash
officecli validate report.docx
officecli view report.docx issues --json
```

生成文档后必须执行验证，确保格式合规。

---

## 红线

- 禁止伪造文件路径（文件必须真实存在）
- 生成文档后必须 `validate` + `view issues`
- 不确定属性时查帮助，禁止猜测
- 路径使用 1-based 索引（XPath 惯例）
