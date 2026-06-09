"""OpenCode CLI Adapter 实例。"""

import os
import signal
import subprocess
import threading
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

        proc = None
        cancelled = False
        stop_watch = threading.Event()
        watcher = None
        try:
            proc = subprocess.Popen(
                cmd, cwd=request.workspace, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1,
                start_new_session=True,
            )

            stderr_buf: list[str] = []

            def _drain_stderr() -> None:
                try:
                    if proc.stderr:
                        stderr_buf.append(proc.stderr.read())
                except Exception:
                    pass

            stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
            stderr_thread.start()
            # 看门狗在 opencode 空闲时会置 cancel_event，但此时 `for line in proc.stdout`
            # 正阻塞读、不会再检查取消标志。用旁路线程监听取消并杀「整个进程组」——既能
            # 解除 stdout 阻塞（管道关闭→循环结束），又能连 opencode 的子进程一起回收，
            # 避免被孤儿化（reparent 到 init）造成进程泄漏。
            cancel_event = request.cancel_event
            if cancel_event is not None:
                def _canceller(p=proc, ev=cancel_event, stop=stop_watch):
                    while not stop.wait(0.3):
                        if p.poll() is not None:
                            return
                        if ev.is_set():
                            self._terminate_group(p)
                            return
                watcher = threading.Thread(target=_canceller, daemon=True)
                watcher.start()

            try:
                proc.stdin.write(request.message)
            except Exception:
                pass
            proc.stdin.close()

            # 注意：先 yield 当前行事件，再检查 cancel，保证 step_finish 行（含 token 计量）
            # 在取消信号到来时依然能从 stdout 缓冲中被读出并上报。
            for line in proc.stdout:
                for ev in parse_line(line):
                    yield ev
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    # 不立即 break：继续排空剩余缓冲行（含 step_finish 行），
                    # 进程会在 canceller 线程 300ms 内被杀死后自然 EOF。

            if cancelled:
                return

            proc.wait()
            stderr_thread.join(timeout=2.0)
            stderr_out = "".join(stderr_buf)
            if stderr_out.strip():
                yield AgentEvent(EventKind.ERROR, {"message": stderr_out.strip()})

        except FileNotFoundError:
            yield AgentEvent(EventKind.ERROR, {"message": f"OpenCode CLI 未找到: {cli_path}"})
        except Exception as e:
            yield AgentEvent(EventKind.ERROR, {"message": str(e)})
        finally:
            stop_watch.set()
            self._terminate_group(proc)
            if watcher is not None:
                watcher.join(timeout=1)

    @staticmethod
    def _terminate_group(proc) -> None:
        """杀掉整个进程组（opencode 以 start_new_session=True 起，其子进程同组）。

        先 SIGTERM 整组、给 2s 退出窗口，未退则 SIGKILL；拿不到进程组时退回单进程 kill。
        """
        if proc is None or proc.poll() is not None:
            return
        try:
            pgid = os.getpgid(proc.pid)
        except (ProcessLookupError, OSError):
            pgid = None
        try:
            if pgid is not None:
                os.killpg(pgid, signal.SIGTERM)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=2)
                return
            except subprocess.TimeoutExpired:
                pass
            if pgid is not None:
                os.killpg(pgid, signal.SIGKILL)
            else:
                proc.kill()
            proc.wait(timeout=2)
        except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
            pass


registry.register(OpenCodeAdapter())
