"""
System Config - 统一工程配置管理
所有配置相对于工程根目录，支持运行时修改并持久化
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "data" / "system_config.json"

# ============ 默认配置 ============

DEFAULT_CONFIG = {
    "system": {
        "port": 8765,
        "default_backend": "opencode",
        "default_model": "SenseNova/sensenova-6.7-flash-lite",
        "debug": False,
    },
    "backends": {
        "opencode": {
            "enabled": True,
            "cli_path": "",  # 空=自动检测
            "model_aliases": {
                "SenseNova-sensenova-6.7-flash-lite": "SenseNova/sensenova-6.7-flash-lite",
                "SenseNova-deepseek-v4-flash": "SenseNova/deepseek-v4-flash",
                "opencode-mimo-v2.5-free": "opencode/mimo-v2.5-free",
                "opencode-deepseek-v4-flash-free": "opencode/deepseek-v4-flash-free",
            },
        },
    },
    "models": {
        "opencode": [
            {"id": "SenseNova/sensenova-6.7-flash-lite", "name": "SenseNova-sensenova-6.7-flash-lite", "provider": "SenseNova", "default": True},
            {"id": "opencode/mimo-v2.5-free", "name": "opencode-mimo-v2.5-free", "provider": "opencode", "default": False},
            {"id": "opencode/deepseek-v4-flash-free", "name": "opencode-deepseek-v4-flash-free", "provider": "opencode", "default": False},
        ],
    },
}


class SystemConfig:
    """系统配置管理器"""

    def __init__(self):
        self._data: dict = {}
        self._load()

    def _load(self):
        """加载配置，不存在则创建默认"""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        else:
            self._data = {}
            self._merge_defaults()
            self._save()

        # 尝试从旧 openclaw.json 合并未覆盖的值
        self._merge_from_openclaw_json()

    def _save(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def _merge_defaults(self):
        """合并默认值（不覆盖已有）"""
        self._deep_merge(self._data, DEFAULT_CONFIG)

    def _deep_merge(self, target: dict, source: dict):
        for key, val in source.items():
            if key not in target:
                target[key] = val
            elif isinstance(val, dict) and isinstance(target.get(key), dict):
                self._deep_merge(target[key], val)

    def _merge_from_openclaw_json(self):
        """从旧版 ~/.openclaw/openclaw.json 读取模型别名"""
        old_cfg = Path.home() / ".openclaw" / "openclaw.json"
        if not old_cfg.exists():
            return
        try:
            with open(old_cfg, encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            return

        aliases = (
            old.get("agents", {})
            .get("defaults", {})
            .get("cliBackends", {})
            .get("cli", {})
            .get("modelAliases", {})
        )
        if aliases:
            bc = self._data.setdefault("backends", {}).setdefault("opencode", {})
            existing = bc.setdefault("model_aliases", {})
            for k, v in aliases.items():
                if k not in existing and k != "default":
                    existing[k] = v

        # 默认模型
        default_model = (
            old.get("agents", {})
            .get("defaults", {})
            .get("subagents", {})
            .get("model", "")
        )
        if default_model:
            stripped = default_model.removeprefix("cli/")
            sys_cfg = self._data.setdefault("system", {})
            if "default_model" not in sys_cfg:
                sys_cfg["default_model"] = aliases.get(stripped, stripped)

        self._save()

    def get(self, *keys: str, default: Any = None) -> Any:
        """深层读取配置项"""
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
                if val is None:
                    return default
            else:
                return default
        return val

    def set(self, value: Any, *keys: str):
        """深层设置配置项"""
        val = self._data
        for k in keys[:-1]:
            if k not in val or not isinstance(val[k], dict):
                val[k] = {}
            val = val[k]
        val[keys[-1]] = value
        self._save()

    def get_all(self) -> dict:
        return self._data

    def update_all(self, data: dict):
        """全量更新配置"""
        self._data = data
        self._save()

    def get_model_aliases(self, backend_id: str = "opencode") -> dict:
        """获取指定后端的模型别名映射"""
        return self.get("backends", backend_id, "model_aliases", default={})

    def get_models(self, backend_id: str = "opencode") -> list:
        """获取指定后端的模型列表"""
        return self.get("models", backend_id, default=[])

    def get_default_model(self, backend_id: str = "opencode") -> str:
        """获取默认模型"""
        models = self.get_models(backend_id)
        for m in models:
            if m.get("default"):
                return m["id"]
        return self.get("system", "default_model", default="")

    def get_cli_path(self, backend_id: str = "opencode") -> str:
        """获取 CLI 路径"""
        return self.get("backends", backend_id, "cli_path", default="")

    def get_system_port(self) -> int:
        return self.get("system", "port", default=8765)

    def set_system_port(self, port: int):
        self.set(port, "system", "port")


# 全局实例
system_config = SystemConfig()