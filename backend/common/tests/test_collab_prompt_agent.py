#!/usr/bin/env python3
"""子模块协作联动测试：prompt → agent。

验证协作链路：
  1. context_assembler.assemble_context 把 Store 中的对话历史（pins/summary/recent）
     组装成 {"text": str, "citations": list[dict]}，text 可被 prompt 层作为 lines 消费
  2. prompt_composer.compose_execute_layers 接收 lines（list[str]）并就地追加
     delivery_profile / task_type 配置的注入块（与 context_assembler 输出共存于同一 lines）
  3. prompt_composer.compose_delivery_variables 产出的变量能渲染 prompt_injections 模板
     占位符（{scaffold_script} 等），供 agent_transport.build_worker_prompt 内部调用
  4. agent_transport.build_worker_prompt 对 execute kind 调用 compose_execute_layers，
     把 prompt_composer 注入的块写进最终 worker 提示词（prompt → agent 接口契约对接）

参考 test_integration.py 的 FakeOpencode 模式与 conftest.py 的共享 fixture。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import common.paths as paths  # noqa: E402
from common.agent.agent_transport import build_worker_prompt  # noqa: E402
from common.contracts import InteractionRequest  # noqa: E402
from common.delivery.delivery_profiles import invalidate_delivery_profiles_cache  # noqa: E402
from common.prompt.context_assembler import AssemblerConfig, assemble_context  # noqa: E402
from common.prompt.prompt_composer import (  # noqa: E402
    compose_delivery_variables,
    compose_execute_layers,
)
from common.prompt.prompt_injections import (  # noqa: E402
    invalidate_injections_cache,
    iter_injection_blocks,
)
from common.prompt.prompt_templates import render_template  # noqa: E402
from common.store.store import Store  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """隔离 delivery_profiles / prompt_injections 配置，避免读工程文件污染。"""
    # 自定义 delivery_profile：light_v1 含过程产物，触发 compose_execute_layers 注入
    dp_file = tmp_path / "delivery_profiles.yaml"
    dp_file.write_text(
        """
profiles:
  none:
    description: 仅 deliverable
    process_artifacts: []
  light_v1:
    description: 测试用 light 过程
    process_artifacts:
      - align.md
      - verify.log
    scaffold: scripts/scaffold_light.sh
""",
        encoding="utf-8",
    )
    # 自定义 prompt_injections：execute kind + light_v1 profile 的注入块
    pi_file = tmp_path / "prompt_injections.yaml"
    pi_file.write_text(
        """
injections:
  execute:
    by_delivery_profile:
      light_v1:
        blocks:
          - |
            【交付过程 · light_v1】须完成 Align + Verify
            过程产物：align.md、verify.log
            脚手架：{scaffold_script}
            交卷前自检：① align.md 四节已填 ② deliverable 章节齐全 ③ verify.log 写入自检结论
    by_task_type:
      product-research:
        blocks:
          - |
            【task_type 注入 · product-research】须对齐产品视角
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "delivery_profiles_file", lambda: dp_file)
    monkeypatch.setattr(paths, "prompt_injections_file", lambda: pi_file)
    # 直接绑定到模块命名空间（from import 不受 paths 层 patch 影响）
    monkeypatch.setattr("common.delivery.delivery_profiles.delivery_profiles_file", lambda: dp_file)
    monkeypatch.setattr("common.prompt.prompt_injections.prompt_injections_file", lambda: pi_file)
    invalidate_delivery_profiles_cache()
    invalidate_injections_cache()
    yield tmp_path
    invalidate_delivery_profiles_cache()
    invalidate_injections_cache()


def _seed_conversation(store: Store, cid: str) -> None:
    """造一个含 pins / summary / recent 的对话，供 context_assembler 组装。"""
    store.create_conversation(cid, kind="dm", participants=["user", "research"],
                              meta={"pins": ["GEO 优化是核心目标", "必须引用数据来源"],
                                    "summary": "更早轮次：讨论了目标引擎与可引用性诊断"})
    # recent 消息（近窗逐字）
    store.append_message(cid, "user", text="请帮我做产品调研")
    store.append_message(cid, "agent", author="research",
                         text="好的，我会从用户、市场、机会三个维度展开")
    store.append_message(cid, "user", text="记得标注数据来源")


