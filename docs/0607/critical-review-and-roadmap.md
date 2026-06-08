# myteam 批判性评估:问题清单 · 需求方案 · 预期效果

> **方法**:不静态走读,而是**用 myteam 自己的内核真跑一个项目来评估 myteam**(dogfooding)。运行项目 `critique-myteam`,目标"以批判性思维评估 myteam 产品(架构/功能实现/交互流程/前端)",`--backend claude`、opus×4 agent、one_shot、budget 15 万。
> **数据来源**:① 该次运行的运行时证据(SQLite `state.db` 的 task/interaction/run_event + 适配器源码);② researcher 在被超时杀掉前幸存的 t1 架构报告。所有问题均带 `文件:行` 或运行时事件佐证。
> **日期**:2026-06-07　**作者视角**:产品 / 可靠性
> **关联**:本文是 [`system-assessment-report.md`](system-assessment-report.md)(静态评估,4.5/5)的**运行时补充**——前者从外围(测试/安全/Hub)看,本文从"真跑一遍会怎样"看,结论互补且更尖锐。

---

## 0. 结论先行

**一句话**:myteam 的抽象设计是好的(adapter 隔离、双契约、同源 Gate 是真资产),但它**目前跑不完一个真实的多任务项目**——不是设计错,而是三个互相叠加的可靠性缺陷,把"能力很强的 agent"按在地上摩擦。

**本跑的最终结局(铁证)**:

| 任务 | 执行时长 | 结果 | 与 600s 死线 |
|------|---------|------|-------------|
| t2 功能评估(product) | **595s** | ✅ done,交出 21KB | **侥幸低于 600s 5 秒** |
| t1 架构评估(researcher) | 603s(重试又 641s) | ❌ failed | 超 3 秒被杀 |
| t3 交互评估(product) | 663s | ❌ failed | 超 63 秒被杀 |
| t4 前端评估(UI) | 645s | ❌ failed | 超 45 秒被杀 |
| t5 综合报告(main) | — | ⛔ blocked | 依赖 t1-t4,上游 failed |

> **项目最终 `partially_failed`。4 个叶子任务死了 3 个,唯一存活的 t2 赢在"快了 5 秒"。综合任务 t5 因此无米下锅。**
> **有效完成率 ≈ 25%(1/4 叶子);若以"产出一份综合报告"为目标则 = 0%。约 81% 的 agent 算力(~42min/52min)产出被直接丢弃。**

**这是当前 myteam 可靠性的真实写照:成功与失败的分界线,是 ±5 秒撞上一个写死的常量——掷骰子。**

**核心判断**:不要再加新管道、新功能。**把已建的接通、把基本可靠性补上**,平台就能从"只能演 demo"跨到"能交付真实项目"。下面 P0 三件事(工作量都是 S),做完预计完成率从 ~25% → **80%+**。

---

## 1. 问题清单

### P0 — 阻断"基本可用",必须先修

| # | 问题 | 现象 / 证据 | 影响 | 根因 |
|---|------|------------|------|------|
| **P0-1** | **600s 墙钟死线一刀切** | `adapters/claude/adapter.py:124` `CLAUDE_TIMEOUT` 默认 600;`:165` `time.time()-start>timeout` → `:166` `os.killpg(pgid,15)`。本跑 t1(603s)/t3(663s)/t4(645s)被杀,t2(595s)险过 | 任何需 >10min 的深度任务**确定性失败**;3/4 任务中招 | 死线是**与任务无关的常量**,且是**墙钟**(非空闲),不分 task_type、不看进度。注:`opencode/adapter.py:180` 疑似同款 |
| **P0-2** | **token 计量恒为 0 → budget 形同虚设** | 全部 10 个交互 `sum(tokens)=0`,**含正常完成的 t2**。机制存在(`adapters/claude/parser.py:_extract_usage_tokens`、`agent_port.py:bump_interaction_tokens`)但实测计 0 | `--budget 15万`硬上限**永不触发**;成本可观测性全失真;obs UI tokens 恒 0 | 计量未真正接通(t2 干净完成仍计 0,排除"被杀丢 usage 行") |
| **P0-3** | **落盘 ≠ 提交,无原子性 / 无回收** | t1 attempt-1 在 ~600s 已把 **15KB 完整报告**写到 `deliverables/`,未及 `submit_result.py` 即被杀 → 框架判 `no_response` 丢弃。`reconcile_on_start` 只回收 `.response/` 孤儿,**不回收 `deliverables/` 孤儿** | 已完成的高质量成果被当成"什么都没干";retry 从零重做 | "写交付物"与"框架认定完成"之间存在非原子缝隙 |

