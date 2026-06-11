# Prompt 注入配置（Strategy Registry）

内核 `backend/common/prompt_injections.py` 在 `build_worker_prompt()` 中按本文件拼入额外块。

## 结构

```yaml
injections:
  execute:
    global:
      when: has_skill_router    # always | has_skill_router
      blocks:
        - |
          多行文本，占位符 {myteam_root} {all_playbook} …
    by_task_type:
      diagram-build:
        blocks:
          - |
            task_type 专用块
```

## 占位符

由 `build_injection_variables()` 提供，可在 yaml 中使用：

| 键 | 含义 |
|----|------|
| `{myteam_root}` | 项目根 |
| `{all_playbook}` | ALL.md 路径 |
| `{catalog}` | catalog.yaml 路径 |
| `{scaffold_process}` | scaffold 脚本路径 |
| `{diagram_execution}` | diagram means 说明 |
| `{diagram_probe}` | diagram 探针脚本 |

扩展占位符：在 yaml 写 `{myteam_root}/business/...` 或后续在 `build_injection_variables()` 增加键。

## 原则

- **内核**：只实现「读取 + when 判断 + 渲染」，不写业务文案。
- **本文件**：B 层 ALL/catalog/means 指引等内容在此维护。
