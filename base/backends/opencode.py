"""
OpenCode CLI 后端实现
复用现有 opencode_adapter 的调用逻辑
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator, Optional

from backends.base import (
    CLIBackend, BackendModel, BackendCapability, BackendConfig,
    StreamEvent, registry,
)

# OpenCode CLI 默认路径
HOME_DIR = Path.home()
OPENCODE_CLI_DEFAULT = HOME_DIR / ".opencode" / "bin" / "opencode"

# 加载系统配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from system_config import system_config


class OpenCodeBackend(CLIBackend):
    """OpenCode CLI 后端"""

    @property
    def id(self) -> str:
        return "opencode"

    @property
    def display_name(self) -> str:
        return "OpenCode CLI"

    @property
    def capabilities(self) -> BackendCapability:
        return BackendCapability(
            streaming=True,
            tool_use=True,
            multi_turn=True,
            json_output=True,
            custom_rules=True,
        )

    def get_cli_path(self) -> str:
        """获取 OpenCode CLI 路径"""
        return os.environ.get("OPENCODE_CLI_PATH", str(OPENCODE_CLI_DEFAULT))

    def list_models(self) -> list[BackendModel]:
        """列出已知可用的模型（从系统配置读取）"""
        models = []
        cfg_models = system_config.get_models("opencode")
        if cfg_models:
            for m in cfg_models:
                models.append(BackendModel(
                    id=m.get("id", ""),
                    name=m.get("name", m.get("id", "")),
                    provider=m.get("provider", ""),
                    default=m.get("default", False),
                ))

        if not models:
            fallback = [
                ("opencode/mimo-v2.5-free", "mimo-v2.5-free", True),
                ("opencode/deepseek-v4-flash-free", "deepseek-v4-flash-free", False),
                ("SenseNova/sensenova-6.7-flash-lite", "SenseNova-sensenova-6.7-flash-lite", False),
            ]
            for mid, mname, default in fallback:
                models.append(BackendModel(id=mid, name=mname, default=default))

        return models

    def get_default_model(self) -> str:
        for m in self.list_models():
            if m.default:
                return m.id
        return "opencode/mimo-v2.5-free"

    def chat(
        self,
        workspace: str,
        message: str,
        model: str,
        session_id: Optional[str] = None,
        rules_file: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Generator[StreamEvent, None, None]:
        """调用 OpenCode CLI 并流式返回事件"""
        cli_path = self.get_cli_path()
        if not os.path.isfile(cli_path):
            yield StreamEvent("error", message=f"OpenCode CLI 未找到: {cli_path}")
            return

        cmd_args = [
            cli_path, "run",
            "--dangerously-skip-permissions",
            "--format", "json",
        ]
        if model:
            cmd_args.extend(["-m", model])
        if session_id:
            cmd_args.extend(["-s", session_id])
        cmd_args.extend(["--dir", workspace])
        if rules_file:
            cmd_args.extend(["-f", rules_file])

        child_env = os.environ.copy()
        if agent_id:
            child_env["OPENCLAW_WORKER_AGENT_ID"] = agent_id

        timeout = 600
        start_time = time.time()
        new_session_id = None

        try:
            proc = subprocess.Popen(
                cmd_args, cwd=workspace, env=child_env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, start_new_session=True,
            )
            try:
                proc.stdin.write(message)
            except Exception:
                pass
            proc.stdin.close()

            for line in proc.stdout:
                if time.time() - start_time > timeout:
                    proc.kill()
                    yield StreamEvent("error", message="执行超时")
                    return

                line = line.strip()
                if not line:
                    continue

                try:
                    event_data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = event_data.get("type", "")

                # 提取 session ID
                sid = event_data.get("sessionID")
                if sid:
                    new_session_id = sid

                if event_type == "text":
                    text = event_data.get("part", {}).get("text", "")
                    if text:
                        yield StreamEvent("thinking", type="text", content=text)

                elif event_type == "tool_use":
                    name = event_data.get("part", {}).get("name", "")
                    tool_input = event_data.get("part", {}).get("input", {})
                    yield StreamEvent("thinking", type="tool_use", name=name,
                                      input=json.dumps(tool_input, ensure_ascii=False))

                elif event_type == "tool_result":
                    content = event_data.get("part", {}).get("content", "")
                    if isinstance(content, list):
                        content = json.dumps(content, ensure_ascii=False)
                    if content:
                        yield StreamEvent("thinking", type="tool_result",
                                          content=str(content)[:2000])

                elif event_type == "step_finish":
                    tokens = event_data.get("part", {}).get("tokens", {})
                    if tokens:
                        yield StreamEvent("thinking", type="step_finish", tokens={
                            "input": tokens.get("input", 0),
                            "output": tokens.get("output", 0),
                            "total": tokens.get("total", 0),
                        })

            proc.wait()

            if new_session_id:
                yield StreamEvent("session", session_id=new_session_id)

        except FileNotFoundError:
            yield StreamEvent("error", message=f"OpenCode CLI 未找到: {cli_path}")
        except Exception as e:
            yield StreamEvent("error", message=str(e))

    def extract_session_id(self, output: str, events: list[StreamEvent]) -> Optional[str]:
        """从 OpenCode 输出中提取 session ID"""
        for line in output.strip().split("\n"):
            try:
                data = json.loads(line)
                sid = data.get("sessionID")
                if sid:
                    return sid
            except Exception:
                continue
        return None


# 自动注册
registry.register(OpenCodeBackend())