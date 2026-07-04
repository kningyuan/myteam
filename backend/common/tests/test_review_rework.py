#!/usr/bin/env python3
"""Task 3 测试：peer_review 触发重做循环。

验证 _review_with_rework 在评审不通过时用反馈驱动重做 execute，
最多 max_review_retries 次后仍未通过则降级为 needs_review。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.agent.agent_port import AgentPortResult  # noqa: E402
from common.process.process_types import ProcessConfig  # noqa: E402
from common.process.task_pipeline import TaskPipeline  # noqa: E402
from common.project.project_artifacts import (  # noqa: E402
    artifact_rel_path,
    task_deliverable_base,
)
from common.store.store import Store  # noqa: E402


# ---------- 辅助函数 ----------

def _make_deliverable(path: Path) -> None:
    """创建符合 custom-survey Gate 的交付物（含 背景/结论 两章，>=200 字）。"""
    content = (
        "# 测试报告\n\n"
        "## 背景\n"
        "这是一个测试用的背景描述，用于验证 peer_review 重做循环的正确性。"
        "需要确保内容长度超过最小字数要求，以便通过 Gate 的 min_length 检查。"
        "这里补充更多内容来确保长度达标，避免因为字数不足而导致 Gate 失败。\n\n"
        "## 结论\n"
        "这是测试结论部分，同样需要足够长的内容来满足 Gate 的要求。"
        "peer_review 重做循环应该在评审不通过时触发新一轮 execute。"
        "重做后的交付物应该被重新评审，直到通过或耗尽重试次数。\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _exec_response(iid: str, rel: str) -> dict:
    """构造通过契约+格式 Gate 的 execute 响应。"""
    return {
        "interaction_id": iid,
        "kind": "execute",
        "status": "ok",
        "notes": "完成执行",
        "quality": {"score": 0.85, "known_gaps": [], "notes": "自评良好"},
        "result": {
            "outcome": {
                "kind": "artifact",
                "artifact": {"path": rel, "title": "测试报告"},
            }
        },
    }


def _review_response(iid: str, passed: bool, feedback: str = "") -> dict:
    return {
        "interaction_id": iid,
        "kind": "review",
        "status": "ok",
        "result": {"passed": passed, "feedback": feedback},
    }


# ---------- FakePort ----------

class FakePort:
    """模拟 AgentPort：按 kind 返回预设响应，execute 时自动创建交付物文件。"""

    def __init__(self, exec_responses, review_results, dv_dir, rel_path):
        self._exec_responses = list(exec_responses)
        self._review_results = list(review_results)
        self._dv_dir = dv_dir
        self._rel_path = rel_path
        self.exec_calls = 0
        self.review_calls = 0

    def run(self, request) -> AgentPortResult:
        if isinstance(request, dict):
            kind = request.get("kind", "")
            iid = request.get("interaction_id", "")
        else:
            kind = getattr(request, "kind", "")
            iid = getattr(request, "interaction_id", "")

        if kind == "execute":
            _make_deliverable(self._dv_dir / self._rel_path)
            idx = min(self.exec_calls, len(self._exec_responses) - 1)
            resp = self._exec_responses[idx]
            self.exec_calls += 1
            return AgentPortResult("done", resp, iid, 1)

        if kind == "review":
            idx = min(self.review_calls, len(self._review_results) - 1)
            passed, feedback = self._review_results[idx]
            self.review_calls += 1
            return AgentPortResult("done", _review_response(iid, passed, feedback), iid, 1)

        if kind == "plan":
            return AgentPortResult("error", None, iid, 1, "plan not supported")

        return AgentPortResult("error", None, iid, 1, f"unknown kind: {kind}")


class FakeErrorPort(FakePort):
    """重做 execute 时返回端口错误。"""

    def run(self, request) -> AgentPortResult:
        if isinstance(request, dict):
            kind = request.get("kind", "")
            iid = request.get("interaction_id", "")
        else:
            kind = getattr(request, "kind", "")
            iid = getattr(request, "interaction_id", "")
        if kind == "execute" and ":r" in iid:
            return AgentPortResult("error", None, iid, 1, "CLI error during rework")
        return super().run(request)


# ---------- fixture ----------

@pytest.fixture()
def env(tmp_path, monkeypatch):
    """隔离路径 + 初始化 store/project/task。"""
    import common.paths as paths
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")

    store = Store(tmp_path / "state.db")
    store.upsert_project("p", title="测试项目")
    store.upsert_task("p", "t1", name="测试任务", agent="worker1",
                      reviewer="reviewer1", task_type="custom-survey")

    base_dir = task_deliverable_base("p", "t1", "custom-survey")
    rel_path = artifact_rel_path("t1", "custom-survey")
    yield store, base_dir, rel_path
    store.close()


def _make_pipeline(store, port, **cfg_kwargs):
    config = ProcessConfig(
        review_enabled=True,
        max_review_retries=2,
        plan_enabled=False,
        inject_context=False,
        **cfg_kwargs,
    )
    return TaskPipeline(
        store=store,
        port=port,
        config=config,
        release_files=lambda a, i: None,
    )


def _task_dict():
    return {
        "id": "t1",
        "name": "测试任务",
        "task_type": "custom-survey",
        "agent": "worker1",
        "reviewer": "reviewer1",
        "description": "测试 peer_review 重做循环",
    }


# ---------- 测试用例 ----------

class TestReviewRework:
    """peer_review + 重做循环测试。"""

    def test_pass_first_try(self, env):
        """评审首次通过 → completed，无重做。"""
        store, base_dir, rel_path = env
        port = FakePort(
            exec_responses=[_exec_response("p:t1:execute:1", rel_path)],
            review_results=[(True, "")],
            dv_dir=base_dir,
            rel_path=rel_path,
        )
        pipeline = _make_pipeline(store, port)

        _make_deliverable(base_dir / rel_path)
        resp = _exec_response("p:t1:execute:1", rel_path)
        outcome = pipeline._finalize_success(
            "p", _task_dict(), resp, 1, rel_path, "custom-survey",
            interaction_id="p:t1:execute:1", agent="worker1",
        )
        assert outcome.status == "completed"
        assert port.review_calls == 1
        assert port.exec_calls == 0

    def test_fail_then_rework_pass(self, env):
        """评审首次拒绝 → 重做 → 评审通过 → completed。"""
        store, base_dir, rel_path = env
        port = FakePort(
            exec_responses=[
                _exec_response("p:t1:execute:1", rel_path),
                _exec_response("p:t1:execute:r1", rel_path),
            ],
            review_results=[
                (False, "背景部分不够详细，需要补充更多上下文"),
                (True, ""),
            ],
            dv_dir=base_dir,
            rel_path=rel_path,
        )
        pipeline = _make_pipeline(store, port)

        _make_deliverable(base_dir / rel_path)
        resp = _exec_response("p:t1:execute:1", rel_path)
        outcome = pipeline._finalize_success(
            "p", _task_dict(), resp, 1, rel_path, "custom-survey",
            interaction_id="p:t1:execute:1", agent="worker1",
        )
        assert outcome.status == "completed"
        assert port.review_calls == 2
        assert port.exec_calls == 1

    def test_all_fail_exhausted(self, env):
        """评审全部拒绝 → needs_review（耗尽 max_review_retries=2）。"""
        store, base_dir, rel_path = env
        port = FakePort(
            exec_responses=[
                _exec_response("p:t1:execute:1", rel_path),
                _exec_response("p:t1:execute:r1", rel_path),
                _exec_response("p:t1:execute:r2", rel_path),
            ],
            review_results=[
                (False, "第一次拒绝"),
                (False, "第二次拒绝"),
                (False, "第三次拒绝"),
            ],
            dv_dir=base_dir,
            rel_path=rel_path,
        )
        pipeline = _make_pipeline(store, port)

        _make_deliverable(base_dir / rel_path)
        resp = _exec_response("p:t1:execute:1", rel_path)
        outcome = pipeline._finalize_success(
            "p", _task_dict(), resp, 1, rel_path, "custom-survey",
            interaction_id="p:t1:execute:1", agent="worker1",
        )
        assert outcome.status == "needs_review"
        assert port.review_calls == 3
        assert port.exec_calls == 2

    def test_rework_port_error(self, env):
        """重做时端口错误 → needs_review。"""
        store, base_dir, rel_path = env
        port = FakeErrorPort(
            exec_responses=[_exec_response("p:t1:execute:1", rel_path)],
            review_results=[(False, "需要修改")],
            dv_dir=base_dir,
            rel_path=rel_path,
        )
        pipeline = _make_pipeline(store, port)

        _make_deliverable(base_dir / rel_path)
        resp = _exec_response("p:t1:execute:1", rel_path)
        outcome = pipeline._finalize_success(
            "p", _task_dict(), resp, 1, rel_path, "custom-survey",
            interaction_id="p:t1:execute:1", agent="worker1",
        )
        assert outcome.status == "needs_review"
        assert port.review_calls == 1

    def test_no_reviewer_skips_review(self, env):
        """无 reviewer → 跳过评审，使用 quality_status。"""
        store, base_dir, rel_path = env
        store.upsert_task("p", "t1", name="测试任务", agent="worker1",
                          reviewer="", task_type="custom-survey")
        port = FakePort(
            exec_responses=[_exec_response("p:t1:execute:1", rel_path)],
            review_results=[],
            dv_dir=base_dir,
            rel_path=rel_path,
        )
        pipeline = _make_pipeline(store, port)

        _make_deliverable(base_dir / rel_path)
        task = _task_dict()
        task["reviewer"] = ""
        resp = _exec_response("p:t1:execute:1", rel_path)
        outcome = pipeline._finalize_success(
            "p", task, resp, 1, rel_path, "custom-survey",
            interaction_id="p:t1:execute:1", agent="worker1",
        )
        assert outcome.status == "completed"
        assert port.review_calls == 0

    def test_review_disabled_uses_quality(self, env):
        """review_enabled=False → 使用 quality_status。"""
        store, base_dir, rel_path = env
        port = FakePort(
            exec_responses=[_exec_response("p:t1:execute:1", rel_path)],
            review_results=[],
            dv_dir=base_dir,
            rel_path=rel_path,
        )
        config = ProcessConfig(
            review_enabled=False,
            max_review_retries=2,
            plan_enabled=False,
            inject_context=False,
        )
        pipeline = TaskPipeline(
            store=store,
            port=port,
            config=config,
            release_files=lambda a, i: None,
        )

        _make_deliverable(base_dir / rel_path)
        resp = _exec_response("p:t1:execute:1", rel_path)
        outcome = pipeline._finalize_success(
            "p", _task_dict(), resp, 1, rel_path, "custom-survey",
            interaction_id="p:t1:execute:1", agent="worker1",
        )
        assert outcome.status == "completed"
        assert port.review_calls == 0

    def test_rework_feedback_injected(self, env):
        """重做请求中应包含评审反馈作为 retry_feedback。"""
        store, base_dir, rel_path = env
        captured_feedback = []

        class CapturingPort(FakePort):
            def run(self, request):
                if isinstance(request, dict):
                    kind = request.get("kind", "")
                    fb = request.get("retry_feedback", [])
                else:
                    kind = getattr(request, "kind", "")
                    fb = getattr(request, "retry_feedback", [])
                if kind == "execute" and fb:
                    captured_feedback.append(fb)
                return super().run(request)

        port = CapturingPort(
            exec_responses=[
                _exec_response("p:t1:execute:1", rel_path),
                _exec_response("p:t1:execute:r1", rel_path),
            ],
            review_results=[
                (False, "背景部分需要补充用户画像分析"),
                (True, ""),
            ],
            dv_dir=base_dir,
            rel_path=rel_path,
        )
        pipeline = _make_pipeline(store, port)

        _make_deliverable(base_dir / rel_path)
        resp = _exec_response("p:t1:execute:1", rel_path)
        outcome = pipeline._finalize_success(
            "p", _task_dict(), resp, 1, rel_path, "custom-survey",
            interaction_id="p:t1:execute:1", agent="worker1",
        )
        assert outcome.status == "completed"
        assert len(captured_feedback) == 1
        assert "背景部分需要补充用户画像分析" in captured_feedback[0][0]
