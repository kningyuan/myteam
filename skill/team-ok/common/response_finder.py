#!/usr/bin/env python3
"""Response Finder — 多模式 .response 文件查找模块。

支持多种文件名模式、phase 校验、格式兜底（raw_response / runId）。
在 executor 轮询 Agent 响应时使用。

用法:
    path = find_response_file("pro_xxx", "developer", "task_001", expected_phase="execute")
    if path:
        response = json.loads(path.read_text(encoding="utf-8"))
"""
import json
import shutil
from pathlib import Path
from typing import Optional

from common.task_data_store import response_dir


def find_response_file(project_id: str, agent_id: str, task_id: str,
                       expected_phase: str = "") -> Optional[Path]:
    """查找 response 文件，支持多种文件名模式。

    Args:
        expected_phase: 如果指定，兜底文件会校验 phase 字段是否匹配

    Returns:
        找到的 response 文件路径，未找到返回 None
    """
    resp_dir = response_dir(agent_id)
    expected = resp_dir / f"{project_id}_{task_id}.response"
    if expected.exists():
        if expected_phase:
            try:
                data = json.loads(expected.read_text(encoding="utf-8"))
                if data.get("phase") == expected_phase:
                    return expected
            except Exception:
                pass
        else:
            return expected

    alt_patterns = [f"{task_id}_response.json", f"{task_id}.response", f"{task_id}.json"]
    for alt in alt_patterns:
        alt_path = resp_dir / alt
        if alt_path.exists() and _phase_matches(alt_path, expected_phase):
            shutil.copy2(str(alt_path), str(expected))
            return expected

    # Scan all .json/.response files with task_id in the name
    import os as _os
    for f in sorted(resp_dir.glob(f"*{task_id}*.json"),
                    key=lambda p: p.stat().st_mtime, reverse=True):
        if f.name == expected.name:
            continue
        if _phase_matches(f, expected_phase):
            shutil.copy2(str(f), str(expected))
            return expected

    # 兜底：如果 expected 文件存在但 phase 不匹配，检查是否可接受
    if expected.exists():
        try:
            data = json.loads(expected.read_text(encoding="utf-8"))
            if "raw_response" in data or "runId" in data:
                return expected
        except Exception:
            pass

    return None


def _phase_matches(path: Path, expected_phase: str) -> bool:
    if not expected_phase:
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("phase") == expected_phase
    except Exception:
        return False