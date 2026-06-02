"""系统配置 — 读写在 store/，路径来自 hub.paths。"""

import json
from pathlib import Path
from typing import Any

from hub.paths import SYSTEM_CONFIG_FILE

DEFAULT_CONFIG = {
    "system": {
        "port": 8765,
        "default_backend": "opencode",
        "default_model": "SenseNova/sensenova-6.7-flash-lite",
        "debug": False,
        "price_per_mtok": 0,
    },
    "backends": {
        "opencode": {
            "enabled": True,
            "cli_path": "",
            "model_aliases": {},
        },
    },
    "models": {
        "opencode": [
            {"id": "SenseNova/sensenova-6.7-flash-lite", "name": "SenseNova-sensenova-6.7-flash-lite", "provider": "SenseNova", "default": True},
        ],
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
        return self._data

    def update_all(self, data: dict):
        self._data = data
        self._save()

    def get_models(self, backend_id: str = "opencode") -> list:
        return self.get("models", backend_id, default=[])

    def get_default_model(self, backend_id: str = "opencode") -> str:
        for m in self.get_models(backend_id):
            if m.get("default"):
                return m["id"]
        return self.get("system", "default_model", default="")

    def get_cli_path(self, backend_id: str = "opencode") -> str:
        return self.get("backends", backend_id, "cli_path", default="")


system_config = SystemConfig()
