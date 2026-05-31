#!/usr/bin/env python3
"""Project Init Skill - 初始化项目

用法:
  init.py '<project_name>' ['<description>']   # 创建项目
  init.py validate-graph <project_id>           # 校验已有项目依赖图（graph_gate / check-cycle）
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".openclaw" / "skills" / "team-ok"))
from common.agent_auth import assert_agent_allowed
from common.graph_gate import assert_valid_task_graph
from common.logger import get_skill_logger, log_skill_step_failure
import json
import subprocess
import re
from datetime import datetime

def create_project(name, description=""):
    """创建标准化项目目录

    规则：空格 → 下划线，特殊字符 → 移除
    """

    # 角色边界检查：仅 Main Agent 可创建项目
    assert_agent_allowed("project-init")

    date_str = datetime.now().strftime("%Y%m%d")
    
    # 【核心规则】空格 → 下划线
    safe_name = name.replace(' ', '_')
    
    # 移除其他特殊字符（保留字母、数字、下划线、中文字符）
    safe_name = re.sub(r'[^\w\u4e00-\u9fa5-]', '', safe_name)
    
    # 将连续的下划线合并为单个
    safe_name = re.sub(r'_+', '_', safe_name)
    
    # 【第二层防御】如果 safe_name 为空，使用哈希
    if not safe_name or safe_name.strip() == '':
        import hashlib
        safe_name = hashlib.md5(name.encode('utf-8')).hexdigest()[:8]
        logger = logging.getLogger('INIT')
        logger.warning(f"项目名称为空，使用哈希：{safe_name}")
    
    # 【第三层防御】确保不以数字开头
    if safe_name and safe_name[0].isdigit():
        safe_name = 'proj_' + safe_name
    
    project_id = f"pro_{safe_name}_{date_str}"
    
    # 【第四层防御】验证生成的路径
    base_dir = Path.home() / f".openclaw/tasks/projects/{project_id}"
    
    # 检查路径是否包含空格或特殊字符
    path_str = str(base_dir)
    if ' ' in path_str or any(c in path_str for c in '<>|\"'):
        print(f"Error: 生成的项目路径包含非法字符：{path_str}", file=sys.stderr)
        print(f"建议：检查项目名称是否合法", file=sys.stderr)
        log_skill_step_failure(
            project_id,
            "INIT",
            "invalid_generated_path",
            path_str,
            name,
        )
        sys.exit(1)
    
    # 创建目录结构（预创建所有必要目录和文件）
    deliverables_dir = base_dir / "deliverables"
    skill_logs_dir = base_dir / "skill-logs"
    
    base_dir.mkdir(parents=True, exist_ok=True)
    deliverables_dir.mkdir(exist_ok=True)
    skill_logs_dir.mkdir(exist_ok=True)
    
    # 创建初始数据结构
    project_data = {
        "version": "2.0",
        "project": {
            "id": project_id,
            "name": name,
            "description": description,
            "status": "pending_confirmation",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "confirmed_by_user": False,
            "confirmed_at": None,
            "completed_at": None
        },
        "tasks": [],
        "agents": []
    }
    
    # 写入 task_data.json
    with open(base_dir / "task_data.json", 'w', encoding='utf-8') as f:
        json.dump(project_data, f, ensure_ascii=False, indent=2)
    
    # 预创建 skill-logs/skills.log 文件（空文件）
    skills_log_file = skill_logs_dir / "skills.log"
    skills_log_file.touch(exist_ok=True)
    
    # 【方案 A】注释掉 .task_queue 文件的预创建
    # 原因：task-queue 是运行时状态文件，应该由 task-queue skill 在第一次使用时创建
    # 预创建会导致 task-queue 把 '[]' 误认为任务 ID，导致 dispatch 失败
    # 原代码：
    # task_queue_file = base_dir / ".task_queue"
    # with open(task_queue_file, 'w', encoding='utf-8') as f:
    #     json.dump([], f)
    
    print(f"✅ Project created: {project_id}")
    print(f"   Location: {base_dir}")
    
    # 记录日志
    logger = get_skill_logger(project_id)
    logger.info(f"[PROJECT_INIT] name={name}, id={project_id}, path={base_dir}", extra={'skill_name': 'INIT'})
    logger.info(f"[PROJECT_INIT_DETAIL] safe_name={safe_name}, description_len={len(description)}, tasks=0, agents=0", extra={'skill_name': 'INIT'})

    return project_id

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "validate-graph":
        if len(sys.argv) < 3:
            print("Usage: init.py validate-graph <project_id>", file=sys.stderr)
            log_skill_step_failure(
                "INIT_CLI",
                "INIT",
                "validate_graph_usage",
                "missing project_id",
                "",
            )
            sys.exit(1)
        assert_valid_task_graph(sys.argv[2])
        print("✅ 任务依赖图为合法 DAG（与 project-data check-cycle 同源）")
        return

    if len(sys.argv) < 2:
        print("Usage: init.py '<project_name>' ['<description>']", file=sys.stderr)
        print("       init.py validate-graph <project_id>", file=sys.stderr)
        log_skill_step_failure(
            "INIT_CLI",
            "INIT",
            "create_usage",
            "missing project name",
            "",
        )
        sys.exit(1)
    
    name = sys.argv[1]
    description = sys.argv[2] if len(sys.argv) > 2 else ""
    
    project_id = create_project(name, description)
    
    
    # 输出项目ID供调用者使用
    print(project_id)

if __name__ == "__main__":
    main()
