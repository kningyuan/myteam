"""project_service 路径切换测试（0.6 旧路径清理）。

验证标准（UPGRADE-PLAN.md §T2）：
  - use_sqlite_project_store=True 时，list_projects 读 Store（SQLite）而非 task_data.json
  - SQLite 无数据时，能回退到 task_data.json
  - use_sqlite_project_store=False 时，读 task_data.json（旧行为不变）

== Mocking 策略 ==
  真实数据库不可达；Store 通过 patch 注入。
  task_data.json 通过 tmp_path 模拟（真正的 Path 对象，支持 sorted）。
  system_config.get → side_effect 控制 use_sqlite_project_store 标志位。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

# ==============================================================
# Fixtures: sample data
# ==============================================================

SQLITE_PROJECTS = [
    {
        "project_id": "pro_a",
        "title": "SQLite Project A",  # differs from JSON_PROJECTS to prove source
        "mode": "one_shot",
        "status": "completed",
        "created_at": "2026-06-01T00:00:00",
        "updated_at": "2026-06-02T00:00:00",
        "meta": {},
    },
    {
        "project_id": "pro_b",
        "title": "SQLite Project B",
        "mode": "recurring",
        "status": "in_progress",
        "created_at": "2026-06-03T00:00:00",
        "updated_at": "2026-06-04T00:00:00",
        "meta": {},
    },
    {
        "project_id": "pro_c_sqlite_only",  # exists only in SQLite
        "title": "SQLite Only",
        "mode": "one_shot",
        "status": "pending",
        "created_at": "2026-06-05T00:00:00",
        "updated_at": "2026-06-05T00:00:00",
        "meta": {},
    },
]

# task_data.json shape for two test projects
JSON_PROJECTS = {
    "pro_a": {
        "project": {
            "name": "Project A",
            "description": "Description A",
            "status": "completed",
        },
        "tasks": [
            {"id": "t1", "status": "completed"},
            {"id": "t2", "status": "completed"},
        ],
        "executor_pid": None,
    },
    "pro_b": {
        "project": {
            "name": "Project B",
            "description": "Description B",
            "status": "in_progress",
        },
        "tasks": [
            {"id": "t1", "status": "completed"},
            {"id": "t2", "status": "in_progress"},
        ],
        "executor_pid": 12345,
    },
}


@pytest.fixture
def json_dir(tmp_path):
    """Create a temporary directory tree that mirrors ``PROJECTS_DIR``.

    ``tmp_path / "pro_a" / "task_data.json"``  etc.  Also patches
    ``hub.services.project_service.PROJECTS_DIR`` to this tmp directory
    for the duration of the test.
    """
    for pid, data in JSON_PROJECTS.items():
        d = tmp_path / pid
        d.mkdir()
        (d / "task_data.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    with patch("hub.services.project_service.PROJECTS_DIR", tmp_path):
        yield


@pytest.fixture
def flag_on():
    """Set use_sqlite_project_store = True (直接覆盖模块级标志位)."""
    import hub.services.project_service as ps
    prev = ps._use_sqlite_store
    ps._use_sqlite_store = True
    yield
    ps._use_sqlite_store = prev


@pytest.fixture
def flag_off():
    """Set use_sqlite_project_store = False (直接覆盖模块级标志位)."""
    import hub.services.project_service as ps
    prev = ps._use_sqlite_store
    ps._use_sqlite_store = False
    yield
    ps._use_sqlite_store = prev


# ==============================================================
# Test 1: flag-on 时走 SQLite（数据存在）
# ==============================================================


class TestSqlitePath:
    """use_sqlite_project_store=True, SQLite 有数据 → 直接返回 SQLite 数据。"""

    def test_read_from_sqlite_returns_correct_fields(
        self, flag_on
    ):
        """list_projects 返回的每条记录包含正确的 key 和 source 字段。"""
        store_inst = MagicMock()
        store_inst.list_projects.return_value = SQLITE_PROJECTS
        with patch("hub.services.project_service.Store", return_value=store_inst, create=True):
            from hub.services.project_service import list_projects

            result = list_projects()

        assert len(result) == 3, "应当返回 3 个项目（含 SQLite-only 项目）"
        first = result[0]
        assert "id" in first
        assert "name" in first
        assert "status" in first
        assert "path" in first
        assert "task_count" in first
        assert "progress" in first

    def test_read_from_sqlite_does_not_touch_json(
        self, flag_on
    ):
        """_read_json 不应被调用（SQLite 数据已够，不读 task_data.json）。"""
        store_inst = MagicMock()
        store_inst.list_projects.return_value = SQLITE_PROJECTS
        with patch("hub.services.project_service.Store", return_value=store_inst, create=True), \
             patch("hub.services.project_service._read_json") as spy:
            from hub.services.project_service import list_projects

            result = list_projects()

        spy.assert_not_called()
        assert len(result) == 3

    def test_read_from_sqlite_maps_sqlite_to_summary_shape(
        self, flag_on
    ):
        """SQLite project_id → id, title → name 映射正确。"""
        store_inst = MagicMock()
        store_inst.list_projects.return_value = SQLITE_PROJECTS
        with patch("hub.services.project_service.Store", return_value=store_inst, create=True):
            from hub.services.project_service import list_projects

            result = list_projects()

        result_by_id = {r["id"]: r for r in result}
        # SQLite 数据独特字段，不来自 JSON 文件
        assert result_by_id["pro_a"]["name"] == "SQLite Project A"
        assert result_by_id["pro_a"]["status"] == "completed"
        assert result_by_id["pro_b"]["name"] == "SQLite Project B"
        assert result_by_id["pro_b"]["status"] == "in_progress"
        # pro_c_sqlite_only 仅存在于 SQLite 中
        assert "pro_c_sqlite_only" in result_by_id
        assert result_by_id["pro_c_sqlite_only"]["name"] == "SQLite Only"


# ==============================================================
# Test 2: flag-on 但 SQLite 无数据 → 回退到 task_data.json
# ==============================================================


class TestFallback:
    """use_sqlite_project_store=True 但 SQLite 列表为空 → 读 task_data.json。"""

    def test_fallback_to_task_data_json(
        self, flag_on, json_dir
    ):
        """当 Store.list_projects() 返回空 list 时，fallback 读取 task_data.json。"""
        store_inst = MagicMock()
        store_inst.list_projects.return_value = []
        with patch("hub.services.project_service.Store", return_value=store_inst, create=True):
            from hub.services.project_service import list_projects

            result = list_projects()

        # Fallback returns the JSON-based summary (2 projects in json_dir)
        assert len(result) == 2

    def test_fallback_produces_correct_summary(
        self, flag_on, json_dir
    ):
        """Fallback 路径输出的字段与旧 _summarize 一致。"""
        store_inst = MagicMock()
        store_inst.list_projects.return_value = []
        with patch("hub.services.project_service.Store", return_value=store_inst, create=True):
            from hub.services.project_service import list_projects

            result = list_projects()

        result_by_id = {r["id"]: r for r in result}
        assert result_by_id["pro_a"]["name"] == "Project A"
        assert result_by_id["pro_a"]["description"] == "Description A"
        assert result_by_id["pro_b"]["progress"] == 50  # 1/2 completed
        assert result_by_id["pro_b"]["executor_pid"] == 12345


# ==============================================================
# Test 3: flag-off → 旧行为，读 task_data.json
# ==============================================================


class TestJsonPath:
    """use_sqlite_project_store=False → 旧 task_data.json 路径。"""

    def test_flag_off_behavior_identical(self, flag_off, json_dir):
        """flag=false 时 list_projects 行为与旧代码一致：读 task_data.json 且不碰 Store。"""
        with patch("hub.services.project_service.Store", create=True) as store_cls:
            from hub.services.project_service import list_projects

            result = list_projects()

        store_cls.assert_not_called()
        assert len(result) == 2

    def test_flag_off_returns_correct_summary(self, flag_off, json_dir):
        """flag=false 返回的 summary 字段正确。"""
        with patch("hub.services.project_service.Store", create=True):
            from hub.services.project_service import list_projects

            result = list_projects()

        by_id = {r["id"]: r for r in result}
        assert by_id["pro_a"]["name"] == "Project A"
        assert by_id["pro_a"]["status"] == "completed"
        assert by_id["pro_a"]["task_count"] == 2
        assert by_id["pro_a"]["progress"] == 100
        assert by_id["pro_b"]["task_count"] == 2

    def test_flag_off_projects_dir_not_found(self, flag_off):
        """PROJECTS_DIR 不存在时返回空列表（崩溃保护）。"""
        nowhere = Path("/nonexistent/projects")
        with patch("hub.services.project_service.PROJECTS_DIR", nowhere), \
             patch("hub.services.project_service.Store", create=True):
            from hub.services.project_service import list_projects

            assert list_projects() == []
