#!/usr/bin/env python3
"""Validation rules engine for task-executor (固定逻辑验证)."""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationResult:
    passed: bool
    failures: list[str] = field(default_factory=list)


def validate_output(content: str, requirements: dict) -> ValidationResult:
    """用固定逻辑验证 LLM 输出。

    requirements 结构:
    {
        "min_length": 500,              # 最小字数
        "required_sections": ["市场现状"],  # 必需章节标题
        "required_elements": ["表格"],     # 必需元素
        "must_include": ["关键词"],        # 必须包含的关键词
        "format": "markdown",            # 输出格式
    }
    """
    failures = []

    # 规则 1: 非空
    if not content or not content.strip():
        failures.append("输出为空，请重新生成")

    # 规则 2: 最小长度（中文 + 英文单词 + 数字/代码 token 混合计数）
    min_length = requirements.get("min_length")
    if min_length:
        chinese_chars = len(re.findall(r'[一-鿿]', content))
        word_tokens = len(re.findall(r'[a-zA-Z0-9_]+', content))
        total = chinese_chars + word_tokens
        if total < min_length:
            failures.append(f"字数不足：当前 {total} 字（中文 {chinese_chars} + 代码/英文 {word_tokens}），要求至少 {min_length} 字")

    # 规则 3: 必需章节
    for section in requirements.get("required_sections", []):
        if section not in content:
            failures.append(f"缺少章节：'{section}'，请在输出中包含此章节")

    # 规则 4: 必需元素
    for element in requirements.get("required_elements", []):
        if element == "表格" and "|" not in content:
            failures.append("缺少表格：请在输出中包含对比表格或数据表格")
        elif element == "代码" and "```" not in content:
            failures.append("缺少代码块：请在输出中使用 ``` 包裹代码")
        elif element == "列表" and not re.search(r'^[*-]\s|\d+\.\s', content, re.MULTILINE):
            failures.append("缺少列表：请在输出中使用项目符号或编号列表")

    # 规则 5: 必须包含的关键词
    for keyword in requirements.get("must_include", []):
        if keyword not in content:
            failures.append(f"缺少关键词：'{keyword}'，请在输出中包含此内容")

    # 规则 6: 格式检查
    fmt = requirements.get("format")
    if fmt == "markdown" and not re.search(r'^#', content, re.MULTILINE):
        failures.append("格式不符合要求：请使用 Markdown 格式（需要标题）")

    return ValidationResult(passed=len(failures) == 0, failures=failures)


def validate_deliverable_file(file_path, requirements: dict) -> ValidationResult:
    """验证交付物文件是否存在且内容符合要求。"""
    from pathlib import Path

    path = Path(file_path)

    # 规则 1: 文件是否存在
    if not path.exists():
        return ValidationResult(passed=False, failures=[f"交付物文件不存在：{file_path}"])

    # 规则 2: 文件是否为空
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return ValidationResult(passed=False, failures=["交付物文件内容为空"])

    # 规则 3: 验证内容
    return validate_output(content, requirements)


def generate_feedback(failures: list[str], task_name: str) -> str:
    """根据验证失败项生成给 Agent 的反馈提示。"""
    feedback = f"""你的任务「{task_name}」的输出未通过验证，请重新生成。

验证失败项：
"""
    for f in failures:
        feedback += f"\n❌ {f}"

    feedback += """

请针对以上问题修改输出，确保：
1. 逐一回应所有失败项
2. 保持内容质量和完整性
3. 不要简单重复之前的内容
4. 修改后保存到同一路径并调用 task-complete complete
"""
    return feedback


def validate_team_config(config: dict) -> ValidationResult:
    """验证 Main Agent 返回的团队配置（接受任意 agent 名称）。"""
    failures = []
    # 防御：Agent 可能返回 [{...}]（数组包对象），自动提取并记录日志
    if isinstance(config, list):
        if len(config) == 1 and isinstance(config[0], dict):
            config = config[0]
        else:
            failures.append(f"团队配置格式错误：期望 dict，收到 list（len={len(config)}）")
            return ValidationResult(passed=False, failures=failures)
    agents = config.get("agents", [])
    if not agents:
        failures.append("团队配置为空，请至少指定一个 agent")
        return ValidationResult(passed=False, failures=failures)

    for agent in agents:
        if not isinstance(agent, str) or not agent.strip():
            failures.append(f"非法的 agent 名称：'{agent}'，agent 必须为非空字符串")

    if len(agents) != len(set(agents)):
        failures.append("agent 列表有重复")

    return ValidationResult(passed=len(failures) == 0, failures=failures)


def validate_task_plan(plan: dict, team: list[str]) -> ValidationResult:
    """验证 Main Agent 返回的任务规划。"""
    failures = []
    tasks = plan.get("tasks", [])

    if not tasks:
        failures.append("任务列表为空，请至少定义一个任务")
        return ValidationResult(passed=False, failures=failures)

    # 第一遍：收集所有 task_ids
    task_ids = set()
    for t in tasks:
        tid = t.get("id", "")
        if not tid:
            failures.append("存在没有 id 的任务")
        elif tid in task_ids:
            failures.append(f"任务 id 重复：{tid}")
        else:
            task_ids.add(tid)

    # 第二遍：检查依赖存在性和 agent 分配
    for t in tasks:
        tid = t.get("id", "")
        if not tid:
            continue

        # 检查 agent 分配
        agent = t.get("agent", "")
        if agent and agent not in team:
            failures.append(f"任务 {tid} 分配的 agent '{agent}' 不在团队中")

        # 检查依赖存在性
        for dep in t.get("dependencies", []):
            if dep and dep not in task_ids:
                failures.append(f"任务 {tid} 依赖不存在的任务：{dep}")

        # 检查自依赖
        if tid in t.get("dependencies", []):
            failures.append(f"任务 {tid} 不能依赖自己")

    # DAG 循环检测
    if _has_cycle(tasks):
        failures.append("任务依赖存在循环依赖，请检查依赖关系")

    return ValidationResult(passed=len(failures) == 0, failures=failures)