def test_context_assembler_output_consumable_by_prompt_composer(env):
    """context_assembler 输出的 text 是 str，可作为 lines 被 prompt_composer 接受。"""
    store = Store(env / "state.db")
    try:
        cid = "dm:research"
        _seed_conversation(store, cid)

        # 1) assemble_context 返回 {"text": str, "citations": list}
        out = assemble_context(store, cid, "产品调研", AssemblerConfig(char_budget=2000))
        assert isinstance(out, dict)
        text = out["text"]
        citations = out["citations"]
        assert isinstance(text, str) and text
        assert isinstance(citations, list)

        # pins / summary / recent 三段都进入 text
        assert "GEO 优化" in text            # pins
        assert "更早轮次" in text             # summary
        assert "产品调研" in text             # recent（用户提问）

        # 2) prompt_composer 接收 lines（list[str]），把 context_assembler 的 text 加入后
        #    调 compose_execute_layers 注入 light_v1 块——两模块输出共存于同一 lines
        lines: list[str] = []
        lines.append("【对话上下文（来自 context_assembler）】")
        lines.append(text)
        lines.append("")
        before = len(lines)
        # compose_execute_layers 就地 append 注入块
        compose_execute_layers(lines, "product-research", "light_v1")

        # 注入块确实追加到 lines 末尾（prompt_composer 不破坏 context_assembler 已写入内容）
        assert len(lines) > before
        joined = "\n".join(lines)
        assert "GEO 优化" in joined                   # context_assembler 输出仍在
        assert "交付过程 · light_v1" in joined         # prompt_composer 注入的新块
        assert "align.md" in joined
    finally:
        store.close()


def test_prompt_composer_variables_render_injection_templates(env):
    """compose_delivery_variables 产出的变量能渲染 prompt_injections 模板占位符。"""
    # 1) compose_delivery_variables 按 profile 解析变量（含 scaffold_script 路径）
    variables = compose_delivery_variables("light_v1")
    assert "scaffold_script" in variables
    assert "delivery_profile" in variables
    assert variables["delivery_profile"] == "light_v1"
    # scaffold 被解析为绝对路径（相对 MYTEAM_ROOT）
    assert Path(variables["scaffold_script"]).is_absolute()

    # 2) iter_injection_blocks 取出 execute kind + light_v1 的模板块
    blocks = iter_injection_blocks("execute", "product-research",
                                   delivery_profile="light_v1", path=paths.prompt_injections_file())
    assert blocks, "未取到 light_v1 注入块"
    raw_block = blocks[0]
    assert "{scaffold_script}" in raw_block  # 模板占位符待渲染

    # 3) render_template 用 variables 渲染占位符 → 产出可进入 worker prompt 的最终文本
    rendered = render_template(raw_block, variables)
    assert "{scaffold_script}" not in rendered          # 占位符已被替换
    assert variables["scaffold_script"] in rendered     # 实际路径写入文本
    assert "交付过程 · light_v1" in rendered


def test_build_worker_prompt_consumes_prompt_composer_layers(env, tmp_path, monkeypatch):
    """build_worker_prompt 对 execute kind 调用 compose_execute_layers，注入块进入最终提示词。"""
    # 隔离 agent 工作目录（build_worker_prompt 内部会拼 deliverables / response 路径）
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path / "workspaces")
    monkeypatch.setattr(paths, "PROJECTS_DIR", tmp_path / "project")

    # 构造 execute kind 的 InteractionRequest；research 绑定 delivery_profile=light_v1
    req = InteractionRequest(
        interaction_id="pro_pa:t1:execute:1",
        kind="execute",
        project_id="pro_pa",
        task_id="t1",
        agent_id="research",
        intent="完成竞品调研",
        input={"deliverable_path": "t1_deliverable.md"},
        constraints={"task_type": "research"},
    )
    resp_path = tmp_path / "resp" / "pro_pa_t1.response"
    resp_path.parent.mkdir(parents=True, exist_ok=True)
    deliv_dir = paths.deliverables_dir("pro_pa")

    prompt = build_worker_prompt(req, resp_path, deliv_dir)

    # 1) prompt_composer 注入的 light_v1 块确实出现在 worker prompt 中（prompt → agent 对接）
    assert "交付过程 · light_v1" in prompt
    assert "align.md" in prompt

    # 2) build_worker_prompt 自身的 execute 骨架也在（submit_result 命令、交付物路径）
    assert "submit_result" in prompt
    assert "t1_deliverable.md" in prompt
    assert str(resp_path) in prompt
