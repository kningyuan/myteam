"""pytest fixtures for executor tests.

executor.py sets module-level constants (HOME, BASE, SKILLS) at import time
via Path.home(). We use importlib to load the module inside fixtures AFTER
monkeypatching HOME, so those constants point to the temp directory.
"""
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add team-ok directory to sys.path so that from common.config import ... works
# during executor_mod fixture execution
_team_ok_path = str(Path(__file__).resolve().parent.parent.parent)
if _team_ok_path not in sys.path:
    sys.path.insert(0, _team_ok_path)


def _load_executor_module():
    """Load executor.py using importlib (avoiding sys.modules cache issues)."""
    executor_path = Path(__file__).parent / "../scripts/executor.py"
    spec = importlib.util.spec_from_file_location(
        "executor_module", str(executor_path),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# We'll use session-scoped mock via conftest setup
# Don't import executor at module level — do it in fixtures


@pytest.fixture
def team_ok_paths(monkeypatch):
    """Add team-ok directory to sys.path (same as executor.py does at runtime)."""
    team_ok = str(Path(__file__).parent.parent / "../")
    if team_ok not in sys.path:
        sys.path.insert(0, team_ok)
    return team_ok


@pytest.fixture
def mock_home(tmp_path):
    """Mock Path.home() to return an isolated temp directory using unittest.mock.patch.

    Creates the ~/.openclaw directory structure BEFORE patching so that the
    executor module's sys.path.insert(Path.home() / '.openclaw' / 'skills' / 'team-ok')
    finds the common modules on import.
    """
    openclaw_dir = tmp_path / ".openclaw"
    openclaw_dir.mkdir()

    skills_team_ok = openclaw_dir / "skills" / "team-ok"
    skills_team_ok.mkdir(parents=True)

    # Create common module with __init__.py
    common = skills_team_ok / "common"
    common.mkdir()
    (common / "__init__.py").write_text("")

    # Copy actual common module files so executor's sys.path insert finds them
    actual_common = Path(__file__).parent.parent / "../common"
    for f in ["config.py", "logger.py", "validator.py"]:
        src = actual_common / f
        if src.exists():
            (common / f).write_text(src.read_text())

    # Create empty task directories for scripts
    for sub in ["project-init/scripts", "project-data/scripts",
                "task-queue/scripts", "agent-notify/scripts",
                "task-monitor/scripts", "task-cleanup/scripts",
                "task-resume/scripts"]:
        (skills_team_ok / sub).mkdir(parents=True, exist_ok=True)

    # Create task data directory and a default project directory
    tasks_projects = openclaw_dir / "tasks" / "projects"
    tasks_projects.mkdir(parents=True)
    (tasks_projects / "pro_test_001").mkdir(parents=True)

    # Create skill-logs directory (needed by get_skill_logger)
    (openclaw_dir / "tasks" / "projects" / "pro_test_001" / "skill-logs").mkdir(parents=True)

    # Create workspace trigger/response directories
    for aid in ["main", "developer", "tester", "researcher"]:
        ws = openclaw_dir / f"workspace-{aid}"
        (ws / ".trigger").mkdir(parents=True)
        (ws / ".response").mkdir(parents=True)

    # Apply mock AFTER creating directory structure
    with patch("pathlib.Path.home", return_value=tmp_path):
        yield tmp_path


@pytest.fixture
def executor_mod(mock_home, team_ok_paths):
    """Load executor module fresh (module-level constants use mocked HOME)."""
    return _load_executor_module()


@pytest.fixture
def sample_task_data():
    """Sample task_data.json content."""
    return {
        "project": {
            "id": "pro_test_001",
            "name": "测试项目",
            "description": "用于测试的项目",
            "status": "active",
        },
        "tasks": [
            {"id": "task_001", "name": "调研需求", "agent": "researcher",
             "status": "pending", "dependencies": []},
            {"id": "task_002", "name": "开发功能", "agent": "developer",
             "status": "pending", "dependencies": ["task_001"]},
            {"id": "task_003", "name": "测试验证", "agent": "tester",
             "status": "pending", "dependencies": ["task_002"]},
        ],
    }


@pytest.fixture
def executor(executor_mod):
    """Create an Executor instance using the freshly loaded module."""
    return executor_mod.Executor("pro_test_001")


@pytest.fixture
def executor_with_project(executor, executor_mod, sample_task_data):
    """Executor with a project already initialized."""
    executor_mod._write_task_data(executor.project_id, sample_task_data)
    executor.team = ["researcher", "developer", "tester", "product"]
    executor.tasks = sample_task_data["tasks"]
    return executor