def _has_cycle(tasks: list[dict]) -> bool:
    """Kahn 拓扑排序检测是否有环。"""
    from collections import defaultdict, deque

    in_degree = defaultdict(int)
    graph = defaultdict(list)

    for t in tasks:
        tid = t["id"]
        if tid not in in_degree:
            in_degree[tid] = 0
        for dep in t.get("dependencies", []):
            if dep:
                graph[dep].append(tid)
                in_degree[tid] += 1

    queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
    count = 0

    while queue:
        node = queue.popleft()
        count += 1
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return count != len(in_degree)


# ============================================================================
# 评估/执行阶段验证函数（executor 流程引擎专用）
# ============================================================================


def validate_evaluation_response(response: dict, expected_task_id: str) -> ValidationResult:
    """验证 Worker 返回的评估结果（phase=evaluate）。"""
    failures = []

    # 规则 1: phase 必须为 "evaluate"
    if response.get("phase") != "evaluate":
        failures.append("phase 必须为 'evaluate'，实际为 '{}'".format(response.get("phase", "缺失")))

    # 规则 2: task_id 必须匹配
    if response.get("task_id") != expected_task_id:
        failures.append(
            "task_id 不匹配：期望 '{}', 实际 '{}'".format(
                expected_task_id, response.get("task_id", "缺失")
            )
        )

    # 规则 3: should_split 必须存在且为布尔值
    if "should_split" not in response:
        failures.append("缺少 should_split 字段")
    elif not isinstance(response["should_split"], bool):
        failures.append("should_split 必须是布尔值 (true/false)，实际为 '{}'".format(
            type(response["should_split"]).__name__
        ))

    # 规则 4: 如果 should_split=true，sub_tasks 不能为空
    if response.get("should_split"):
        sub_tasks = response.get("sub_tasks", [])
        if not sub_tasks:
            failures.append("should_split=true 时 sub_tasks 不能为空")
        else:
            # 规则 5: 每个子任务必须有 id/name/description
            for i, st in enumerate(sub_tasks):
                for field in ["id", "name", "description"]:
                    if field not in st or not st[field]:
                        failures.append("子任务 {} 缺少 '{}' 字段".format(i, field))

                # 规则 6: 子任务依赖必须在 sub_tasks 中存在
                deps = st.get("dependencies", [])
                sub_task_ids = [s.get("id") for s in sub_tasks if s.get("id")]
                for dep in deps:
                    if dep and dep not in sub_task_ids:
                        failures.append("子任务 '{}' 依赖不存在的任务: '{}'".format(
                            st.get("id", i), dep
                        ))

            # 规则 7: 检查子任务依赖是否有循环（自依赖）
            if _has_subtask_cycle(sub_tasks):
                failures.append("子任务依赖存在循环依赖（自依赖）")

    return ValidationResult(passed=len(failures) == 0, failures=failures)


def validate_execution_response(response: dict, expected_task_id: str, expected_path: str) -> ValidationResult:
    """验证 Worker 返回的执行结果（phase=execute）。"""
    failures = []

    # 规则 1: phase 必须为 "execute"
    if response.get("phase") != "execute":
        failures.append("phase 必须为 'execute'，实际为 '{}'".format(response.get("phase", "缺失")))

    # 规则 2: task_id 必须匹配
    if response.get("task_id") != expected_task_id:
        failures.append(
            "task_id 不匹配：期望 '{}', 实际 '{}'".format(
                expected_task_id, response.get("task_id", "缺失")
            )
        )

    # 规则 3: status 必须合法
    valid_statuses = ["completed", "needs_retry"]
    if "status" not in response:
        failures.append("缺少 status 字段")
    elif response.get("status") not in valid_statuses:
        failures.append("status 必须为 '{}'，实际为 '{}'".format(
            "/".join(valid_statuses), response.get("status")
        ))

    # 规则 4: 如果 status=completed，deliverable_path 必须非空
    if response.get("status") == "completed":
        actual_path = response.get("deliverable_path", "")
        if not actual_path:
            failures.append("status=completed 时 deliverable_path 不能为空")

    # 规则 5: summary 不能过短（如果提供了）
    summary = response.get("summary", "")
    if summary and len(summary.strip()) < 10:
        failures.append("summary 过短（至少 10 字），实际 {} 字".format(len(summary)))

    return ValidationResult(passed=len(failures) == 0, failures=failures)


def _has_subtask_cycle(sub_tasks: list[dict]) -> bool:
    """检测子任务依赖是否有循环（主要是自依赖检测）。"""
    for st in sub_tasks:
        tid = st.get("id")
        deps = st.get("dependencies", [])
        # 自依赖检测
        if tid and tid in deps:
            return True
    return False