"""Agent 身份识别 — 读取 team/workspaces 中的身份文件。"""
from common.coordinator import get_coordinator_id

import re
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from hub.paths import IDENTITY_FILES, WORKSPACE_PREFIX, WORKSPACES_DIR


class AgentIdentityBuilder:
    """Agent 身份构建器 - 支持多 Agent"""

    def __init__(self, agent_id: str, workspace: str):
        self.agent_id = agent_id
        self.workspace = Path(workspace)
        self.identity_content = []
        self.chinese_name = None
        self.agent_role = None
        self._load_identity_files()

    def _load_identity_files(self):
        for filename in IDENTITY_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    self.identity_content.append(f"# {filename}\n{content}\n")
                    if filename == "IDENTITY.md":
                        self._extract_identity_info(content)
                except Exception as e:
                    print(f"[WARN] 读取 {filename} 失败: {e}")

    def _extract_identity_info(self, content: str):
        name_patterns = [
            r"(?:你的名字|中文名|称呼)[：:]\s*(\S+)",
            r"名字[：:]\s*(\S+)",
            r"##\s*名字\s*\n\s*(\S+)",
            r"(?:你是|我是)\s*(\S+)",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, content)
            if match:
                self.chinese_name = match.group(1).strip()
                break

        role_patterns = [
            r"(?:你的角色|角色|职责)[：:]\s*(.+?)(?:\n|$)",
            r"role[：:]\s*(.+?)(?:\n|$)",
            r"##\s*角色\s*\n\s*(.+?)(?:\n|$)",
        ]
        for pattern in role_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                self.agent_role = match.group(1).strip()
                break

    def extract_chinese_name(self) -> str:
        if self.chinese_name:
            return self.chinese_name
        agent_names = {
            get_coordinator_id(): "项目协调专家",
            "product": "产品经理",
            "developer": "开发工程师",
            "designer": "UI设计师",
            "research": "研究员",
            "researcher": "研究员",
            "content": "内容创作者",
            "ops": "运维工程师",
            "docs": "技术文档工程师",
            "consultation": "咨询顾问",
            "coordinator": "合规审查员",
            "social": "社交媒体运营",
            "seo": "SEO优化师",
            "email": "邮件营销专家",
        }
        return agent_names.get(self.agent_id, f"Agent-{self.agent_id}")

    def get_identity_context(self, *, rules_profile: str = "workflow_execute") -> str:
        """IDENTITY / SOUL / USER；能力与 task_type 见 agents_registry 注入块。"""
        if not self.identity_content:
            return ""
        return "\n".join([
            "=" * 40,
            "Agent 身份信息",
            "=" * 40,
            "\n".join(self.identity_content),
            "=" * 40,
        ])

    def get_agent_prompt_prefix(self) -> str:
        name = self.extract_chinese_name()
        role = self.agent_role or "AI 助手"
        return f"【{name}】{role}\n"


class MultiAgentManager:
    """多 Agent 管理器 - 管理所有 Agent 的上下文"""

    def __init__(self):
        self.agents: dict[str, AgentIdentityBuilder] = {}
        self._load_all_agents()

    def _load_all_agents(self):
        if not WORKSPACES_DIR.is_dir():
            return
        for workspace_dir in WORKSPACES_DIR.glob(f"{WORKSPACE_PREFIX}*"):
            match = re.search(rf"{WORKSPACE_PREFIX}(.+)$", workspace_dir.name)
            if match:
                agent_id = match.group(1)
                self.agents[agent_id] = AgentIdentityBuilder(agent_id, str(workspace_dir))

    def get_agent(self, agent_id: str) -> Optional[AgentIdentityBuilder]:
        return self.agents.get(agent_id)

    def get_all_agents_info(self) -> dict:
        return {
            agent_id: {
                "name": agent.extract_chinese_name(),
                "role": agent.agent_role,
                "workspace": str(agent.workspace),
            }
            for agent_id, agent in self.agents.items()
        }

    def build_multi_agent_context(self, current_agent_id: str) -> str:
        if not self.agents.get(current_agent_id):
            return ""
        other_agents = []
        for agent_id, agent in self.agents.items():
            if agent_id != current_agent_id:
                name = agent.extract_chinese_name()
                role = agent.agent_role or "AI 助手"
                other_agents.append(f"- {name} ({agent_id}): {role}")
        if not other_agents:
            return ""
        return "\n".join([
            "协作团队",
            "=" * 40,
            "你可以与其他以下 Agent 协作：",
            "\n".join(other_agents),
            "=" * 40,
        ])


multi_agent_manager = MultiAgentManager()
