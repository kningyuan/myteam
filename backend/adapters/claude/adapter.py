"""Claude Code CLI 实例 — 适配器层唯一知道 Claude Code 格式与命令行的地方。"""

import os
import subprocess
from pathlib import Path
from typing import Generator

from adapter.events import AgentEvent, EventKind
from adapter.protocol import AdapterCapabilities, ModelInfo, RunRequest
from common.submit_result import DISPATCH_TOKEN_ENV
from adapter.subprocess_cli import SubprocessCLIAdapter

from adapters.claude.parser import parse_line


class ClaudeCodeAdapter(SubprocessCLIAdapter):
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
            "--no-session-persistence",
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
        token = (request.extra or {}).get("dispatch_token")
        if token:
            env[DISPATCH_TOKEN_ENV] = str(token)

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
            yield AgentEvent(EventKind.ERROR, {"message": f"Claude Code CLI 未找到: {cli_args[0]}"})
        except Exception as e:
            yield AgentEvent(EventKind.ERROR, {"message": str(e)})


from adapter.registry import registry  # noqa: E402

registry.register(ClaudeCodeAdapter())
