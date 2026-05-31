"""
Agent 身份识别模块
自动识别不同 Agent 的工作区和身份信息
支持多 Agent 上下文管理
"""
import re
from pathlib import Path
from typing import Optional, List

from config import Config


class AgentIdentityBuilder:
    """Agent 身份构建器 - 支持多 Agent"""
    
    def __init__(self, agent_id: str, workspace: str):
        self.agent_id = agent_id
        self.workspace = Path(workspace)
        self.identity_content = []
        self.chinese_name = None
        self.agent_role = None
        
        # 加载身份文件
        self._load_identity_files()
    
    def _load_identity_files(self):
        """加载所有身份文件"""
        for filename in Config.IDENTITY_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding='utf-8')
                    self.identity_content.append(f"# {filename}\n{content}\n")
                    
                    # 从 IDENTITY.md 提取中文名
                    if filename == "IDENTITY.md":
                        self._extract_identity_info(content)
                        
                except Exception as e:
                    print(f"[WARN] 读取 {filename} 失败: {e}")
    
    def _extract_identity_info(self, content: str):
        """从 IDENTITY.md 提取身份信息"""
        # 提取中文名 - 支持多种格式
        name_patterns = [
            r'(?:你的名字|中文名|称呼)[：:]\s*(\S+)',  # 标准格式
            r'名字[：:]\s*(\S+)',  # 简化格式
            r'##\s*名字\s*\n\s*(\S+)',  # Markdown 格式
            r'(?:你是|我是)\s*(\S+)',  # 描述格式
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, content)
            if match:
                self.chinese_name = match.group(1).strip()
                break
        
        # 提取角色
        role_patterns = [
            r'(?:你的角色|角色|职责)[：:]\s*(.+?)(?:\n|$)',  # 标准格式
            r'role[：:]\s*(.+?)(?:\n|$)',  # 英文格式
            r'##\s*角色\s*\n\s*(.+?)(?:\n|$)',  # Markdown 格式
        ]
        
        for pattern in role_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                self.agent_role = match.group(1).strip()
                break
    
    def extract_chinese_name(self) -> str:
        """提取 Agent 中文名"""
        if self.chinese_name:
            return self.chinese_name
        
        # 默认名称
        agent_names = {
            'main': '项目协调专家',
            'product': '产品经理',
            'developer': '开发工程师',
            'designer': 'UI设计师',
            'researcher': '调研专家',
            'content': '内容创作者',
            'ops': '运维工程师',
            'docs': '技术文档工程师',
            'consultation': '咨询顾问',
            'coordinator': '合规审查员',
            'social': '社交媒体运营',
            'seo': 'SEO优化师',
            'email': '邮件营销专家',
        }
        
        return agent_names.get(self.agent_id, f'Agent-{self.agent_id}')
    
    def get_identity_context(self) -> str:
        """获取完整身份上下文"""
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
        """获取 Agent 提示词前缀"""
        name = self.extract_chinese_name()
        role = self.agent_role or "AI 助手"
        
        return f"【{name}】{role}\n"


class MultiAgentManager:
    """多 Agent 管理器 - 管理所有 Agent 的上下文"""
    
    def __init__(self):
        self.agents: dict[str, AgentIdentityBuilder] = {}
        self._load_all_agents()
    
    def _load_all_agents(self):
        """加载所有 Agent"""
        base_dir = Config.AGENTS_BASE_DIR
        
        # 查找所有 workspace-* 目录
        for workspace_dir in base_dir.glob("workspace-*"):
            match = re.search(r'workspace-(.+)$', workspace_dir.name)
            if match:
                agent_id = match.group(1)
                self.agents[agent_id] = AgentIdentityBuilder(
                    agent_id, 
                    str(workspace_dir)
                )
    
    def get_agent(self, agent_id: str) -> Optional[AgentIdentityBuilder]:
        """获取指定 Agent"""
        return self.agents.get(agent_id)
    
    def get_all_agents_info(self) -> dict:
        """获取所有 Agent 信息"""
        return {
            agent_id: {
                'name': agent.extract_chinese_name(),
                'role': agent.agent_role,
                'workspace': str(agent.workspace)
            }
            for agent_id, agent in self.agents.items()
        }
    
    def build_multi_agent_context(self, current_agent_id: str) -> str:
        """构建多 Agent 协作上下文（不含核心指令，仅团队信息）"""
        current = self.agents.get(current_agent_id)
        if not current:
            return ""
        
        context_parts = []
        
        # 只添加其他 Agent 信息（简要）- 核心指令已在 core_instructions
        other_agents = []
        for agent_id, agent in self.agents.items():
            if agent_id != current_agent_id:
                name = agent.extract_chinese_name()
                role = agent.agent_role or "AI 助手"
                other_agents.append(f"- {name} ({agent_id}): {role}")
        
        if other_agents:
            context_parts.extend([
                "协作团队",
                "=" * 40,
                "你可以与其他以下 Agent 协作：",
                "\n".join(other_agents),
                "=" * 40,
            ])
        
        return "\n".join(context_parts) if context_parts else ""


# 创建全局多 Agent 管理器
multi_agent_manager = MultiAgentManager()
