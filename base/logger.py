"""
日志模块 - 支持 DEBUG 和 DEBUGALL 两种模式
专为 OpenCode 适配器设计
"""
import json
import os
import sys
import re
from datetime import datetime
from typing import Optional

from config import Config


class DebugLogger:
    """调试日志记录器 - 支持 DEBUG 和 DEBUGALL 并行
    
    DEBUG = 精简模式(关键信息) -> 写入 openclaw-opencode-debug.log
    DEBUG_ALL = 详细模式(全部内容) -> 写入 openclaw-opencode-debug-all.log
    """
    
    def __init__(self):
        # DEBUG = 精简模式(关键信息)
        self.debug_mode = Config.DEBUG_MODE
        
        # DEBUG_ALL = 详细模式(全部内容)
        self.debugall_mode = Config.DEBUGALL_MODE
        
        # 日志文件路径
        self.debug_log = str(Config.DEBUG_LOG)         # 精简日志
        self.debugall_log = str(Config.DEBUG_ALL_LOG)   # 详细日志
        
        # 确保日志目录存在
        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # 当前 Agent 中文名
        self.agent_chinese_name = None
    
    def set_agent_name(self, chinese_name: str):
        """设置当前 Agent 的中文名"""
        self.agent_chinese_name = chinese_name
    
    def _get_agent_prefix(self) -> str:
        """获取 Agent 前缀"""
        if self.agent_chinese_name:
            return f"【{self.agent_chinese_name}】"
        return "【Agent】"
    
    def _write_log(self, log_file: str, level: str, message: str):
        """写入日志文件"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] [{level}] {message}\n"
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            print(f"[ERROR] 无法写入日志: {e}", file=sys.stderr)
    
    def _write_both(self, level: str, message: str):
        """同时写入 DEBUG 和 DEBUGALL"""
        if self.debug_mode:
            self._write_log(self.debug_log, level, message)
        if self.debugall_mode:
            self._write_log(self.debugall_log, level, message)
    
    def debug(self, message: str):
        """DEBUG 模式日志 - 精简信息(关键节点)"""
        if self.debug_mode:
            self._write_log(self.debug_log, "DEBUG", message)
    
    def info(self, message: str):
        """INFO 级别日志（同时写入 DEBUG 和 DEBUGALL）"""
        self._write_both("INFO", message)
    
    def section(self, title: str):
        """记录分隔区块（仅详细模式）"""
        if self.debugall_mode:
            self._write_log(self.debugall_log, "DEBUGALL", "")
            self._write_log(self.debugall_log, "DEBUGALL", "=" * 80)
            self._write_log(self.debugall_log, "DEBUGALL", f"【{title}】")
            self._write_log(self.debugall_log, "DEBUGALL", "=" * 80)
    
    def subsection(self, title: str, both: bool = False):
        """记录子区块
        both=True 时同时写入 DEBUG 和 DEBUGALL
        """
        if both and self.debug_mode:
            self._write_log(self.debug_log, "DEBUG", "")
            self._write_log(self.debug_log, "DEBUG", "-" * 80)
            self._write_log(self.debug_log, "DEBUG", f"  ▶ {title}")
            self._write_log(self.debug_log, "DEBUG", "-" * 80)
        if self.debugall_mode:
            self._write_log(self.debugall_log, "DEBUGALL", "")
            self._write_log(self.debugall_log, "DEBUGALL", "-" * 80)
            self._write_log(self.debugall_log, "DEBUGALL", f"  ▶ {title}")
            self._write_log(self.debugall_log, "DEBUGALL", "-" * 80)
    
    def kv(self, key: str, value: str, both: bool = False):
        """记录键值对
        both=True 时同时写入 DEBUG 和 DEBUGALL
        """
        line = f"    {key}: {value}"
        if both and self.debug_mode:
            self._write_log(self.debug_log, "DEBUG", line)
        if self.debugall_mode:
            self._write_log(self.debugall_log, "DEBUGALL", line)
    
    def log(self, message: str = ""):
        """通用日志方法（详细模式）"""
        if self.debugall_mode:
            self._write_log(self.debugall_log, "DEBUGALL", message)
    
    def log_both(self, message: str = ""):
        """同时写入 DEBUG 和 DEBUGALL"""
        self._write_both("DEBUG", message)
    
    def log_separator(self, char: str = "=", both: bool = False):
        """输出分隔符"""
        line = char * 80
        if both and self.debug_mode:
            self._write_log(self.debug_log, "DEBUG", line)
        if self.debugall_mode:
            self._write_log(self.debugall_log, "DEBUGALL", line)
    
    def extract_interactions(self, content: str) -> dict:
        """从 OpenCode JSON 输出中提取关键交互内容
        返回: dict with 'texts', 'tools', 'steps' keys
        """
        if not content:
            return {"texts": [], "tools": [], "steps": []}
        
        texts = []
        tools = []
        steps = []
        
        try:
            for line in content.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    msg_type = data.get('type', '')
                    
                    if msg_type == 'text':
                        text = data.get('part', {}).get('text', '')
                        if text:
                            texts.append(text)
                    
                    elif msg_type == 'tool_use':
                        # OpenCode API 字段: tool, part.state.input
                        tool_name = data.get('part', {}).get('tool', '')
                        tool_input = data.get('part', {}).get('state', {}).get('input', {})
                        tools.append({"name": tool_name, "input": tool_input})
                    
                    elif msg_type == 'tool_result':
                        tool_name = data.get('part', {}).get('name', '')
                        result = data.get('part', {}).get('content', '')
                        tools.append({"name": tool_name, "result": result[:200]})
                    
                    elif msg_type == 'step_start':
                        steps.append("step_start")
                    
                    elif msg_type == 'step_finish':
                        reason = data.get('part', {}).get('reason', '')
                        steps.append(f"step_finish: {reason}")
                    
                    elif msg_type == 'error':
                        error_name = data.get('error', {}).get('name', '')
                        steps.append(f"error: {error_name}")
                        
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            steps.append(f"[解析错误] {e}")
        
        return {"texts": texts, "tools": tools, "steps": steps}
    
    def content(self, label: str, content: str, max_len: Optional[int] = None):
        """记录内容块（详细模式，默认不截断）"""
        if not self.debugall_mode:
            return
        
        self._write_log(self.debugall_log, "DEBUGALL", f"")
        self._write_log(self.debugall_log, "DEBUGALL", f"  [{label}]")
        
        # 如果指定了 max_len 且内容超长，则截断
        if max_len and len(content) > max_len:
            truncated = content[:max_len]
            self._write_log(self.debugall_log, "DEBUGALL", f"    内容长度: {len(content)} 字符")
            self._write_log(self.debugall_log, "DEBUGALL", f"    {truncated}...")
            self._write_log(self.debugall_log, "DEBUGALL", f"    [已截断，共 {len(content)} 字符]")
        else:
            # 完整记录，不截断
            self._write_log(self.debugall_log, "DEBUGALL", f"    内容长度: {len(content)} 字符")
            for line in content.split('\n'):
                self._write_log(self.debugall_log, "DEBUGALL", f"    {line}")
    
    def content_both(self, label: str, content: str, max_len: int = 3000):
        """记录内容块（精简模式记录摘要，详细模式记录完整内容）"""
        
        # 提取交互内容
        interactions = self.extract_interactions(content)
        
        # DEBUG 模式（精简）：分开显示 文本回复 + 工具调用
        if self.debug_mode:
            self._write_log(self.debug_log, "DEBUG", f"")
            
            # ---- 文本回复 ----
            self._write_log(self.debug_log, "DEBUG", f"  ┌─ 【文本回复】")
            if interactions["texts"]:
                for i, text in enumerate(interactions["texts"]):
                    for line in text.split('\n'):
                        self._write_log(self.debug_log, "DEBUG", f"  │ {line}")
            else:
                self._write_log(self.debug_log, "DEBUG", f"  │ （无文本回复）")
            self._write_log(self.debug_log, "DEBUG", f"  └─")
            
            # ---- 工具调用 ----
            self._write_log(self.debug_log, "DEBUG", f"")
            self._write_log(self.debug_log, "DEBUG", f"  ┌─ 【工具调用】")
            if interactions["tools"]:
                for tool in interactions["tools"]:
                    tool_name = tool.get("name", "unknown")
                    if "input" in tool:
                        tool_input = str(tool.get("input", {}))[:200]
                        self._write_log(self.debug_log, "DEBUG", f"  │ → {tool_name}({tool_input}...)")
                    elif "result" in tool:
                        self._write_log(self.debug_log, "DEBUG", f"  │ ← {tool_name}")
            else:
                self._write_log(self.debug_log, "DEBUG", f"  │ （无工具调用）")
            self._write_log(self.debug_log, "DEBUG", f"  └─")
            
            # ---- 步骤状态 ----
            if interactions["steps"]:
                self._write_log(self.debug_log, "DEBUG", f"")
                self._write_log(self.debug_log, "DEBUG", f"  [步骤] {' | '.join(interactions['steps'])}")
        
        # DEBUGALL 模式（详细）：完整记录（不截断）
        if self.debugall_mode:
            self._write_log(self.debugall_log, "DEBUGALL", f"")
            self._write_log(self.debugall_log, "DEBUGALL", f"  [{label} - 完整内容]")
            self._write_log(self.debugall_log, "DEBUGALL", f"    内容长度: {len(content)} 字符")
            
            # 完整记录，不截断
            for line in content.split('\n'):
                self._write_log(self.debugall_log, "DEBUGALL", f"    {line}")
    
    def error(self, message: str, exc_info: Optional[Exception] = None):
        """错误日志（同时写入 DEBUG 和 DEBUGALL）"""
        error_msg = f"ERROR: {message}"
        if self.debug_mode:
            self._write_log(self.debug_log, "ERROR", error_msg)
        if self.debugall_mode:
            self._write_log(self.debugall_log, "ERROR", error_msg)
            if exc_info:
                import traceback
                tb_str = traceback.format_exc()
                self._write_log(self.debugall_log, "ERROR", f"异常详情:\n{tb_str}")
    
    def log_user_message(self, message: str):
        """记录用户消息（同时输出到 DEBUG 和 DEBUGALL）"""
        # DEBUG 模式：简化输出
        if self.debug_mode:
            self._write_log(self.debug_log, "DEBUG", "")
            self._write_log(self.debug_log, "DEBUG", "-" * 80)
            self._write_log(self.debug_log, "DEBUG", "  ▶ 用户消息")
            self._write_log(self.debug_log, "DEBUG", "-" * 80)
            self._write_log(self.debug_log, "DEBUG", f"    {message}")
        
        # DEBUGALL 模式：完整输出
        if self.debugall_mode:
            self._write_log(self.debugall_log, "DEBUGALL", "")
            self._write_log(self.debugall_log, "DEBUGALL", "-" * 80)
            self._write_log(self.debugall_log, "DEBUGALL", "  ▶ 用户消息")
            self._write_log(self.debugall_log, "DEBUGALL", "-" * 80)
            self._write_log(self.debugall_log, "DEBUGALL", f"    字符数: {len(message)}")
            self._write_log(self.debugall_log, "DEBUGALL", f"    内容: {message}")
    
    def log_opencode_call(self, model: str, session_id: Optional[str], workspace: str):
        """记录 OpenCode 调用（详细模式）"""
        if self.debugall_mode:
            agent_prefix = self._get_agent_prefix()
            self.section("调用 OpenCode CLI")
            self.kv("模型", model)
            if session_id:
                self.kv("Session", session_id)
            self.kv("工作目录", workspace)
    
    def log_opencode_response(self, exit_code: int, output: str, duration_ms: int,
                           new_session_id: str = None):
        """记录 OpenCode 响应（同时输出到 DEBUG 和 DEBUGALL）"""
        agent_prefix = self._get_agent_prefix()
        
        # 流向标题：同时写入 DEBUG 和 DEBUGALL
        self.log_both("")
        self.log_separator("=", both=True)
        self.log_both(f"【OpenCode】 --> {agent_prefix} 响应返回 (耗时: {duration_ms}ms)")
        self.log_separator("=", both=True)
        
        # 基本信息：同时写入
        self.kv("退出码", str(exit_code), both=True)
        self.kv("耗时", f"{duration_ms}ms", both=True)
        
        if new_session_id:
            self.kv("新 Session ID", new_session_id, both=True)
        
        # 响应内容：使用 content_both 方法
        self.content_both("响应内容", output)

    def warning(self, message: str):
        """WARNING 级别日志（同时写入 DEBUG 和 DEBUGALL）"""
        self._write_both("WARNING", message)


# 创建全局 logger 实例
logger = DebugLogger()
