"""Claude Code CLI 实例 — 适配器层唯一知道 Claude Code 格式与命令行的地方。"""

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Generator, Optional

from adapter.events import AgentEvent, EventKind
from adapter.protocol import AdapterCapabilities, CLIAdapter, ModelInfo, RunRequest

from adapters.claude.parser import parse_line


class ClaudeCodeAdapter(CLIAdapter):
    @property
    def id(self) -> str:
        return "claude"

    @property
    def display_name(self) -> str:
        return "Claude Code CLI"

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            streaming=True,
            tool_use=True,
            multi_turn=True,
            custom_rules=True,
        )

    def _cli_path(self) -> str:
        """探测 Claude Code CLI 路径。

        优先级：
          1. system_config.backends.claude.cli_path
          2. CLAUDE_CLI_PATH 环境变量
          3. PATH 中的 claude
          4. 回退 npx
        """
        try:
            from store.system_config import system_config
            p = system_config.get_cli_path("claude")
            if p:
                return p
        except Exception:
            pass

        env_path = os.environ.get("CLAUDE_CLI_PATH", "")
        if env_path:
            return env_path

        # 检查 PATH 中是否有 claude
        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = Path(p) / "claude"
            if candidate.exists():
                return str(candidate)

        # 回退到 npx
        return "npx"

    def _cli_args(self) -> list[str]:
        """构建基础 CLI 参数列表。"""
        path = self._cli_path()
        if "npx" in path:
            return ["npx", "@anthropic-ai/claude-code"]
        return [path]

    def list_models(self) -> list[ModelInfo]:
        """优先用 system_config 中配置的模型；否则返回静态列表。"""
        default_id = ""
        try:
            from store.system_config import system_config
            default_id = system_config.get_default_model("claude") or ""
        except Exception:
            pass
        try:
            from store.system_config import system_config
            cfg_models = system_config.get_models("claude")
            if cfg_models:
                return [
                    ModelInfo(
                        id=m.get("id", ""),
                        name=m.get("name", m.get("id", "")),
                        provider=m.get("provider", "claude"),
                        default=bool(m.get("default")) or m.get("id", "") == default_id,
                    )
                    for m in cfg_models
                ]
        except Exception:
            pass
        # 回退静态列表
        return [
            ModelInfo("claude-sonnet-4-6", "Sonnet 4.6", "claude", True),
            ModelInfo("claude-opus-4-8", "Opus 4.8", "claude", False),
            ModelInfo("claude-haiku-4-5", "Haiku 4.5", "claude", False),
        ]

    def get_default_model(self) -> str:
        for m in self.list_models():
            if m.default:
                return m.id
        return "claude-sonnet-4-6"

    def run(self, request: RunRequest) -> Generator[AgentEvent, None, None]:
        cli_args = self._cli_args()
        cmd = cli_args + [
            "-p",
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
        if request.model:
            cmd.extend(["--model", request.model])
        if request.session_id:
            cmd.extend(["--session-id", request.session_id])

        env = os.environ.copy()
        if request.agent_id:
            env["OPENCLAW_WORKER_AGENT_ID"] = request.agent_id

        timeout = int(os.environ.get("CLAUDE_TIMEOUT", "600"))
        start = time.time()

        proc: Optional[subprocess.Popen] = None
        cancelled = False
        stop_watch = threading.Event()
        watcher: Optional[threading.Thread] = None

        try:
            proc = subprocess.Popen(
                cmd, cwd=request.workspace, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1,
                start_new_session=True,
            )

            # 看门狗：cancel_event 触发时杀整个进程组（解除 stdout 阻塞 + 连子进程一起回收）
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

            # 写入 prompt 到 stdin
            try:
                proc.stdin.write(request.message)
            except Exception:
                pass
            proc.stdin.close()

            # 逐行读取 stream-json
            for line in proc.stdout:
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                if time.time() - start > timeout:
                    self._terminate_group(proc)
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
            yield AgentEvent(EventKind.ERROR, {"message": f"Claude Code CLI 未找到: {cli_args[0]}"})
        except Exception as e:
            yield AgentEvent(EventKind.ERROR, {"message": str(e)})
        finally:
            stop_watch.set()
            self._terminate_group(proc)
            if watcher is not None:
                watcher.join(timeout=1)

    @staticmethod
    def _terminate_group(proc: Optional[subprocess.Popen]) -> None:
        """安全终止进程组。"""
        if proc is None or proc.poll() is not None:
            return
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, 15)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.terminate()
            except Exception:
                pass
