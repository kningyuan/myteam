"""
Session 管理模块 - 优化版
管理 OpenCode Session 与 OpenClaw Session 的映射关系
支持多 Agent 各自的 Session 管理
优化：更好的 Session 持久化策略
"""
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from config import Config
from logger import logger

# 文件锁：防止多个 agent 并发读写 session_map.json
try:
    import fcntl
    HAS_FLOCK = True
except ImportError:
    HAS_FLOCK = False


class SessionManager:
    """Session 管理器 - 支持多 Agent - 优化版"""

    def __init__(self):
        self.map_file = Config.SESSION_MAP_FILE
        self.lock_file = Path(str(self.map_file) + ".lock")
        self.session_map: Dict[str, dict] = {}
        self._load_map()

    def _acquire_lock(self):
        """获取文件锁（阻塞直到获得锁）"""
        if not HAS_FLOCK:
            return None
        try:
            lf = open(self.lock_file, 'w')
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            return lf
        except Exception:
            return None

    def _release_lock(self, lf):
        """释放文件锁"""
        if lf is not None and HAS_FLOCK:
            try:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
                lf.close()
            except Exception:
                pass

    def _load_map(self):
        """从文件加载 Session 映射"""
        lf = self._acquire_lock()
        try:
            if self.map_file.exists():
                try:
                    with open(self.map_file, 'r', encoding='utf-8') as f:
                        self.session_map = json.load(f)
                    logger.debug(f"已加载 Session 映射: {len(self.session_map)} 条")

                    # 清理过期 Session（超过 7 天）
                    self._cleanup_expired_sessions()
                except Exception as e:
                    logger.error(f"加载 Session 映射失败: {e}")
                    self.session_map = {}
        finally:
            self._release_lock(lf)

    def _save_map(self):
        """保存 Session 映射到文件"""
        lf = self._acquire_lock()
        try:
            self.map_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.map_file, 'w', encoding='utf-8') as f:
                json.dump(self.session_map, f, indent=2, ensure_ascii=False)
            logger.debug(f"已保存 Session 映射: {len(self.session_map)} 条")
        except Exception as e:
            logger.error(f"保存 Session 映射失败: {e}")
        finally:
            self._release_lock(lf)
    
    def _cleanup_expired_sessions(self):
        """清理过期的 Session（超过 7 天）"""
        if not Config.SESSION_PERSISTENCE:
            return
            
        now = time.time()
        expired_keys = []
        
        for key, data in self.session_map.items():
            last_used = data.get('last_used', 0)
            if now - last_used > 7 * 24 * 3600:  # 7 天
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.session_map[key]
            logger.debug(f"清理过期 Session: {key}")
        
        if expired_keys:
            self._save_map()
    
    def _get_map_key(self, stable_key: str, agent_id: str) -> str:
        """生成映射键（按 Agent 隔离，使用稳定 key）
        
        优化：使用 stable_key（workspace + agent_id）而非每次不同的 openclaw_session
        这样同一个 Agent 的多次调用会复用同一个 Session
        """
        return f"{agent_id}:{stable_key}"
    
    def get_opencode_session(self, stable_key: str, agent_id: str) -> Optional[str]:
        """获取 OpenCode Session ID
        
        Args:
            stable_key: 稳定的 key（如 workspace-agent_id）
            agent_id: Agent ID（如 main, product, developer）
        
        Returns:
            OpenCode 的 session ID，如果没有则返回 None
        """
        if not Config.SESSION_PERSISTENCE:
            return None
            
        key = self._get_map_key(stable_key, agent_id)
        session_data = self.session_map.get(key)
        
        if session_data:
            opencode_session = session_data.get('session_id')
            # 更新最后使用时间
            session_data['last_used'] = time.time()
            logger.debug(f"找到 Session [{agent_id}]: {stable_key} -> {opencode_session}")
            return opencode_session
        else:
            logger.debug(f"无 Session 映射 [{agent_id}]: {stable_key}")
            return None
    
    def get_chat_id(self, stable_key: str, agent_id: str) -> Optional[str]:
        """获取保存的 Telegram chat_id
        
        Args:
            stable_key: 稳定的 key
            agent_id: Agent ID
        
        Returns:
            Telegram chat_id，如果没有则返回 None
        """
        key = self._get_map_key(stable_key, agent_id)
        session_data = self.session_map.get(key)
        
        if session_data:
            chat_id = session_data.get('chat_id')
            if chat_id:
                logger.debug(f"找到 chat_id [{agent_id}]: {chat_id}")
                return chat_id
        
        logger.debug(f"无 chat_id 映射 [{agent_id}]: {stable_key}")
        return None
    
    def set_opencode_session(self, stable_key: str, agent_id: str, 
                            opencode_session: str, chat_id: str = None):
        """设置 OpenCode Session ID 映射
        
        Args:
            stable_key: 稳定的 key
            agent_id: Agent ID
            opencode_session: OpenCode 的 session ID
            chat_id: Telegram chat ID（用于发送通知）
        """
        if not Config.SESSION_PERSISTENCE:
            return
            
        key = self._get_map_key(stable_key, agent_id)
        session_data = {
            'session_id': opencode_session,
            'created_at': time.time(),
            'last_used': time.time(),
            'agent_id': agent_id
        }
        
        # 保存 chat_id（如果提供）
        if chat_id:
            session_data['chat_id'] = chat_id
            logger.debug(f"保存 chat_id: {chat_id}")
        
        self.session_map[key] = session_data
        self._save_map()
        logger.debug(f"保存映射 [{agent_id}]: {stable_key} -> {opencode_session}")
    
    def remove_mapping(self, stable_key: str, agent_id: str):
        """删除 Session 映射"""
        key = self._get_map_key(stable_key, agent_id)
        if key in self.session_map:
            del self.session_map[key]
            self._save_map()
            logger.debug(f"删除映射 [{agent_id}]: {stable_key}")
    
    def get_all_sessions_for_agent(self, agent_id: str) -> Dict[str, str]:
        """获取指定 Agent 的所有 Session 映射"""
        result = {}
        for key, data in self.session_map.items():
            if data.get('agent_id') == agent_id:
                stable_key = key[len(f"{agent_id}:"):]
                result[stable_key] = data.get('session_id')
        return result
    
    def clear_agent_sessions(self, agent_id: str):
        """清除指定 Agent 的所有 Session 映射"""
        keys_to_remove = [
            key for key, data in self.session_map.items() 
            if data.get('agent_id') == agent_id
        ]
        for key in keys_to_remove:
            del self.session_map[key]
        self._save_map()
        logger.info(f"清除 Agent [{agent_id}] 的所有 Session 映射")
    
    def get_session_info(self, stable_key: str, agent_id: str) -> Optional[Dict]:
        """获取 Session 详细信息"""
        key = self._get_map_key(stable_key, agent_id)
        data = self.session_map.get(key)
        
        if data:
            return {
                'session_id': data.get('session_id'),
                'created_at': datetime.fromtimestamp(data.get('created_at', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                'last_used': datetime.fromtimestamp(data.get('last_used', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                'agent_id': data.get('agent_id')
            }
        return None
    
    def list_all_sessions(self) -> List[Dict]:
        """列出所有 Session"""
        result = []
        for key, data in self.session_map.items():
            result.append({
                'key': key,
                'session_id': data.get('session_id'),
                'created_at': datetime.fromtimestamp(data.get('created_at', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                'last_used': datetime.fromtimestamp(data.get('last_used', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                'agent_id': data.get('agent_id')
            })
        return result


# 创建全局 Session 管理器
session_manager = SessionManager()