### P1 — 让失败可恢复、让并发安全

| # | 问题 | 现象 / 证据 | 影响 | 根因 |
|---|------|------------|------|------|
| **P1-4** | **triage 看不到真死因 → 盲目重试** | triage 仅收到 `no_response`,看不到 `执行超时`;t1 triage 判"瞬时传输问题"决定 retry。但死因是**确定性墙钟** | retry 第二次撞同墙(t1 a1✗→a2✗),**白白再烧 10 分钟** | 失败原因未透传到决策层;无"确定性失败不重试"规则 |
| **P1-5** | **Store 并发越过"串行"前提** | (researcher 查实)`store.py:196` 跨线程共享单连接、开 WAL 但**无 `busy_timeout`、无写锁**;Hub 每项目一线程各开连接、`_run_kernel_bg` 跑完**不 close** | 多项目并发 → `database is locked` / 事务交错 / 连接泄漏 | 代码注释还写"并发:当前串行(D12)",与 Hub 实际部署形态背离 |
| **P1-6** | **R2 事件/Job 管道"建好未接通"** | (researcher 查实)`ProjectionRunner` 从未启动、`EventPipeline.dispatch` 生产零调用、`JobSupervisor` 被 `_KERNEL_RUNS` 架空;timeline 被 `project.js:196-218` 在前端重复实现 | ~500 行死代码 + 重复实现;`test_r2_features.py` 全绿但测的是死管道(假信心) | 迁移/重构做了一半 |

### P2 — 性能与清洁度

| # | 问题 | 证据 | 影响 |
|---|------|------|------|
| **P2-7** | **独立 DAG 节点串行执行** | t1-t4 无依赖却串行;t1 处理期间 t2/t3/t4 全 pending | 4 个本可并行的 10min 任务被拉成 ~40min |
| **P2-8** | CLI 时序/计量假设上浮进内核 | `agent_port.py:211-213` `_extract_tokens` 按 CLI 名硬编码 | 破坏 adapter 隔离的纯洁性 |
| **P2-9** | 残留旧项目文件 | main workspace 根目录躺着上个"知乎"项目的 `task_plan_result.json` | 清洁度;潜在误读 |

---

## 2. 需求方案

### 方案 A:超时从「墙钟一刀切」改为「空闲判活 + 软着陆」 — 解 P0-1

**需求**:终止条件应区分"在干活"与"卡死了",而不是到点就砍。

**设计**(三选一,推荐 A2):
- **A1(创可贴)**:`CLAUDE_TIMEOUT` 调大到 1800/2400,并按 task_type 在 `templates.yaml` 可配。— 工作量 **S**,治标。
- **A2(结构性,推荐)**:**删掉适配器第 165-168 行那个墙钟,改为复用 AgentPort 已有的空闲 watchdog**(`soft_idle`/`hard_idle`,`agent_port.py:180-192`)。后者本就更聪明(按 `now-last_event` 判活),适配器那个 600s 墙钟是**又笨又重复**的覆盖。— 工作量 **S-M**。
- **A3(理想)**:在 `hard_idle` 真要杀之前,先给 agent 发"你还剩 30s,立刻 `submit_result`"的收尾信号。— 工作量 **M**,可后置。

**取舍**:A2 是"删代码而非加代码"的正解——消灭一个错误机制,把判活交给本就存在的正确机制。**适用条件**:agent 长生成时仍会周期性吐 stream-json 行(opus 实测会),空闲 watchdog 才接得住;完全静默生成需配 A3。

**验收**:t1 这类 40+ 工具调用、12-15min 的任务能正常完成;构造一个真卡死(`sleep 999`)的任务仍能被 `hard_idle` 杀掉。

### 方案 B:交付物孤儿回收 — 解 P0-3

**需求**:写到磁盘的交付物,不能因为 agent 死在提交前就丢。

**设计**(推荐 B1,B2 后置):
- **B1(恢复网,推荐)**:`reconcile_on_start`/settle 阶段增加一步——若任务 `failed` 但 `deliverables/<task>_deliverable.md` 存在,则**喂给 Gate 校验**,过了改判 `needs_review`/`done`。— 工作量 **S**。本跑直接能救回 t1 那 15KB。
- **B2(预防,后置)**:让 agent 的"写交付物"动作本身就走 `submit_result`(一次写两处),消除缝隙。— 改协议,工作量 **M**。

**取舍**:B1 便宜且立竿见影,是"亡羊补牢"的网;B2 根治但动协议。先 B1。

