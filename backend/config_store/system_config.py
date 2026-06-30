"""系统配置 — 读写在 store/，路径来自 common.paths。"""

import json
from pathlib import Path
from typing import Any

from common.paths import SYSTEM_CONFIG_FILE

DEFAULT_CONFIG = {
    "system": {
        "port": 8765,
        "default_backend": "opencode",
        "default_model": "sensenova/sensenova-6.7-flash-lite",
        "debug": False,
        "price_per_mtok": 0,
        "default_review": False,
        "audit_log": False,
        "audit_log_max_bytes": 500000,
        "coordinator_agent_id": "main",
        "deputy_agent_id": "deputy",
        # P0 边界澄清：旧路径清理（0.6）
        "use_sqlite_project_store": False,
        # P0 边界澄清：code_project outcome_kind 检测（0.2）
        "use_outcome_kind_detection": False,
        # P0 边界澄清：PGD 严格类型配置化（0.3）
        "use_strict_must_include_config": False,
        # P0 边界澄清：KB API 抽象修复（0.5）
        "use_kb_backend_for_observability": False,
        # P2 硬编码配置化
        "placeholder_markers": ["待补充", "待填写", "todo", "tbd", "tbd", "xxx", "lorem ipsum", "占位"],
        "blocked_markers": ["signin", "unhuman", "/account/", "captcha", "verify", "登录知乎", "网络环境存在异常"],
        "code_extensions": [".py", ".sh", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".h", ".c", ".rb", ".php", ".swift"],
        # rules 规则文件配置 — 每个 profile 对应的文件名（可覆盖）
        "rules": {
            "profile_filenames": {
                "interactive": "interactive-guide.md",
                "discussion": "brainstorming-guide.md",
                "workflow_execute": "worker-template.md",
                "ethos": "ethos.md",
            },
        },
    },
    "backends": {
        "opencode": {
            "enabled": True,
            "cli_path": "",
            "model_aliases": {},
        },
        "claude": {
            "enabled": True,
            "cli_path": "",
        },
    },
}


class SystemConfig:
    def __init__(self):
        self._data: dict = {}
        self._load()

    def _load(self):
        SYSTEM_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if SYSTEM_CONFIG_FILE.exists():
            try:
                with open(SYSTEM_CONFIG_FILE, encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        if not self._data:
            self._data = {}
            self._deep_merge(self._data, DEFAULT_CONFIG)
            self._save()

    def _save(self):
        with open(SYSTEM_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def _deep_merge(self, target: dict, source: dict):
        for key, val in source.items():
            if key not in target:
                target[key] = val
            elif isinstance(val, dict) and isinstance(target.get(key), dict):
                self._deep_merge(target[key], val)

    def get(self, *keys: str, default: Any = None) -> Any:
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
                if val is None:
                    return default
            else:
                return default
        return val

    def get_all(self) -> dict:
        data = dict(self._data)
        data.pop("models", None)
        return data

    def update_all(self, data: dict):
        preserved_models = self._data.get("models")
        self._data = dict(data)
        self._data.pop("models", None)  # 模型列表由 /api/backends 管理，不接受设置页 PUT
        if preserved_models:
            self._data["models"] = preserved_models
        self._save()

    def get_models(self, backend_id: str = "opencode") -> list:
        return self._data.get("models", {}).get(backend_id, [])

    def get_default_model(self, backend_id: str = "opencode") -> str:
        for m in self.get_models(backend_id):
            if m.get("default"):
                return m["id"]
        return self.get("system", "default_model", default="")

    def get_cli_path(self, backend_id: str = "opencode") -> str:
        return self.get("backends", backend_id, "cli_path", default="")


system_config = SystemConfig()
