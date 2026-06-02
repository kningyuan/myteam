"""OpenCode CLI Adapter 实例。"""

import os
import subprocess
import time
from pathlib import Path
from typing import Generator

from adapter.events import AgentEvent, EventKind
from adapter.protocol import AdapterCapabilities, CLIAdapter, ModelInfo, RunRequest
from adapter.registry import registry
from adapters.opencode.parser import parse_line


class OpenCodeAdapter(CLIAdapter):
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

    def list_models(self) -> list[ModelInfo]:
        """优先用 `opencode models` 的真实可用模型（带缓存，CLI 较慢）；失败回退静态配置。"""
        default_id = ""
        try:
            from store.system_config import system_config
            default_id = system_config.get_default_model("opencode") or ""
        except Exception:
            pass

        dynamic = self._query_opencode_models()
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

    def _query_opencode_models(self) -> list[str]:
        now = time.time()
        cls = OpenCodeAdapter
        if cls._models_cache and (now - cls._models_cache_ts) < cls._MODELS_TTL:
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

        timeout = int(os.environ.get("OPENCODE_TIMEOUT", "600"))
        start = time.time()

        proc = None
        cancelled = False
        try:
            proc = subprocess.Popen(
                cmd, cwd=request.workspace, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1,
                start_new_session=True,
            )
            try:
                proc.stdin.write(request.message)
            except Exception:
                pass
            proc.stdin.close()

            for line in proc.stdout:
                if request.cancel_event and request.cancel_event.is_set():
                    cancelled = True
                    break
                if time.time() - start > timeout:
                    proc.kill()
                    yield AgentEvent(EventKind.ERROR, {"message": "执行超时"})
                    return
                for ev in parse_line(line):
                    yield ev

            if cancelled:
                return

            proc.wait()
            stderr_out = proc.stderr.read() if proc.stderr else ""
            if stderr_out.strip():
                yield AgentEvent(EventKind.ERROR, {"message": stderr_out.strip()})

        except FileNotFoundError:
            yield AgentEvent(EventKind.ERROR, {"message": f"OpenCode CLI 未找到: {cli_path}"})
        except Exception as e:
            yield AgentEvent(EventKind.ERROR, {"message": str(e)})
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    pass


registry.register(OpenCodeAdapter())