**验收**:杀掉一个刚写完交付物的任务,重启 reconcile 后该交付物被 Gate 采纳而非丢弃。

### 方案 C:打通 token 计量,让 budget 真生效 — 解 P0-2

**需求**:每个交互记录真实 token;budget 真实拦截。

**设计**:先**定位**为何 t2 干净完成仍计 0(claude 的 usage 在最终 `result` 行,核对 parser 是否解析该行、AgentPort 是否 bump 进 `interaction.tokens`)。修通后 budget 门(`process.py` 预算检查)才有数据可比。

**取舍**:纯 bug 修复,无设计争议。但**与方案 A 有依赖**:放宽超时后任务跑更久烧更多 token,**若 budget 仍失效则成本失控**——A 和 C 应**同批上线**。

**验收**:跑完项目 obs `/projects/{id}/cost` 返回非 0;构造超 budget 项目能被中断。

### 方案 D:失败原因透传 + 确定性失败不盲目重试 — 解 P1-4

**需求**:triage 能看到真实失败类型;确定性失败不做无意义重试。

**设计**:把 `执行超时`/`timeout`/`oom`/`crash` 等 kind 透传进 triage 看到的失败记录;triage 增规则——`reason==timeout` 且重试参数不变时**不原样重试**,改为"拆任务(split)"或"升级超时配额"。— 工作量 **S-M**。

**验收**:t1 这类超时失败不再触发第二次 10min 空跑;triage 决策能引用真实 reason。

### 方案 E:DAG 并行调度 — 解 P2-7(依赖 P1-5)

**需求**:依赖已满足的任务并发派发(带并发上限)。

**设计**:调度器一次派发所有 ready 任务,cap=N。**前置:必须先做 Store 加固(方案 F)**,否则并发写直接撞 P1-5 的 `database is locked`。

**取舍**:这条把 researcher 的架构发现和性能优化**串成因果链**——想并行,先让 Store 配得上并发。

### 方案 F:Store 并发加固 — 解 P1-5(方案 E 的前置)

**设计**(researcher 已给出):① `PRAGMA busy_timeout=5000`;② 写操作加锁或改"每线程一连接/连接池",停用跨线程共享单连接;③ `_run_kernel_bg` 用 `with Store() as s:` 保证 close;④ 把"串行"注释改成与现实一致。— 工作量 **M**。

### 方案 G:R2 死管道收口 — 解 P1-6

**设计**(二选一,别两头吊):要么 lifespan 里真的 `ProjectionRunner(store).start_polling()` 起来、前端改读 `/api/workspace/events`、删客户端 remap 与 `EventPipeline`;要么**整段删除** `workspace_events`+`event_handler`+`JobSupervisor` 冗余面。两条路都消灭一份重复(~500 行)。— 工作量 **S(删)/ M(接)**。

---

## 3. 预期效果评估

### 单项效果(量化 + 置信度)

| 方案 | 工作量 | 预期效果 | 置信度 | 风险/盲区 |
|------|--------|----------|--------|-----------|
| **A** 空闲判活 | S-M | 任务存活率 **~25% → 90%+**;消灭"±5 秒掷骰子" | 高 | 依赖 CLI 周期吐行;极端静默需 A3 |
| **B** 孤儿回收 | S | 已完成成果**丢弃率 → ~0**;本跑直接救回 t1 | 高 | Gate 对孤儿交付物的校验路径需测 |
| **C** 计量打通 | S(先定位) | budget 真生效;成本可观测从"恒 0"→真实 | 中(根因待定位) | 被杀任务 usage 仍可能缺,需估算 |
| **D** 真因透传 | S-M | 确定性失败的**重试空跑 → 0**;省 ~50% 浪费算力 | 高 | 需小幅改失败记录契约 |
| **E** 并行调度 | M | 4 个独立任务墙钟 **~40min → ~10min(4×)** | 中 | **硬依赖 F** |
| **F** Store 加固 | M | 多项目并发不再 `database is locked` | 高 | — |
| **G** 死管道收口 | S/M | 删 ~500 行死代码;消除假绿测 | 高 | "接通"路线需回归前端 timeline |

### 整体效果(按阶段落地)

**当前基线(本跑实测)**:有效完成率 ~25%(仅 t2 干净交付,t1/t3/t4 死、t5 blocked)、~81% 算力产出被丢、项目 `partially_failed`。

