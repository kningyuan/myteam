#!/usr/bin/env python3
"""
Task Cleanup Skill — 清理工作区文件
删除已完成任务的 .trigger 和 .response 文件
"""
import sys
from pathlib import Path

HOME = Path.home()
BASE = HOME / ".openclaw"


def cleanup(project_id: str, agent_id: str, task_id: str) -> bool:
    """清理指定任务的 .trigger 和 .response 文件。"""
    cleaned = 0

    # .trigger 文件
    trigger_dir = BASE / f"workspace-{agent_id}" / ".trigger"
    trigger_file = trigger_dir / f"{project_id}_{task_id}.trigger"
    if trigger_file.exists():
        trigger_file.unlink()
        cleaned += 1

    # .response 文件（标准命名）
    resp_dir = BASE / f"workspace-{agent_id}" / ".response"
    resp_file = resp_dir / f"{project_id}_{task_id}.response"
    if resp_file.exists():
        resp_file.unlink()
        cleaned += 1

    # .response 文件（备用命名）
    for pattern in [f"{project_id}_{task_id}*.json", f"{task_id}_response.json", f"{task_id}.response"]:
        for f in sorted(resp_dir.glob(pattern)):
            try:
                f.unlink()
                cleaned += 1
            except OSError:
                pass

    if cleaned > 0:
        print(f"Cleaned {cleaned} files for task {task_id}")
        return True
    return True  # 没有文件也是正常


def main():
    if len(sys.argv) < 4:
        print("Usage: cleanup.py <project_id> <agent_id> <task_id>")
        sys.exit(1)

    project_id = sys.argv[1]
    agent_id = sys.argv[2]
    task_id = sys.argv[3]

    success = cleanup(project_id, agent_id, task_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()