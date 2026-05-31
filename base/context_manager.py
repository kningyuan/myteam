"""
上下文管理模块 - 优化版
管理 Agent 工作区的上下文加载，支持 Agent 身份和多 Agent 协作
增强：更好的 token 估算、智能上下文压缩
"""
import re
import math
from pathlib import Path
from typing import List, Optional, Tuple, Dict

from config import Config
from logger import logger


class TokenEstimator:
    """更精确的 token 估算器"""
    
    # GPT 系列模型的平均 token 比率
    # 实际约 1 token ≈ 4 字符（英文）或 1.5-2 字符（中文）
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """更精确的 token 估算
        
        考虑中英文混合、代码等因素
        """
        if not text:
            return 0
        
        # 统计字符类型
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        digits = sum(1 for c in text if c.isdigit())
        spaces = sum(1 for c in text if c.isspace())
        other = len(text) - chinese_chars - english_chars - digits - spaces
        
        # 中文约 1.5 字符/token，英文约 4 字符/token，代码约 3.5 字符/token
        chinese_tokens = chinese_chars / 1.5
        english_tokens = english_chars / 4.0
        code_tokens = (digits + other) / 3.5
        space_tokens = spaces / 6.0
        
        return int(chinese_tokens + english_tokens + code_tokens + space_tokens)
    
    @staticmethod
    def estimate_tokens_simple(text: str) -> int:
        """简单估算 - 作为后备"""
        # 更保守的估算：3 字符/token
        return int(len(text) / 3)