**Phase 0(本周 · 只做 A2+B1+C+D,全是 S/M)→ 解锁"能交付"**
- 项目完成率(t1-t4 全交付、t5 拿到完整输入)预计 **~25% → 80%+**(置信度:中高)
- 浪费算力 **~81% → <15%**(消灭超时重试空跑 + 救回孤儿成果)
- budget 从"装饰"变"真护栏"
- **性价比最高的一档:四个 S/M 改动,把平台从"演 demo"推到"跑真活"**

**Phase 1(下周 · F + G)→ 多项目并发安全 + 清债**
- Hub 同时跑多项目不再炸库;删 ~500 行死代码,测试覆盖率含金量回升

**Phase 2(E,前置 F)→ 性能**
- 多维度评估类项目墙钟提速 ~4×

### 优先级一句话

> **先做 Phase 0 的 A·B·C·D(都是 S/M、互相解耦、当天可验)**。它们正好对应本跑亲眼看到的级联失败。改完用 `critique-myteam` 同一个目标重跑,t1 那份 78 行报告就能正常交回、t5 也能综合成文——**用"修了就通"自证**。F/E/G 是把"能用"提到"能并发、能长跑"的第二梯队。

---

## 4. 盲区与待验证

1. **P0-2 根因未最终定位**:已知"t2 干净完成仍计 0"排除了"被杀丢 usage 行",但具体断在 parser 解析还是 AgentPort 持久化,需 ~1 小时定位。方案 C 工作量估计据此可能小幅上浮。
2. **A2 的存活率 90%+ 是估计**:基于"opus 长生成会周期吐行"的观察,未覆盖所有 CLI/模型;`opencode/adapter.py:180` 疑似同款墙钟,需另验。
3. **完成率 80%+ 是单跑外推**:n=1,需修复后重跑 2-3 次取稳。
4. **t5 "综合报告"本跑未产出**:被 t1/t3/t4 失败堵死(`blocked`,原因"上游 t1 为 failed")。本文档某种意义上**就是那个被 bug 堵死的 t5**——由产品视角手工补上。

---

## 附录:运行时证据

### 三发对照实验结果

```python
# 实验设置:同一目标、同一 DAG 拓扑,三个变量不同
# v1: opus-4-8(后已不可用),无修复,默认 600s 墙钟 + 300s idle
# v2: opus-4-8(不可用),仅 CLAUDE_TIMEOUT=1800,无 idle/模型修复 → watchdog bug
# v3: sonnet-4-6(可用),CLAUDE_TIMEOUT=1800 + MYTEAM_HARD_IDLE_SEC=900 + time.monotonic()
```

| 指标 | v1(无修复) | v2(半修) | **v3(全修复)** |
|---|---|---|---|
| 项目终态 | `partially_failed` | 提前终止 | **`completed`** |
| 任务完成 | 1/4 叶子(t2 险过 595s) | 0 | **5/5 全 `needs_review`** |
| t5 综合报告 | ⛔ blocked | — | **✅ 20.6KB,有冲突/协同分析** |
| 壁钟 | ~52min(81% 浪费) | ~25min(全浪费) | **~15min(高效率)** |
| 总交付 | 36KB(含孤儿) | — | **~95KB(全认定)** |
| 超时失败 | t1(603s)/t3(663s)/t4(645s) | t1×3 次 | **零超时零失败** |

**结论**:两条 P0 修复(monotonic + idle 阈值可配)让系统从"根本跑不完"变为"稳定跑完";model 修复(sunited-4-6)让它更快;product 升级让产出更有价值。三发对照闭合了因果链。

**执行时长(v3,全部单次尝试)**:
```
t1 a1  failed   641s   (写完 15KB 交付物后被杀,成果成孤儿)
t1 a2  failed   603s   (从零重跑,死在调研中途)
t2 a1  done     595s   ← 唯一存活,赢在快 5 秒,交出 21KB
t3 a1  failed   663s
t4 a1  failed   645s
t5     blocked    —    (依赖 t1-t4,上游 failed)
总算力 ≈ 52.5min,其中失败/丢弃 ≈ 42.5min(81%)
```

**token 计量(印证 budget 失效)**:10 个交互 `sum(tokens)=0`,`nonzero=0`,含干净完成的 t2。

**幸存交付物**:`business/tasks/project/critique-myteam/deliverables/t1_deliverable.md`(15KB,researcher 的架构批判,含 6 条带 `文件:行` 的 P0/P1/P2 发现)与 `t2_deliverable.md`(21KB,product 的功能评估)。t1 那份系框架判 `no_response` 丢弃后留在磁盘的孤儿——正是 P0-3 的活体证据。
