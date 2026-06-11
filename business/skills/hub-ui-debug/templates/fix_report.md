# Hub UI 修复记录

## 现象

（例：首页总览刷新后一直「加载中」，切 Tab 再回首页恢复正常）

## 根因

（一句话 + 文件:行号）

## 改动文件

| 文件 | 变更摘要 |
|------|----------|
| | |

## 验证

```text
$ bash business/skills/hub-ui-debug/scripts/check_frontend_js.sh
（粘贴 exit 0 的关键输出）

$ bash business/skills/hub-ui-debug/scripts/probe_hub_ui_api.sh
（粘贴结果）
```

## 浏览器手验

- [ ] 硬刷新后 Console 无红字
- [ ] 首页总览 ≤3s 出内容
- [ ] （如涉及）设置页保存正常

## 预防说明

（例：全局变量只在一处 let；改 JS 须 bump ?v=）