class ContextCompressor:
    """智能上下文压缩器 - 增强版"""
    
    # 保留的关键标记
    KEY_MARKERS = ['# ', '## ', '### ', '- [ ]', '- [x]', '- ', '* ', '```', '|']
    
    # 压缩级别
    COMPRESSION_LEVELS = {
        'light': 0.7,    # 轻度压缩
        'medium': 0.5,   # 中度压缩
        'heavy': 0.3,    # 重度压缩
    }
    
    @staticmethod
    def compress_file(content: str, max_tokens: int, file_path: str) -> str:
        """智能压缩文件内容
        
        策略：
        1. 保留文件头和关键配置
        2. 压缩重复内容
        3. 保留关键代码片段
        4. 智能摘要提取
        """
        lines = content.split('\n')
        
        # 判断文件类型
        if file_path.endswith('.md'):
            return ContextCompressor._compress_markdown(lines, max_tokens)
        elif file_path.endswith(('.json', '.yaml', '.yml')):
            return ContextCompressor._compress_config(lines, max_tokens)
        else:
            return ContextCompressor._compress_generic(lines, max_tokens)
    
    @staticmethod
    def compress_with_summary(content: str, max_tokens: int, file_path: str) -> str:
        """带摘要的压缩 - 保留开头 + 压缩尾部 + 摘要"""
        lines = content.split('\n')
        
        if not lines:
            return ""
        
        # 保留策略：开头 30% + 摘要 + 尾部 20%
        keep_head = int(len(lines) * 0.3)
        keep_tail = int(len(lines) * 0.2)
        
        head_lines = lines[:keep_head]
        tail_lines = lines[-keep_tail:] if keep_tail > 0 else []
        
        # 生成摘要
        summary = ContextCompressor._generate_summary(lines[keep_head:-keep_tail] if keep_tail > 0 else lines[keep_head:])
        
        result = []
        result.extend(head_lines)
        if summary:
            result.append("")
            result.append("--- [压缩摘要] ---")
            result.extend(summary[:5])  # 最多5行摘要
        if tail_lines:
            result.append("--- [后续内容] ---")
            result.extend(tail_lines)
        
        return '\n'.join(result)
    
    @staticmethod
    def _compress_markdown(lines: List[str], max_tokens: int) -> str:
        """压缩 Markdown 文件 - 保留结构，压缩内容"""
        result = []
        token_budget = max_tokens
        
        in_code_block = False
        for i, line in enumerate(lines):
            line_tokens = TokenEstimator.estimate_tokens(line)
            
            if line_tokens > token_budget:
                # 截断剩余内容
                remaining = max(0, token_budget - 50)
                result.append(f"\n... [内容已压缩，当前文件剩余 {remaining} tokens]")
                break
            
            # 保留标题和列表
            if line.strip().startswith('#') or line.strip().startswith('- ') or line.strip().startswith('* '):
                result.append(line)
                token_budget -= line_tokens
            elif line.strip().startswith('```'):
                in_code_block = not in_code_block
                result.append(line)
                token_budget -= line_tokens
            elif in_code_block:
                result.append(line)
                token_budget -= line_tokens
            elif line_tokens < 100:
                result.append(line)
                token_budget -= line_tokens
        
        return '\n'.join(result)
    
    @staticmethod
    def _compress_config(lines: List[str], max_tokens: int) -> str:
        """压缩配置文件 - 保留键，压缩值"""
        result = []
        token_budget = max_tokens
        
        for line in lines:
            line_tokens = TokenEstimator.estimate_tokens(line)
            
            if line_tokens > token_budget:
                result.append(f"# ... [配置已压缩]")
                break
            
            # 保留键，简化值
            if ':' in line and not line.strip().startswith('#'):
                key, value = line.split(':', 1)
                if len(value) > 50:
                    value = value[:50] + '...'
                result.append(f"{key}: {value}")
            else:
                result.append(line)
            
            token_budget -= line_tokens
        
        return '\n'.join(result)
    
    @staticmethod
    def _compress_generic(lines: List[str], max_tokens: int) -> str:
        """通用压缩"""
        result = []
        token_budget = max_tokens
        
        for line in lines:
            line_tokens = TokenEstimator.estimate_tokens(line)
            
            if line_tokens > token_budget:
                result.append("# ... [内容已压缩]")
                break
            
            # 保留空行和短行
            if not line.strip() or len(line.strip()) < 80:
                result.append(line)
            
            token_budget -= line_tokens
        
        return '\n'.join(result)
    
    @staticmethod
    def _generate_summary(lines: List[str]) -> List[str]:
        """从内容中提取关键信息作为摘要"""
        keywords = []
        
        # 提取标题
        for line in lines:
            if line.strip().startswith('#'):
                level = line.count('#')
                title = line.strip('#').strip()
                keywords.append(f"[{'>'*level} {title}]")
        
        # 提取列表项
        list_items = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('- ') or stripped.startswith('* '):
                item = stripped[2:]
                if len(item) < 50 and item not in list_items:
                    list_items.append(item)
        
        return keywords + list_items[:10]
    
    @staticmethod
    def deduplicate_content(lines: List[str]) -> List[str]:
        """去除重复行"""
        seen = set()
        result = []
        
        for line in lines:
            # 标准化比较
            normalized = line.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(line)
            elif not normalized:
                result.append(line)  # 保留空行
        
        return result


