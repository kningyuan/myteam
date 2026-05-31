#!/usr/bin/env python3
"""
统一日志模块 - 为所有 Skills 提供项目级日志记录功能

所有 Skill 的日志都记录到：~/.openclaw/tasks/projects/{project_id}/skill-logs/skills.log

使用方式:
    from common.logger import get_skill_logger, log_skill_step_failure, fail_skill_step
    
    logger = get_skill_logger(project_id)
    logger.info("[ACTION_NAME] key=value", extra={'skill_name': 'DISPATCH'})
    
    # 在 sys.exit(非0) 前尽量落盘一步失败（见 log_skill_step_failure / fail_skill_step 文档字符串）
"""

import logging
import re
import sys
from pathlib import Path
from datetime import datetime
import threading

# 线程锁，确保并发安全
_lock = threading.Lock()

# 缓存已创建的 logger，避免重复创建
_logger_cache = {}


def normalize_project_id(project_id: str) -> str:
    """标准化 project_id（与 init.py 逻辑一致：空格→下划线）"""
    match = re.match(r'pro_(.+)_(\d{8})$', project_id)
    if match:
        safe_name = match.group(1)
        date_str = match.group(2)
        # 空格 → 下划线
        safe_name = safe_name.replace(' ', '_')
        # 移除其他特殊字符
        safe_name = re.sub(r'[^\w\u4e00-\u9fa5-]', '', safe_name)
        # 连续下划线 → 单个
        safe_name = re.sub(r'_+', '_', safe_name)
        return f"pro_{safe_name}_{date_str}"
    return project_id


def get_skill_logger(project_id: str) -> logging.Logger:
    """
    获取项目专用的 Skill 日志器
    
    所有 Skill 共享同一个日志文件：skills.log
    日志格式：[时间戳] [级别] [Skill 名称] 消息
    
    参数:
        project_id: 项目 ID
    
    返回:
        logging.Logger: 配置好的日志器
    
    使用示例:
        logger = get_skill_logger("pro_test")
        logger.info("[DISPATCH_START] project=pro_test, task=task_001", 
                   extra={'skill_name': 'DISPATCH'})
    """
    cache_key = f"skill.{project_id}"
    
    # 检查缓存
    if cache_key in _logger_cache:
        return _logger_cache[cache_key]
    
    with _lock:
        # 双重检查缓存（防止并发创建）
        if cache_key in _logger_cache:
            return _logger_cache[cache_key]
        
        # 标准化 project_id
        corrected_id = normalize_project_id(project_id)
        
        # 构建项目目录和日志文件路径
        project_dir = Path.home() / f".openclaw/tasks/projects/{corrected_id}"
        log_file = project_dir / "skill-logs" / "skills.log"
        
        # 【关键】验证项目是否已初始化（检查 task_data.json）
        task_data_file = project_dir / "task_data.json"
        if not task_data_file.exists():
            # 项目未初始化，返回临时 logger 记录到全局错误日志
            return _get_temp_logger(project_id, corrected_id)
        
        # 项目已初始化，正常创建 logger
        logger = logging.getLogger(f"skill.{corrected_id}")
        logger.setLevel(logging.INFO)
        
        # 避免重复添加 handler
        if not logger.handlers:
            # 文件处理器
            handler = logging.FileHandler(log_file, encoding='utf-8')
            handler.setLevel(logging.INFO)
            
            # 格式化器
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] [%(skill_name)s] %(message)s',
                datefmt='%Y-%m-%dT%H:%M:%S'
            )
            handler.setFormatter(formatter)
            
            # 添加过滤器，确保每个日志记录都有 skill_name
            class SkillNameFilter(logging.Filter):
                def filter(self, record):
                    if not hasattr(record, 'skill_name'):
                        record.skill_name = 'UNKNOWN'
                    return True
            
            handler.addFilter(SkillNameFilter())
            logger.addHandler(handler)
        
        # 缓存 logger
        _logger_cache[cache_key] = logger
        
        return logger


def log_skill_step_failure(
    project_id: str,
    skill_name: str,
    step: str,
    detail: str,
    extra_text: str = "",
) -> None:
    """在 `sys.exit(非0)` 前尽量写入项目 `skill-logs/skills.log`。

    项目未初始化（无 `task_data.json`）时，`get_skill_logger` 会落到
    `~/.openclaw/logs/uninitialized_projects.log`，仍优于完全无记录。
    """
    tail = (extra_text or "").strip().replace("\n", " ")
    if len(tail) > 800:
        tail = tail[:797] + "..."
    msg = f"[SKILL_STEP_FAIL] step={step} detail={detail}"
    if tail:
        msg = f"{msg} | ctx={tail}"
    try:
        get_skill_logger(project_id).error(msg, extra={"skill_name": skill_name})
    except Exception:
        pass


def fail_skill_step(
    project_id: str,
    skill_name: str,
    step: str,
    detail: str,
    extra_text: str = "",
    code: int = 1,
) -> None:
    """写入 `[SKILL_STEP_FAIL]` 后以 `code` 退出（协作脚本硬失败统一出口）。"""
    log_skill_step_failure(project_id, skill_name, step, detail, extra_text)
    sys.exit(code)


def _get_temp_logger(project_id: str, corrected_id: str) -> logging.Logger:
    """返回临时 logger，记录到全局错误日志（不创建目录）"""
    error_log = Path.home() / ".openclaw/logs/uninitialized_projects.log"
    error_log.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"temp.{project_id}")
    if not logger.handlers:
        handler = logging.FileHandler(error_log, encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '[%(asctime)s] [UNINITIALIZED] project=%(project_id)s %(message)s'
        ))

        class ProjectIdFilter(logging.Filter):
            def filter(self, record):
                if not hasattr(record, 'project_id'):
                    record.project_id = 'unknown'
                return True

        handler.addFilter(ProjectIdFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)

    logger.warning(f"项目未初始化：{project_id} (修正后：{corrected_id})",
                   extra={'project_id': project_id})
    return logger


def clear_logger_cache():
    """清除 logger 缓存（用于测试）"""
    global _logger_cache
    with _lock:
        for logger in _logger_cache.values():
            # 关闭所有 handler
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
        _logger_cache = {}
