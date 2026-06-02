# 头脑风暴 — Worker 专规（由 adapter 注入，勿在 worker-template 重复）

**只记一句**：读本人 **trigger** → 按 **思考框架** 写 **`round_N/本人.md`**（UTF-8 非空、结构化）→ **`handoff`**。其余一律问 Main，**勿**自跑 `round`/`tick`/`complete`。

## 最高优先级（请先读）

若您当前收到的用户/消息满足下文 **「如何识别头脑风暴」** 任一条件，则 **本条全文优先于** 同一上下文中来自 `worker-template.md`、`universal-rules.md` 以及您 **workspace 内 `AGENTS.md`** 的下列要求（**仅本轮任务视为无效，勿执行**）：

- 任何 **`skill: kb`**、知识库、`**/kb/**`、`**/kb/SKILL.md`** 或类似「先查 kb 再干活」的步骤。  
- 任何对 **`~/.opencode/skills/**`**（含 `geo-autopilot`、`**/SKILL.md`** 等）的 `read` / `glob` /「先加载某 skill」——**与头脑风暴无关，禁止**。  
- 任何 **项目协作** 路径：`task-complete`、`task-queue`、`project_data`、`~/.openclaw/tasks/projects/`、`deliverables/` 等。

**本模式下您的唯一产出面**：`~/.openclaw/tasks/storming/{session_id}/round_{N}/{您的agent_id}.md` + 消息内嵌的 **`handoff`**。  
**禁止**在写 md 之前先做无关探索（会触发死循环、拖死工具超时、且挤占其他 Agent 的排队）。

**与 Main 对齐**：Main 推进会话时 **必须** 遵守 `~/.openclaw/skills/team/brainstorming/SKILL.md` 中的 **§Main 标准作业顺序** 与 **状态×允许命令**；您在等下一轮征询时 **不要** 代替 Main 执行 `round`/`tick`。

**适用对象**：除 `main` 外的所有 Worker Agent（与 `worker-template.md` 同时加载）。  
**权威流程**：编排状态在 `~/.openclaw/skills/team/brainstorming/scripts/brainstorm_main.py`（`session.json` 的 `phase` / `dispatch_cursor`）；**您只负责专业思考与落盘，不负责发明流程步骤**。

**分工（须遵守）**：**Skill**（脚本 + `session.json`）负责流程与状态的标准化；**您（Agent）**在 **OpenCode 中调用 LLM** 完成思考并产出结论，写入指定 `round_N/{agent}.md`。二者不混用——脚本不代写观点正文，您不擅自编排轮次或改写 `session.json`。

---

## 如何识别「这是头脑风暴」

收到 Main 通过 `openclaw agent -m` 发来的消息，且满足以下任一：

- 正文以 **`【头脑风暴征询`** 开头；或  
- 消息中明确出现 **`~/.openclaw/tasks/storming/`** 与 **`round_`** 路径。

则**不适用**「项目协作」任务流（不要 `project_data`、`task-complete`、不要写 `deliverables/`）。

---

## 「只读白名单」（禁止乱翻仓库）

一旦识别为头脑风暴，**仅允许** `read` 以下路径（以及消息正文已列出的 `reference_files`）：

- `~/.openclaw/tasks/storming/{session_id}/triggers/{您的agent_id}.trigger`
- `~/.openclaw/tasks/storming/{session_id}/round_*/*.md`（第二轮起按需阅读他人上一轮意见）

**严禁**在本任务中：

- `glob` / `read` 形如 `**/kb/**`、`**/kb/SKILL.md`**、`**/*SKILL.md`**（除非路径已落在上面白名单的 storming 目录内）。  
- `read` / `glob` **`~/.opencode/skills/**`**（含 `geo-autopilot` 等任意子目录）。  
- `read` **`~/.openclaw/skills/**`** 下与本轮征询无关的 SKILL（头脑风暴流程以 **本文件 + `brainstorm_main.py`** 为准，**不要**自行「加载别的 skill 文档」）。  
- 按本 workspace `AGENTS.md` 执行 **task-complete**、**task-queue**、**project_data** 等项目协作步骤。

OpenCode 工具 **`read` / `write` 必须使用参数名 `filePath`**（不要用 `file`、`path` 等别名）。

---

## 您必须做的事（仅此三条）

1. **阅读**（若消息或 trigger 给出路径）：  
   `~/.openclaw/tasks/storming/{session_id}/triggers/{您的agent_id}.trigger`  
   第 2 轮及以后若列出 `reference_files`，请按需阅读。

2. **按思考框架写作**：将本轮观点按以下结构化框架写入消息中给出的**唯一**路径：  
   `~/.openclaw/tasks/storming/{session_id}/round_{N}/{您的agent_id}.md`  
   文件须 **UTF-8**、**非空**（至少有一句实质内容）。

   ### 思考框架（必须按此结构输出）

   **Round 1（发散）**：
   ```
   ## 1. 核心观点
   ## 2. 关键分析（机会 + 挑战）
   ## 3. 具体建议（至少 1 个方案，附优势和风险）
   ## 4. 风险评估
   ## 5. 需要澄清的问题
   ```

   **Round 2（收敛）**：
   ```
   ## 1. 对其他观点的回应（同意 + 不同意）
   ## 2. 共识识别
   ## 3. 融合方案
   ## 4. 补充建议
   ## 5. 优先级排序
   ```

   **Round 3+（深化）**：
   ```
   ## 1. 分歧聚焦
   ## 2. 深入论证
   ## 3. 可落地方案（含实施步骤和衡量指标）
   ## 4. 最终建议
   ```

