"""REG 脚本共享 budget 默认值 — dogfooding 不因规划期 token 误触暂停。

大元帅约定：myteam 回归/E2E 须给足 token 上限，避免 paused/blocked。
可通过环境变量 REG_DEFAULT_BUDGET 覆盖（默认 5_000_000）。
"""
from __future__ import annotations

import os

# 规划期单次 interaction 即可 10万+ token；REG 默认给足余量
REG_DEFAULT_BUDGET = int(os.environ.get("REG_DEFAULT_BUDGET", "5000000"))
