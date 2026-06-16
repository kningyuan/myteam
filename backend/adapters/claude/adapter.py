"""Claude Code CLI 实例 — 适配器层唯一知道 Claude Code 格式与命令行的地方。"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Generator

from adapter.events import AgentEvent, EventKind
from adapter.protocol import AdapterCapabilities, ModelInfo, RunRequest
from common.submit_result import DISPATCH_TOKEN_ENV
from adapter.subprocess_cli import SubprocessCLIAdapter

from adapters.claude.parser import parse_line
from adapters.claude.skill_sync import sync_workspace_skills
from adapters.claude.mcp_sync import sync_workspace_mcp, MCP_CONFIG_NAME

# 非交互 stream-json 下输出思考摘要（对齐 opencode --thinking）
_CLAUDE_USER_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


def _load_claude_user_settings() -> dict:
    """读取 ~/.claude/settings.json（ccswitch / 用户认证与代理常写在这里）。"""
    path = _CLAUDE_USER_SETTINGS_PATH
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _claude_user_env() -> dict[str, str]:
    raw = _load_claude_user_settings().get("env")
    if not isinstance(raw, dict):
        return {}
    return {k: str(v) for k, v in raw.items() if v is not None}


def _runtime_settings_json() -> str:
    """stream-json 运行参数：思考摘要 + 用户 env（--setting-sources project 时仍需代理/鉴权）。"""
    payload: dict = {"showThinkingSummaries": True}
    user_env = _claude_user_env()
    if user_env:
        payload["env"] = user_env
    return json.dumps(payload, separators=(",", ":"))


def _claude_subprocess_env(base: dict | None = None) -> dict[str, str]:
    """子进程环境：继承 Hub 环境，并补齐 ~/.claude/settings.json 的 env（不覆盖已有变量）。"""
    env = dict(base if base is not None else os.environ)
    for k, v in _claude_user_env().items():
        env.setdefault(k, v)
    return env

# Claude Code --model 接受的别名与完整 ID（见 `claude --help`）
_CLAUDE_MODEL_CATALOG: list[tuple[str, str]] = [
    ("sonnet", "Sonnet（别名 · 跟随 CLI 默认）"),
    ("opus", "Opus（别名 · 跟随 CLI 默认）"),
    ("haiku", "Haiku（别名 · 跟随 CLI 默认）"),
    ("fable", "Fable（别名 · 跟随 CLI 默认）"),
    ("claude-sonnet-4-6", "Sonnet 4.6"),
    ("claude-sonnet-4-6[1M]", "Sonnet 4.6 · 1M"),
    ("claude-opus-4-8", "Opus 4.8"),
    ("claude-opus-4-8[1M]", "Opus 4.8 · 1M"),
    ("claude-haiku-4-5", "Haiku 4.5"),
    ("claude-fable-5", "Fable 5"),
    ("claude-sonnet-4-5", "Sonnet 4.5"),
    ("claude-opus-4-6", "Opus 4.6"),
]


def _merge_claude_models(
    cfg_models: list[dict],
    *,
    default_id: str = "",
) -> list[ModelInfo]:
    """内置目录 + system_config 扩展/覆盖；config 不再独占列表。"""
    merged: dict[str, ModelInfo] = {}
    for mid, name in _CLAUDE_MODEL_CATALOG:
        merged[mid] = ModelInfo(mid, name, "claude", default=(mid == default_id))

    for cm in cfg_models:
        mid = (cm.get("id") or "").strip()
        if not mid:
            continue
        base = merged.get(mid)
        merged[mid] = ModelInfo(
            mid,
            cm.get("name") or (base.name if base else mid),
            cm.get("provider", "claude"),
            default=bool(cm.get("default")) or mid == default_id,
        )

    models = list(merged.values())
    if default_id:
        return models
    if any(m.default for m in models):
        return models
    for m in models:
        if m.id == "sonnet":
            m.default = True
            break
    else:
        if models:
            models[0].default = True
    return models


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
            native_skill_registry=True,
            native_mcp_registry=True,
        )

    def sync_agent_skills(
        self,
        agent_id: str,
        workspace: str,
        skill_ids: list[str],
    ) -> dict:
        """将 Skill 注册到 workspace/.claude/skills/（Claude Code 项目级 skill 目录）。"""
        _ = agent_id
        return sync_workspace_skills(workspace, skill_ids)

    def sync_agent_mcp(
        self,
        agent_id: str,
        workspace: str,
        server_ids: list[str],
    ) -> dict:
        _ = agent_id
        return sync_workspace_mcp(workspace, server_ids)

    def _configured_cli_path(self) -> str:
        """system_config / CLAUDE_CLI_PATH 显式配置。"""
        try:
            from store.system_config import system_config
            p = system_config.get_cli_path("claude")
            if p:
                return p
        except Exception:
            pass
        return os.environ.get("CLAUDE_CLI_PATH", "")

    def _cli_path(self) -> str:
        """探测 Claude Code CLI 可执行路径。

        优先级：
          1. system_config.backends.claude.cli_path
          2. CLAUDE_CLI_PATH 环境变量
          3. PATH 中的 claude
          4. 回退 npx（由 _cli_command 展开为 npx @anthropic-ai/claude-code）
        """
        configured = self._configured_cli_path()
        if configured:
            return configured

        found = shutil.which("claude")
        if found:
            return found

        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = Path(p) / "claude"
            if candidate.is_file():
                return str(candidate)

        return "npx"

    def _cli_available(self) -> tuple[bool, str]:
        """检查 CLI 是否可启动（npx 回退仅检查 npx 存在）。"""
        path = self._cli_path()
        if path == "npx":
            if shutil.which("npx"):
                return True, path
            return False, path
        if os.path.isfile(path) or shutil.which(path):
            return True, path
        return False, path

    def _cli_command(self) -> list[str]:
        """构建 CLI 可执行前缀（不含 run 参数）。"""
        path = self._cli_path()
        if path == "npx" or "npx" in path:
            return ["npx", "@anthropic-ai/claude-code"]
        return [path]

    def list_models(self, *, refresh: bool = False) -> list[ModelInfo]:
        """返回 Claude Code 可用模型：内置目录 + system_config 扩展/覆盖。"""
        _ = refresh
        default_id = ""
        cfg_models: list[dict] = []
        try:
            from store.system_config import system_config
            default_id = system_config.get_default_model("claude") or ""
            cfg_models = system_config.get_models("claude") or []
        except Exception:
            pass
        return _merge_claude_models(cfg_models, default_id=default_id)

    def get_default_model(self) -> str:
        for m in self.list_models():
            if m.default:
                return m.id
        return "sonnet"

    def _build_run_command(self, request: RunRequest) -> list[str]:
        cmd = self._cli_command() + [
            "-p",
            "--no-session-persistence",
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            # 与 opencode --thinking 等价：在 stream-json 中输出 thinking 内容块
            "--settings", _runtime_settings_json(),
        ]
        if request.model:
            cmd.extend(["--model", request.model])
        if request.session_id:
            cmd.extend(["--session-id", request.session_id])
        if request.rules_file and os.path.isfile(request.rules_file):
            cmd.extend(["--append-system-prompt-file", request.rules_file])

        ws = Path(request.workspace).resolve()
        mcp_config = ws / MCP_CONFIG_NAME
        if mcp_config.is_file():
            cmd.extend(["--strict-mcp-config", "--mcp-config", str(mcp_config)])

        if request.agent_id:
            from common.agent_skills import get_agent_skill_ids

            if get_agent_skill_ids(request.agent_id):
                # 仅加载项目级 .claude/skills；鉴权 env 由 _runtime_settings_json / _claude_subprocess_env 注入
                cmd.extend(["--setting-sources", "project"])

        return cmd

    def run(self, request: RunRequest) -> Generator[AgentEvent, None, None]:
        ok, cli_ref = self._cli_available()
        if not ok:
            yield AgentEvent(EventKind.ERROR, {
                "message": f"Claude Code CLI 未找到: {cli_ref}（请安装 claude 或配置 CLAUDE_CLI_PATH）",
            })
            return

        cmd = self._build_run_command(request)

        env = _claude_subprocess_env()
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
            yield AgentEvent(EventKind.ERROR, {
                "message": f"Claude Code CLI 未找到: {self._cli_command()[0]}",
            })
        except Exception as e:
            yield AgentEvent(EventKind.ERROR, {"message": str(e)})


from adapter.registry import registry  # noqa: E402

registry.register(ClaudeCodeAdapter())