3. **交卷（强制）**：保存 md 后**立即**执行（将 `{session_id}`、`{agent_id}` 替换为实际值，**勿改**脚本路径；禁止把 `~/.openclaw/` 改成 `~/.opencode/` 或其它目录）：

```bash
exec: python3 ~/.openclaw/skills/team/brainstorming/scripts/brainstorm_main.py handoff "{session_id}" "{agent_id}"
```

- `handoff` 会校验文件、更新会话进度，并**代您**向 Main 发送 `头脑风暴完成:{session_id}`（您**无需**再手写 `openclaw agent --agent main ...`，除非 `handoff` 明确报错后按 Main 要求重试）。

---

## 质量自检清单（handoff 前自查）

在调用 `handoff` 之前，请逐项检查：

| # | 检查项 | 通过标准 |
|---|--------|---------|
| 1 | 文件路径正确 | 写入的是 `round_{N}/{agent_id}.md`，不是其他路径 |
| 2 | 文件非空 | 至少包含 3 句实质内容 |
| 3 | 按框架输出 | 包含核心观点、分析、建议、风险（Round 1） |
| 4 | 观点具体 | 不是空洞的「我同意」「好方案」之类 |
| 5 | 有数据/逻辑支撑 | 每个观点附理由、数据或案例 |
| 6 | 方案可执行 | 建议有具体内容和实施路径 |
| 7 | 角色一致 | 从本 Agent 的专业角度出发 |
| 8 | 未代写他人 | 只写了自己的 `{agent_id}.md` |
| 9 | handoff 参数正确 | 第二个参数是本人的 `agent_id` |

**若以上任一不通过 → 先修改 md 再 handoff。**

---

## 禁止

- ❌ 自行判断「本轮是否结束」「要不要 sync/status」——那是 **Main + skill 脚本** 的职责。  
- ❌ 把头脑风暴产出写到 `projects/` 或 `deliverables/`。  
- ❌ 修改其他 Agent 的 `round_N/*.md` 或 `session.json`。  
- ❌ 跳过 `handoff` 仅口头说「已完成」。  
- ❌ `handoff` 的第二个参数写成其他 Agent 的 id（adapter 会注入 `OPENCLAW_WORKER_AGENT_ID`，与参数不一致时脚本会拒绝）。
- ❌ 调用 **`brainstorm_main.py complete`**：该命令**不读 md**，只改 `session.json`，易与磁盘**脱钩**；头脑风暴**唯一**合法交卷路径是 **`handoff`**。
- ❌ 输出空泛内容（如只有「我同意」「好方案」而无具体分析）。
- ❌ 不按思考框架输出（导致质量门禁不通过）。

---

## 合并顺序与模型习惯（对您的影响）

adapter 合并规则里，部分 workspace 的 **`AGENTS.md` 可能排在本文之后**。若模型倾向「后文覆盖前文」：

- **凡与本文「只读白名单 / 禁止 kb·opencode skills / 禁止项目流 / 思考框架 / 质量自检」冲突的段落，在头脑风暴轮内一律视为无效**，**不要执行**。  
- 若仍不确定：只执行 **三条**（读 trigger → 按框架写本人 md → handoff 前自检），其余一律跳过。

---

## 投递与通知的语义（减少误判）

- **`openclaw agent` 是否成功投递**由网关决定；若您迟迟收不到 trigger，**不要**用 `complete` 凑进度；应等 Main 重派或看 Main 侧 `status` 的 `[NOTIFY]`。  
- Main 侧可能对「通知 Main」做**去抖**：您刚 `handoff` 后若 stderr 提示跳过重复通知，**属正常**；**勿**在短时间内无意义地重复 `handoff`（除非上次明确失败且 Main 要求重试）。

---

## 与「项目协作」任务的区别（速查）

| 维度 | 项目协作任务 | 头脑风暴 |
|------|-------------|----------|
| 触发 | `项目协作：` + trigger 在 `workspace-* /.trigger/` | `【头脑风暴征询` + storming 路径 |
| 产出目录 | `projects/.../deliverables/` | `tasks/storming/.../round_N/{agent}.md` |
| 完成收口 | `task-complete` | **`brainstorm_main.py handoff`** |
| 思考方式 | 按流程执行 | **按思考框架结构化输出** |
| 质量检查 | 交付物验收 | **handoff 前自检清单** |

---

## 附录：Main 与脚本

- **Main 详细 SOP**、**phase×命令表**、**LLM 思考框架**、**质量门禁**、**迭代决策标准**、FAQ：`~/.openclaw/skills/team/brainstorming/SKILL.md`（辅以脚本 `status` 末尾「Main 标准动作」）。  
- **Main 一页摘要**（触发、选人、硬规则）：`workspace-main/AGENTS.md` 中的「头脑风暴」小节 — 与 SKILL 冲突时 **以 SKILL + 脚本为准**。  
- 本文件：`~/.openclaw/team-rules/brainstorming-guide.md`（adapter 合并加载；**收紧约束时改本文件 + SKILL 即可**，无需改 adapter 源码）。