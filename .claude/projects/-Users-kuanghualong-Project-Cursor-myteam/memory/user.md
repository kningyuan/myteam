---
name: skill-installation-rule
description: 所有 skill 必须先放到 ~/skill/ 作为源码，再通过软链接注册到 business/skills/ 目录
metadata:
  type: user
---

**规则：skill 安装流程**

1. 新建或修改 skill 时，源码放在 `/Users/kuanghualong/skill/` 目录下
2. 注册到项目时，通过软链接形式链接到 `business/skills/`，而不是直接复制文件
3. 示例：`ln -sfn ~/skill/pm-product-discovery business/skills/pm-product-discovery`

**Why：** 用户希望 skill 的单一数据源在 `~/skill/`，项目只持有引用（软链），避免重复维护和同步问题。

**How to apply：** 任何时候用户要求创建、安装、注册 skill，都要遵循这个两阶段流程——先写源码到 `~/skill/`，再创建软链接到 `business/skills/`。