class ContextManager:
    """上下文管理器 - 按 Agent 隔离 - 优化版"""
    
    CONTEXT_FILES = [
        "IDENTITY.md",
        "USER.md", 
        "SOUL.md",
        "AGENTS.md",
        "MEMORY.md",
        "HEARTBEAT.md",
        "TOOLS.md",
        "PERSONA.md",
    ]
    
    CORE_INSTRUCTION_FILES = ["IDENTITY.md", "AGENTS.md", "SOUL.md", "USER.md"]
    TOOLS_FILES = ["TOOLS.md"]
    FEWSHOT_FILES = ["FEWSHOT.md", "EXAMPLES.md"]
    
    IGNORE_PATTERNS = [
        r'\.git',
        r'node_modules',
        r'__pycache__',
        r'\.pyc$',
        r'\.log$',
        r'\.tmp$',
        r'\.cache',
        r'session-.*\.jsonl$',
    ]
    
    def __init__(self, agent_id: str, workspace: str, max_tokens: int = 80000):
        self.agent_id = agent_id
        self.workspace = Path(workspace)
        self.max_tokens = max_tokens
        self.ignore_regex = [re.compile(p) for p in self.IGNORE_PATTERNS]
        self.token_estimator = TokenEstimator()
        self.compressor = ContextCompressor()
    
    def should_ignore(self, file_path: Path) -> bool:
        """判断文件是否应该被忽略"""
        path_str = str(file_path)
        for pattern in self.ignore_regex:
            if pattern.search(path_str):
                return True
        return False
    
    def is_priority_file(self, file_path: Path) -> bool:
        """判断是否为优先级文件（不被压缩）"""
        return file_path.name in Config.PRIORITY_CONTEXT_FILES
    
    def read_file_content(self, file_path: Path, for_compression: bool = False) -> Optional[str]:
        """安全地读取文件内容"""
        try:
            if not file_path.exists():
                return None
            
            size = file_path.stat().st_size
            if size > 1024 * 1024:
                logger.debug(f"文件过大，跳过: {file_path} ({size / 1024:.1f}KB)")
                return f"# {file_path.name}\n[文件过大，已跳过]\n"
            
            try:
                content = file_path.read_text(encoding='utf-8')
                return f"# {file_path.name}\n{content}\n"
            except UnicodeDecodeError:
                return f"# {file_path.name}\n[二进制文件，已跳过]\n"
                
        except Exception as e:
            logger.debug(f"读取文件失败 {file_path}: {e}")
            return None
    
    def collect_context_files(self) -> List[Tuple[Path, int]]:
        """收集所有上下文文件（按优先级排序）"""
        files_with_priority = []
        
        for priority, filename in enumerate(self.CONTEXT_FILES):
            file_path = self.workspace / filename
            if file_path.exists() and not self.should_ignore(file_path):
                files_with_priority.append((file_path, priority))
        
        other_priority = len(self.CONTEXT_FILES)
        for file_path in self.workspace.rglob("*.md"):
            if self.should_ignore(file_path):
                continue
            if file_path.name in self.CONTEXT_FILES:
                continue
            files_with_priority.append((file_path, other_priority))
            other_priority += 1
        
        for ext in [".json", ".yaml", ".yml", ".toml"]:
            for file_path in self.workspace.rglob(f"*{ext}"):
                if self.should_ignore(file_path):
                    continue
                files_with_priority.append((file_path, other_priority))
                other_priority += 1
        
        return files_with_priority
    
    def build_context(self, include_identity: bool = True) -> str:
        """构建上下文内容 - 优化版
        
        改进：
        1. 更精确的 token 估算
        2. 优先级文件不被压缩
        3. 智能内容压缩
        """
        if not Config.ENABLE_CONTEXT:
            return ""
        
        context_parts = []
        total_tokens = 0
        
        header = f"""="{'='*38}
工作区上下文 (Agent: {self.agent_id})
优化版 - 智能上下文管理
={'='*38}
"""
        context_parts.append(header)
        total_tokens += self.token_estimator.estimate_tokens(header)
        
        files = self.collect_context_files()
        
        # 计算安全阈值 - 80% 时开始压缩
        compression_threshold = int(self.max_tokens * Config.COMPRESSION_THRESHOLD)
        
        for file_path, priority in files:
            if total_tokens >= self.max_tokens:
                logger.debug(f"达到 token 限制 ({self.max_tokens})，停止加载")
                break
            
            rel_path = file_path.relative_to(self.workspace)
            content = self.read_file_content(file_path)
            if not content:
                continue
            
            tokens = self.token_estimator.estimate_tokens(content)
            is_priority = self.is_priority_file(file_path)
            
            # 优先级文件：完整加载
            if is_priority:
                if total_tokens + tokens > self.max_tokens:
                    remaining = self.max_tokens - total_tokens
                    content = self.compressor.compress_file(content, remaining, str(rel_path))
                    tokens = self.token_estimator.estimate_tokens(content)
            else:
                # 非优先级文件：检查是否需要压缩
                if total_tokens > compression_threshold and tokens > 500:
                    remaining = self.max_tokens - total_tokens
                    if remaining < 1000:
                        logger.debug(f"跳过非关键文件: {rel_path} (token 不足)")
                        continue
                    content = self.compressor.compress_file(content, remaining, str(rel_path))
                    tokens = self.token_estimator.estimate_tokens(content)
                elif tokens > 10000:
                    content = self.compressor.compress_file(content, 8000, str(rel_path))
                    tokens = self.token_estimator.estimate_tokens(content)
            
            if total_tokens + tokens > self.max_tokens:
                remaining = self.max_tokens - total_tokens
                if remaining > 200:
                    content = content[:remaining * 3] + "\n...[因 token 限制截断]"
                    tokens = self.token_estimator.estimate_tokens(content)
                else:
                    continue
            
            section = f"\n--- {rel_path} ---\n{content}\n"
            
            context_parts.append(section)
            total_tokens += tokens
            logger.debug(f"加载上下文: {rel_path} (~{tokens} tokens)")
        
        footer = f"\n={'='*38}\n上下文结束 (总计约 {total_tokens} tokens)\n={('='*38)}\n"
        context_parts.append(footer)
        
        return "\n".join(context_parts)
    
    def get_workspace_summary(self) -> str:
        """获取工作区摘要"""
        try:
            files = list(self.workspace.rglob("*"))
            total_files = len([f for f in files if f.is_file()])
            total_dirs = len([f for f in files if f.is_dir()])
            md_files = len(list(self.workspace.rglob("*.md")))
            
            return f"""工作区: {self.workspace}
总文件数: {total_files}
总目录数: {total_dirs}
Markdown 文件: {md_files}
"""
        except Exception as e:
            return f"获取工作区摘要失败: {e}"
    
    def get_context_stats(self) -> Dict:
        """获取上下文统计信息"""
        files = self.collect_context_files()
        total_size = 0
        file_count = 0
        
        for file_path, _ in files:
            try:
                total_size += file_path.stat().st_size
                file_count += 1
            except:
                pass
        
        return {
            "file_count": file_count,
            "total_size": total_size,
            "estimated_tokens": self.token_estimator.estimate_tokens(
                self.build_context() if Config.ENABLE_CONTEXT else ""
            ),
            "max_tokens": self.max_tokens
        }
    
    def build_layered_context(self) -> Dict[str, str]:
        """构建分层上下文 - 优化版
        
        返回结构化字典：
        - core: 核心指令（IDENTITY, AGENTS, SOUL）
        - tools: 工具描述（TOOLS）
        - fewshot: 示例引导
        - dynamic: 动态上下文（MHEARTBEAT, EMORY等）
        """
        if not Config.ENABLE_CONTEXT:
            return {"core": "", "tools": "", "fewshot": "", "dynamic": ""}
        
        result = {
            "core": "",
            "tools": "",
            "fewshot": "",
            "dynamic": ""
        }
        
        core_parts = []
        tools_parts = []
        fewshot_parts = []
        dynamic_parts = []
        
        files = self.collect_context_files()
        
        for file_path, _ in files:
            rel_path = file_path.relative_to(self.workspace)
            content = self.read_file_content(file_path)
            if not content:
                continue
            
            file_name = file_path.name
            
            if file_name in self.CORE_INSTRUCTION_FILES:
                core_parts.append(content)
            elif file_name in self.TOOLS_FILES:
                tools_parts.append(content)
            elif file_name in self.FEWSHOT_FILES:
                fewshot_parts.append(content)
            else:
                dynamic_parts.append(content)
        
        result["core"] = "\n\n".join(core_parts)
        result["tools"] = "\n\n".join(tools_parts)
        result["fewshot"] = "\n\n".join(fewshot_parts)
        result["dynamic"] = "\n\n".join(dynamic_parts)
        
        return result

    def is_core_file(self, file_path: Path) -> bool:
        return file_path.name in self.CORE_INSTRUCTION_FILES
    
    def is_tools_file(self, file_path: Path) -> bool:
        return file_path.name in self.TOOLS_FILES
    
    def is_fewshot_file(self, file_path: Path) -> bool:
        return file_path.name in self.FEWSHOT_FILES
