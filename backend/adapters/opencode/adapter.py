"""OpenCode CLI Adapter 实例。"""

import os
import subprocess
import time
from pathlib import Path
from typing import Generator

from adapter.events import AgentEvent, EventKind
from adapter.protocol import AdapterCapabilities, ModelInfo, RunRequest
from adapter.subprocess_cli import SubprocessCLIAdapter
from adapter.registry import registry
from adapters.opencode.parser import parse_line


class OpenCodeAdapter(SubprocessCLIAdapter):
    @property
    def id(self) -> str:
        return "opencode"

    @property
    def display_name(self) -> str:
        return "OpenCode CLI"

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            tool_use=True,
            multi_turn=True,
            custom_rules=True,
        )

    def _cli_path(self) -> str:
        try:
            from store.system_config import system_config
            p = system_config.get_cli_path("opencode")
            if p:
                return p
        except Exception:
            pass
        return os.environ.get(
            "OPENCODE_CLI_PATH",
            str(Path.home() / ".opencode" / "bin" / "opencode"),
        )

    def list_models(self, *, refresh: bool = False) -> list[ModelInfo]:
        """优先用 `opencode models` 的真实可用模型（带缓存，CLI 较慢）；失败回退静态配置。"""
        default_id = ""
        try:
            from store.system_config import system_config
            default_id = system_config.get_default_model("opencode") or ""
        except Exception:
            pass

        dynamic = self._query_opencode_models(refresh=refresh)
        if dynamic:
            return [
                ModelInfo(id=mid, name=mid.split("/", 1)[-1],
                          provider=mid.split("/", 1)[0] if "/" in mid else "",
                          default=(mid == default_id))
                for mid in dynamic
            ]

        try:
            from store.system_config import system_config
            cfg_models = system_config.get_models("opencode")
            if cfg_models:
                return [
                    ModelInfo(
                        id=m.get("id", ""),
                        name=m.get("name", m.get("id", "")),
                        provider=m.get("provider", ""),
                        default=bool(m.get("default")) or m.get("id", "") == default_id,
                    )
                    for m in cfg_models
                ]
        except Exception:
            pass
        return [
            ModelInfo("opencode/mimo-v2.5-free", "mimo-v2.5-free", "opencode", True),
        ]

    # `opencode models` 启动较慢（数秒），按进程级缓存（TTL 5 分钟）避免拖慢 /api/backends。
    _models_cache: list[str] = []
    _models_cache_ts: float = 0.0
    _MODELS_TTL = 300.0

    @classmethod
    def invalidate_models_cache(cls) -> None:
        cls._models_cache = []
        cls._models_cache_ts = 0.0

    def _query_opencode_models(self, *, refresh: bool = False) -> list[str]:
        now = time.time()
        cls = OpenCodeAdapter
        if (
            not refresh
            and cls._models_cache
            and (now - cls._models_cache_ts) < cls._MODELS_TTL
        ):
            return cls._models_cache
        cli = self._cli_path()
        if not os.path.isfile(cli):
            return []
        try:
            out = subprocess.run([cli, "models"], capture_output=True, text=True,
                                 timeout=20)
        except (subprocess.SubprocessError, OSError):
            return []
        models = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
        if models:
            cls._models_cache = models
            cls._models_cache_ts = now
        return models

    def get_default_model(self) -> str:
        for m in self.list_models():
            if m.default:
                return m.id
        return "opencode/mimo-v2.5-free"

    def run(self, request: RunRequest) -> Generator[AgentEvent, None, None]:
        cli_path = self._cli_path()
        if not os.path.isfile(cli_path):
            yield AgentEvent(EventKind.ERROR, {"message": f"OpenCode CLI 未找到: {cli_path}"})
            return

        cmd = [
            cli_path, "run",
            "--dangerously-skip-permissions",
            "--format", "json",
            "--thinking",
        ]
        if request.model:
            cmd.extend(["-m", request.model])
        if request.session_id:
            cmd.extend(["-s", request.session_id])
        cmd.extend(["--dir", request.workspace])
        if request.rules_file:
            cmd.extend(["-f", request.rules_file])

        env = os.environ.copy()
        if request.agent_id:
            env["OPENCLAW_WORKER_AGENT_ID"] = request.agent_id

        try:
            proc = subprocess.Popen(
                cmd, cwd=request.workspace, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1,
                start_new_session=True,
            )
            yield from self.stream_subprocess_io(
                proc,
                message=request.message,
                cancel_event=request.cancel_event,
                parse_line=parse_line,
            )

        except FileNotFoundError:
            yield AgentEvent(EventKind.ERROR, {"message": f"OpenCode CLI 未找到: {cli_path}"})
        except Exception as e:
            yield AgentEvent(EventKind.ERROR, {"message": str(e)})


registry.register(OpenCodeAdapter())
