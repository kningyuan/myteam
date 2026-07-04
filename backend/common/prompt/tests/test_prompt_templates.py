#!/usr/bin/env python3
"""task_type / kind 标准 Prompt 模板渲染测试。"""
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.prompt.prompt_templates import (
    render_execute_intent,
    render_kind_intent,
    render_template,
)
from common.paths import prompt_templates_file


def test_render_template_replaces_placeholders():
    out = render_template("【对象】{task_description}\n【类型】{task_type}", {
        "task_description": "AionUi",
        "task_type": "research",
    })
    assert "AionUi" in out
    assert "research" in out


def test_research_execute_wraps_task_description():
    task = {
        "id": "t1",
        "name": "调研",
        "task_type": "research",
        "description": "【对象】https://example.com\n【视角】产品",
    }
    intent = render_execute_intent(task, prompt_templates_file())
    assert "【任务类型】research" in intent
    assert "https://example.com" in intent
    assert "禁止全仓扫描" in intent
    assert "submit_result" in intent


def test_strategy_execute_includes_uncertainty_hint():
    task = {
        "id": "t4",
        "task_type": "strategy",
        "description": "【输入】只读上游",
    }
    intent = render_execute_intent(task, prompt_templates_file())
    assert "不确定性" in intent
    assert "只读上游" in intent


def test_task_plan_kind_template():
    intent = render_kind_intent("task_plan", {
        "goal": "调研 AionUi",
        "team": "main, product, research",
    }, prompt_templates_file())
    assert "task_plan" in intent
    assert "调研 AionUi" in intent
    assert "main, product, research" in intent
    assert "description 只写" in intent


def test_missing_template_returns_description_only(tmp_path):
    tpl = tmp_path / "empty.yaml"
    tpl.write_text("task_types: {}\n", encoding="utf-8")
    task = {"task_type": "nonexistent_xyz", "description": "只做这一件事"}
    assert render_execute_intent(task, tpl) == "只做这一件事"


def test_default_template_for_registered_without_custom_prompt(tmp_path):
    """未单独配置 prompt 的 task_type 可走 _default 壳。"""
    tpl = tmp_path / "prompt_templates.yaml"
    tpl.write_text(
        "task_types:\n  _default:\n    execute: |\n      TYPE={task_type}\n      {task_description}\n",
        encoding="utf-8",
    )
    task = {"task_type": "content", "description": "写一篇文章"}
    intent = render_execute_intent(task, tpl)
    assert "TYPE=content" in intent
    assert "写一篇文章" in intent
