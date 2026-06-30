"""Session 映射 — Adapter 无关，键 = adapter_id:agent_id:workspace。"""

import json
import time
from pathlib import Path
from typing import Optional

from common.paths import SESSION_MAP_FILE

try:
    import fcntl
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


class SessionStore:
    def __init__(self, path: Path = SESSION_MAP_FILE):
        self.path = path
        self.lock_path = Path(str(path) + ".lock")
        self._map: dict = {}
        self._load()

    def _lock(self):
        if not _HAS_FLOCK:
            return None
        try:
            f = open(self.lock_path, "w")
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            return f
        except Exception:
            return None

    def _unlock(self, f):
        if f and _HAS_FLOCK:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                f.close()
            except Exception:
                pass

    def _load(self):
        f = self._lock()
        try:
            if self.path.exists():
                with open(self.path, encoding="utf-8") as fp:
                    self._map = json.load(fp)
        except Exception:
            self._map = {}
        finally:
            self._unlock(f)

    def _save(self):
        f = self._lock()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fp:
                json.dump(self._map, fp, indent=2, ensure_ascii=False)
        finally:
            self._unlock(f)

    def _key(self, adapter_id: str, agent_id: str, workspace_key: str) -> str:
        return f"{adapter_id}:{agent_id}:{workspace_key}"

    def get(self, adapter_id: str, agent_id: str, workspace_key: str) -> Optional[str]:
        entry = self._map.get(self._key(adapter_id, agent_id, workspace_key))
        if entry:
            entry["last_used"] = time.time()
            self._save()
            return entry.get("session_id")
        return None

    def set(self, adapter_id: str, agent_id: str, workspace_key: str, session_id: str):
        self._map[self._key(adapter_id, agent_id, workspace_key)] = {
            "session_id": session_id,
            "created_at": time.time(),
            "last_used": time.time(),
        }
        self._save()

    def remove(self, adapter_id: str, agent_id: str, workspace_key: str):
        k = self._key(adapter_id, agent_id, workspace_key)
        if k in self._map:
            del self._map[k]
            self._save()

    def remove_for_agent_workspace(self, agent_id: str, workspace_key: str) -> int:
        """移除某 Agent 在指定 workspace_key 下所有 Adapter 的 session 映射。"""
        suffix = f":{agent_id}:{workspace_key}"
        to_del = [k for k in self._map if k.endswith(suffix)]
        for k in to_del:
            del self._map[k]
        if to_del:
            self._save()
        return len(to_del)


session_store = SessionStore()

# 兼容旧 opencode_session_map.json
_legacy = SESSION_MAP_FILE.parent / "opencode_session_map.json"
if _legacy.exists() and not SESSION_MAP_FILE.exists():
    try:
        SESSION_MAP_FILE.write_text(_legacy.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        pass
