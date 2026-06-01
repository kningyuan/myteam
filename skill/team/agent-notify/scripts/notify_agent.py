#!/usr/bin/env python3
"""
Agent 间消息通知 Skill
通过 myteam API（项目群 @mention 或直连 notify）实现 Agent 间通信

支持命令：
  dispatch   - 通知 Agent 有新任务
  complete   - 通知 Main Agent 任务完成
  evaluate   - 通知 Agent 评估任务是否需要拆分（新增）
  execute    - 通知 Agent 执行任务（新增）
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

TEAM_OK_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TEAM_OK_DIR))

from bridge.myteam_notify import send_agent_message, send_project_dispatch
from common.config import AGENT_MSG_TIMEOUT
from common.graph_gate import assert_valid_task_graph
from common.logger import get_skill_logger, log_skill_step_failure, normalize_project_id
from common.paths import (
    deliverables_dir,
    project_data_script,
    response_dir,
    task_data_path,
    trigger_file_path,
    workspace_dir,
)

# Agent ID 映射表
AGENT_ID_MAP = {
    'main': 'main',
    'product': 'product',
    'developer': 'developer',
    'designer': 'designer',
    'researcher': 'researcher',
    'content': 'content',
    'social': 'social',
    'seo': 'seo',
    'email': 'email',
    'docs': 'docs',
    'ops': 'ops',
    'consultation': 'consultation',
    'coordinator': 'coordinator',
    'tester': 'tester',
    'deputy': 'deputy',
    'analyst': 'seo',
}

# Agent 中文名称
AGENT_NAME_MAP = {
    'main': '项目协调专家',
    'product': '产品经理',
    'developer': '开发工程师',
    'designer': 'UI 设计师',
    'researcher': '调研专家',
    'content': '内容创作者',
    'social': '社交媒体运营',
    'seo': 'SEO 优化师',
    'email': '邮件营销专家',
    'docs': '技术文档工程师',
    'ops': '运维工程师',
    'consultation': '咨询顾问',
    'coordinator': '合规审查员',
    'tester': '测试工程师',
    'deputy': '副协调员',
}




def get_project_data(project_id):
    """读取项目数据（带自动修正）"""
    corrected_id = normalize_project_id(project_id)
    project_file = task_data_path(corrected_id)
    if not project_file.exists():
        return None
    with open(project_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_task_info(project_data, task_id):
    """获取任务信息（搜索顶层任务和子任务）"""
    if not project_data:
        return None
    for task in project_data.get('tasks', []):
        if task['id'] == task_id:
            return task
        # 搜索嵌套子任务
        for subtask in task.get('subtasks', []):
            if subtask['id'] == task_id:
                return subtask
    return None


def _is_ack_timeout(msg: str) -> bool:
    s = (msg or "").lower()
    return "timeout" in s or "timed out" in s


def _notify_agent(agent_id, message, timeout=AGENT_MSG_TIMEOUT, thinking='minimal',
                  project_id=None, deliver=False, task_id=None, wait_response=None,
                  response_file=None):
    """统一通知入口：dispatch 走项目群，其余走 myteam notify API。"""
    logger = get_skill_logger(project_id) if project_id else None
    msg_preview = message[:300].replace('\n', '\\n')
    if logger:
        logger.info(
            f"[AGENT_MSG_SEND] agent={agent_id}, project={project_id}, thinking={thinking}, "
            f"deliver={deliver}, timeout={timeout}, msg_preview={msg_preview}",
            extra={'skill_name': 'AGENT_NOTIFY'},
        )

    try:
        if response_file:
            success, output = send_agent_message(
                agent_id, message, timeout=timeout, thinking=thinking,
                project_id=project_id, deliver=deliver,
                task_id=task_id, wait_response=wait_response,
                response_file=response_file,
            )
        elif project_id and task_id and not deliver:
            success, output = send_project_dispatch(project_id, agent_id, message, task_id)
        else:
            success, output = send_agent_message(
                agent_id,
                message,
                timeout=timeout,
                thinking=thinking,
                project_id=project_id,
                deliver=deliver,
                task_id=task_id,
                wait_response=wait_response,
                response_file=response_file,
            )
    except Exception as e:
        if logger:
            logger.error(
                f"[AGENT_MSG_ERROR] agent={agent_id}, project={project_id}, error={str(e)}",
                extra={'skill_name': 'AGENT_NOTIFY'},
            )
        return False, str(e)

    if success:
        resp_preview = (output or "")[:300].replace('\n', '\\n')
        if logger:
            logger.info(
                f"[AGENT_MSG_SUCCESS] agent={agent_id}, project={project_id}, resp_preview={resp_preview}",
                extra={'skill_name': 'AGENT_NOTIFY'},
            )
        return True, output or ""
    if logger:
        logger.error(
            f"[AGENT_MSG_FAIL] agent={agent_id}, project={project_id}, error={output}",
            extra={'skill_name': 'AGENT_NOTIFY'},
        )
    if _is_ack_timeout(output or ""):
        return False, output
    return False, output or "notify failed"


def notify_task_dispatch(project_id, task_id, agent_id, require_valid_graph=False):
    """通知 Agent 有新任务分派"""
    logger = get_skill_logger(project_id)
    logger.info(f"[NOTIFY_DISPATCH_START] project={project_id}, task={task_id}, agent={agent_id}", extra={'skill_name': 'AGENT_NOTIFY'})

    corrected_id = normalize_project_id(project_id)
    if require_valid_graph:
        assert_valid_task_graph(corrected_id)

    project_data = get_project_data(project_id)
    task = get_task_info(project_data, task_id)

    if not project_data or not task:
        logger.error(f"[NOTIFY_DISPATCH_FAIL] project={project_id}, task={task_id}, reason=data_not_found", extra={'skill_name': 'AGENT_NOTIFY'})
        return False, "项目或任务不存在"

    project_name = project_data['project']['name']
    task_name = task['name']
    description = task.get('description', '无描述')

    ws = workspace_dir(agent_id)
    trigger_rel = trigger_file_path(agent_id, corrected_id, task_id)
    pdata = project_data_script()

    message = f"""项目协作：你有一个新任务需要执行

项目：{project_name}
任务：{task_name}
任务 ID: {task_id}

任务描述：{description}

请读取 {trigger_rel} 获取任务详情并开始执行。

【重要】开始执行前，请先调用以下命令更新任务状态为 in_progress（将触发群通报）：
exec: {pdata} update-task {project_id} {task_id} in_progress

执行完毕后，请在 .response/ 目录返回 JSON 响应。"""

    trigger_file = trigger_rel
    if trigger_file.exists():
        try:
            with open(trigger_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['notified_at'] = datetime.now().isoformat()
            data['notified_success'] = True
            with open(trigger_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[TRIGGER_UPDATE_WARN] file={trigger_file}, error={str(e)}", extra={'skill_name': 'AGENT_NOTIFY'})

    success, output = _notify_agent(
        agent_id, message, project_id=project_id, deliver=False,
        task_id=task_id, wait_response=False,
    )

    if success:
        logger.info(f"[NOTIFY_DISPATCH_END] project={project_id}, task={task_id}, agent={agent_id}, status=success", extra={'skill_name': 'AGENT_NOTIFY'})
        return True, f"已通知 {AGENT_NAME_MAP.get(agent_id, agent_id)} 执行任务"
    else:
        logger.error(f"[NOTIFY_DISPATCH_END] project={project_id}, task={task_id}, agent={agent_id}, status=fail, error={output}", extra={'skill_name': 'AGENT_NOTIFY'})
        return False, f"通知失败：{output}"


def notify_task_complete(project_id, task_id, agent_id, require_valid_graph=False):
    """通知 Main Agent 任务已完成"""
    logger = get_skill_logger(project_id)
    logger.info(f"[NOTIFY_COMPLETE_START] project={project_id}, task={task_id}, agent={agent_id}", extra={'skill_name': 'AGENT_NOTIFY'})

    corrected_id = normalize_project_id(project_id)
    if require_valid_graph:
        assert_valid_task_graph(corrected_id)

    project_data = get_project_data(project_id)
    task = get_task_info(project_data, task_id)

    if not project_data or not task:
        logger.error(f"[NOTIFY_COMPLETE_FAIL] project={project_id}, task={task_id}, reason=data_not_found", extra={'skill_name': 'AGENT_NOTIFY'})
        return False, "项目或任务不存在"

    project_name = project_data['project']['name']
    task_name = task['name']
    agent_name = AGENT_NAME_MAP.get(agent_id, agent_id)

    deliverables_dir_path = deliverables_dir(corrected_id)
    deliverables = list(deliverables_dir_path.glob(f"{task_id}_*.md")) if deliverables_dir_path.exists() else []

    message = f"""项目协作：任务执行完毕

项目：{project_name}
任务：{task_name}
任务 ID: {task_id}
执行 Agent: {agent_name}

任务已完成，交付物已保存到 deliverables/ 目录。"""

    if deliverables:
        message += "\n\n交付物文件:\n"
        for f in deliverables:
            message += f"- {f.name}\n"

    message += "\n请调度下一个任务。"

    success, output = _notify_agent('main', message, project_id=project_id, deliver=True)

    if success:
        logger.info(f"[NOTIFY_COMPLETE_END] project={project_id}, task={task_id}, agent={agent_id}, status=success", extra={'skill_name': 'AGENT_NOTIFY'})
        return True, output
    else:
        logger.error(f"[NOTIFY_COMPLETE_END] project={project_id}, task={task_id}, agent={agent_id}, status=fail, error={output}", extra={'skill_name': 'AGENT_NOTIFY'})
        return False, f"通知失败：{output}"


def notify_task_evaluate(project_id, task_id, agent_id, ack_timeout=None):
    """通知 Agent 评估任务是否需要拆分。

    Args:
        ack_timeout: ACK 超时秒数。设置后不等待完整响应，由调用方轮询 .response 文件。
    """
    logger = get_skill_logger(project_id)
    logger.info(f"[NOTIFY_EVALUATE_START] project={project_id}, task={task_id}, agent={agent_id}, ack_timeout={ack_timeout}",
                extra={'skill_name': 'AGENT_NOTIFY'})

    corrected_id = normalize_project_id(project_id)
    project_data = get_project_data(corrected_id)
    task = get_task_info(project_data, task_id)

    if not project_data or not task:
        logger.error(f"[NOTIFY_EVALUATE_FAIL] project={project_id}, task={task_id}, reason=data_not_found",
                     extra={'skill_name': 'AGENT_NOTIFY'})
        return False, "项目或任务不存在"

    project_name = project_data['project']['name']
    task_name = task['name']
    description = task.get('description', '无描述')

    message = f"""项目协作：请评估任务是否需要拆分子任务

项目：{project_name}
任务：{task_name}
任务 ID: {task_id}

任务描述：{description}

请读取 {trigger_file_path(agent_id, corrected_id, task_id)} 获取任务详情。

【重要】请只输出以下 JSON，不要包含任何其他文字、markdown 代码块或解释：
{{
  "phase": "evaluate",
  "task_id": "{task_id}",
  "should_split": true/false,
  "reason": "为什么需要/不需要拆分",
  "sub_tasks": [
    {{
      "id": "子任务 ID",
      "name": "子任务名称",
      "description": "子任务描述",
      "dependencies": ["依赖的任务 ID 列表"]
    }}
  ]
}}

不要直接调用任何 skill 脚本。"""

    timeout_value = ack_timeout if ack_timeout else 1800
    resp_path = response_dir(agent_id) / f"{project_id}_{task_id}.response"
    success, output = _notify_agent(
        agent_id, message, timeout=timeout_value, project_id=project_id,
        task_id=task_id, deliver=False, wait_response=False,
        response_file=str(resp_path),
    )

    logger.info(f"[NOTIFY_EVALUATE_END] project={project_id}, task={task_id}, agent={agent_id}, status=success",
                extra={'skill_name': 'AGENT_NOTIFY'})
    return True, f"已通知 {AGENT_NAME_MAP.get(agent_id, agent_id)} 评估任务"


def notify_task_execute(project_id, task_id, agent_id, parent_task=None, sub_task_index=None, ack_timeout=None):
    """通知 Agent 执行任务。

    Args:
        ack_timeout: ACK 超时秒数。设置后使用短超时等待 Agent 确认收到消息，
                     不等待完整响应，由调用方轮询 .response 文件。
    """
    logger = get_skill_logger(project_id)
    logger.info(f"[NOTIFY_EXECUTE_START] project={project_id}, task={task_id}, agent={agent_id}, ack_timeout={ack_timeout}",
                extra={'skill_name': 'AGENT_NOTIFY'})

    corrected_id = normalize_project_id(project_id)
    project_data = get_project_data(corrected_id)
    task = get_task_info(project_data, task_id)

    if not project_data or not task:
        logger.error(f"[NOTIFY_EXECUTE_FAIL] project={project_id}, task={task_id}, reason=data_not_found",
                     extra={'skill_name': 'AGENT_NOTIFY'})
        return False, "项目或任务不存在"

    project_name = project_data['project']['name']
    task_name = task['name']
    description = task.get('description', '无描述')

    # 确定交付物路径
    deliverables_dir_path = deliverables_dir(corrected_id)
    deliverables_dir_path.mkdir(parents=True, exist_ok=True)
    deliverable_filename = f"{task_id}_deliverable.md"
    deliverable_path = str(deliverables_dir_path / deliverable_filename)

    # 组装通知消息
    extra_info = []
    if parent_task:
        extra_info.append(f"父任务: {parent_task}")
    if sub_task_index:
        extra_info.append(f"子任务进度: {sub_task_index}")
    extra_msg = "\n".join(extra_info)

    # 从 .trigger 文件读取模板内容
    agent_ws = workspace_dir(agent_id)
    trigger_path = trigger_file_path(agent_id, corrected_id, task_id)
    template_guide = ""
    if trigger_path.exists():
        try:
            trigger_data = json.loads(trigger_path.read_text(encoding="utf-8"))
            tmpl = trigger_data.get("template", {})
            sections = tmpl.get("sections", []) if isinstance(tmpl, dict) else []
            if sections and isinstance(sections, list):
                parts = ["\n\n【交付指引】"]
                for sec in sections:
                    if not isinstance(sec, dict):
                        continue
                    name = sec.get("name", "")
                    desc = sec.get("description", "")
                    example = sec.get("example", "")
                    sec_lines = [f"\n📋 {name}：{desc}"]
                    if example:
                        sec_lines.append(f"  例如：{example[:120]}")
                    parts.extend(sec_lines)
                structure = tmpl.get("structure", [])
                if structure and isinstance(structure, list):
                    parts.append("\n📐 结构要求：")
                    for s in structure:
                        parts.append(f"  - {s}")
                template_guide = "\n".join(parts)

            # 附加质量门禁检查规则（standard_requirements）
            std = trigger_data.get("standard_requirements", {})
            if std and isinstance(std, dict):
                req_parts = ["\n\n【质量门禁要求 — 必须满足】"]
                secs = std.get("required_sections", [])
                if secs:
                    req_parts.append(f"\n📌 必需章节：{', '.join(secs)}")
                kws = std.get("must_include_keywords", [])
                if kws:
                    req_parts.append(f"\n🔑 必须包含关键词：{', '.join(kws)}")
                ml = std.get("min_length", 0)
                if ml:
                    req_parts.append(f"\n📏 最小内容量：{ml} 字以上")
                if len(req_parts) > 1:
                    template_guide += "\n".join(req_parts)
        except Exception:
            pass

    message = f"""项目协作：请执行任务

项目：{project_name}
任务：{task_name}
任务 ID: {task_id}
{extra_msg}

任务描述：{description}
交付物路径：{deliverable_path}{template_guide}

请读取 {trigger_path} 获取完整任务详情。

【重要】执行完成后，请将以下 JSON 写入文件，不要通过聊天回复。聊天中的内容会被忽略。
文件：{response_dir(agent_id) / f"{corrected_id}_{task_id}.response"}
{{
  "phase": "execute",
  "task_id": "{task_id}",
  "status": "completed",
  "deliverable_path": "{deliverable_path}",
  "summary": "任务执行摘要，100-200 字",
  "notes": "需要说明的事项"
}}

不要直接调用任何 skill 脚本。"""

    timeout_value = ack_timeout if ack_timeout else 1800
    resp_path = response_dir(agent_id) / f"{project_id}_{task_id}.response"
    success, output = _notify_agent(
        agent_id, message, timeout=timeout_value, project_id=project_id,
        task_id=task_id, deliver=False, wait_response=False,
        response_file=str(resp_path),
    )

    logger.info(f"[NOTIFY_EXECUTE_END] project={project_id}, task={task_id}, agent={agent_id}, status=success",
                extra={'skill_name': 'AGENT_NOTIFY'})
    return True, f"已通知 {AGENT_NAME_MAP.get(agent_id, agent_id)} 执行任务"


def _write_response_file(project_id: str, agent_id: str, task_id: str, raw_output: str, expected_phase: str = ""):
    """从 Agent 回复中提取 JSON 并写入 .response 文件。

    如果 Agent 已通过文件写入工具在 .response 目录写入了有效 JSON，则保留 Agent 的版本，
    不覆盖 Agent 自行写入的响应（此时 raw_output 是自然语言描述而非 JSON）。
    """
    import re
    agent_ws = workspace_dir(agent_id)
    resp_file = response_dir(agent_id) / f"{project_id}_{task_id}.response"
    resp_file.parent.mkdir(parents=True, exist_ok=True)

    # 优先检查 Agent 已通过文件工具写入的干净 JSON 文件
    # Agent 可能使用不同命名格式（_evaluate.json / _execute.json / .json 等）
    # 扫描 .response 目录下所有匹配 {project_id}_{task_id}*.json 的文件
    resp_dir = response_dir(agent_id)
    prefix = f"{project_id}_{task_id}"
    for candidate in sorted(resp_dir.glob(f"{prefix}*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        # 跳过 .response 自身（它是我们要写入的目标文件）
        if candidate.name == f"{prefix}.response":
            continue
        try:
            candidate_data = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(candidate_data, dict) and any(k in candidate_data for k in ("phase", "status", "should_split")):
                if expected_phase and candidate_data.get("phase") != expected_phase:
                    continue
                # Agent 已写入干净 JSON 文件，更新 .response 并返回
                with open(resp_file, "w", encoding="utf-8") as f:
                    json.dump(candidate_data, f, ensure_ascii=False, indent=2)
                return
        except (json.JSONDecodeError, Exception):
            pass

    # 回退：检查已有的 .response 文件
    if resp_file.exists():
        try:
            existing = json.loads(resp_file.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and any(k in existing for k in ("phase", "status", "should_split")):
                if expected_phase and existing.get("phase") != expected_phase:
                    pass
                else:
                    return
        except (json.JSONDecodeError, Exception):
            pass  # 文件损坏或格式不对，继续用 stdout 覆盖

    # 迁移开关（D11/F1）：契约严格路径下不做 JSON 抢救。
    # Agent 须用 submit_result 写回经契约校验的 .response；此处找不到合法响应宁可不写（拒绝），
    # 让流程按「缺失/超时」处理，而不是替 Agent 猜测意图。
    try:
        from common.contracts import contracts_enabled
        if contracts_enabled():
            get_skill_logger(project_id).info(
                f"[RESPONSE_FILE] 契约模式：跳过 JSON 抢救，等待 submit_result 写回合法 .response（{resp_file}）")
            return
    except Exception:
        pass

    content = raw_output.strip()
    # 尝试从 markdown 代码块中提取 JSON（平衡花括号匹配）
    def _extract_json_from_fence(text: str) -> str:
        m = re.search(r'```(?:json)?\s*(\{.*)\s*```', text, re.DOTALL)
        if not m:
            return text
        candidate = m.group(1)
        depth = 0
        for i, c in enumerate(candidate):
            if c == '{': depth += 1
            elif c == '}': depth -= 1
            if depth == 0:
                return candidate[:i+1].strip()
        return text
    content = _extract_json_from_fence(content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # 尝试修复常见 JSON 问题：全角引号 → 半角引号
        fixed_content = content.replace('“', '"').replace('”', '"')
        try:
            parsed = json.loads(fixed_content)
        except json.JSONDecodeError:
            # 再尝试：Agent 经常在字符串内使用未转义的双引号，如 "USB-C"
            # 策略：找到第一个 "{" 和最后一个 "}"，提取子串尝试解析
            try:
                start = content.index('{')
                end = content.rindex('}')
                candidate = content[start:end+1]
                parsed = json.loads(candidate)
            except (ValueError, json.JSONDecodeError):
                logger = get_skill_logger(project_id)
                logger.warning(f"[RESPONSE_FILE] Agent 返回非 JSON，原文保存: {content[:200]}")
                parsed = {"raw_response": content}

    with open(resp_file, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    logger = get_skill_logger(project_id)
    logger.info(f"[RESPONSE_FILE] written: {resp_file}")


def notify_team_config(project_id, agent_id):
    """通知 Agent 配置团队，服务器后台写回 .response 文件"""
    logger = get_skill_logger(project_id)
    agent_ws = workspace_dir(agent_id)
    req_file = response_dir(agent_id) / f"{project_id}_team_config.request"
    resp_file = response_dir(agent_id) / f"{project_id}_team_config.response"

    if not req_file.exists():
        logger.error(f"[TEAM_CONFIG_FAIL] request file not found: {req_file}")
        return False, "请求文件不存在"

    with open(req_file, "r", encoding="utf-8") as f:
        req = json.load(f)

    retry_feedback = req.get("retry_feedback")
    feedback_part = ""
    if retry_feedback:
        feedback_text = "；".join(retry_feedback) if isinstance(retry_feedback, list) else str(retry_feedback)
        feedback_part = f"\n\n【上次验证失败】\n{feedback_text}\n\n请严格按照要求的 JSON 格式重新回复，不要回复其他内容。"

    message = (
        f"项目协作: 团队配置请求\n\n"
        f"项目：{req.get('project_id')}\n\n"
        f"{req.get('message')}\n\n"
        f"这是一个系统级别的 JSON 配置请求。请只输出以下格式的 JSON，不要包含任何其他文字、markdown 代码块或解释：\n"
        f"格式：{json.dumps(req.get('expected_format', {}), ensure_ascii=False, indent=2)}"
        f"{feedback_part}"
    )

    thinking_mode = "auto" if retry_feedback else "minimal"
    # 异步通知：服务器后台收集回复并写入 resp_file
    _notify_agent(agent_id, message, project_id=project_id, deliver=False,
                  thinking=thinking_mode, wait_response=False,
                  response_file=str(resp_file))
    logger.info(f"[TEAM_CONFIG_NOTIFIED] async response to: {resp_file}")
    return True, "团队配置已通知"


def notify_task_plan(project_id, agent_id):
    """通知 Agent 规划任务，写回 .response 文件"""
    logger = get_skill_logger(project_id)
    agent_ws = workspace_dir(agent_id)
    req_file = response_dir(agent_id) / f"{project_id}_task_plan.request"
    resp_file = response_dir(agent_id) / f"{project_id}_task_plan.response"

    if not req_file.exists():
        logger.error(f"[TASK_PLAN_FAIL] request file not found: {req_file}")
        return False, "请求文件不存在"

    with open(req_file, "r", encoding="utf-8") as f:
        req = json.load(f)

    expected = req.get("expected_format", {})

    # 构建消息，包含 retry_feedback（如有）
    retry_feedback = req.get("retry_feedback")
    feedback_part = ""
    if retry_feedback:
        feedback_text = "；".join(retry_feedback) if isinstance(retry_feedback, list) else str(retry_feedback)
        feedback_part = f"\n\n【上次验证失败】\n{feedback_text}\n\n请严格按照要求的 JSON 格式重新回复，不要回复其他内容。"

    message = (
        f"项目协作: 任务规划请求\n\n"
        f"项目：{req.get('project_id')}\n\n"
        f"{req.get('message')}\n\n"
        f"这是一个系统级别的 JSON 配置请求。请只输出以下，不要包含任何其他文字、markdown 代码块或解释：\n"
        f"格式：{json.dumps(expected, ensure_ascii=False, indent=2)}"
        f"{feedback_part}"
    )

    # 首次使用 auto thinking，重试时使用更多思考
    thinking_mode = "auto" if retry_feedback else "minimal"
    _notify_agent(agent_id, message, project_id=project_id, deliver=False,
                  thinking=thinking_mode, wait_response=False,
                  response_file=str(resp_file))
    logger.info(f"[TASK_PLAN_NOTIFIED] async response to: {resp_file}")
    return True, "任务规划已通知"


def notify_json_response_request(
    project_id,
    agent_id,
    stem,
    title,
    fallback=None,
):
    """读取 {project_id}_{stem}.request，通知 Agent，写 {project_id}_{stem}.response。"""
    logger = get_skill_logger(project_id)
    req_file = response_dir(agent_id) / f"{project_id}_{stem}.request"
    resp_file = response_dir(agent_id) / f"{project_id}_{stem}.response"

    if not req_file.exists():
        logger.error(f"[{title}_FAIL] request file not found: {req_file}")
        return False, "请求文件不存在"

    with open(req_file, "r", encoding="utf-8") as f:
        req = json.load(f)

    expected = req.get("expected_format", {})
    retry_feedback = req.get("retry_feedback")
    feedback_part = ""
    if retry_feedback:
        feedback_text = "；".join(retry_feedback) if isinstance(retry_feedback, list) else str(retry_feedback)
        feedback_part = (
            f"\n\n【上次验证失败】\n{feedback_text}\n\n"
            "请严格按照要求的 JSON 格式重新回复，不要回复其他内容。"
        )

    message = (
        f"项目协作: {title}\n\n"
        f"项目：{req.get('project_id', project_id)}\n\n"
        f"{req.get('message', '')}\n\n"
        f"这是一个系统级别的 JSON 配置请求。请只输出以下格式，不要包含 markdown 代码块或解释：\n"
        f"{json.dumps(expected, ensure_ascii=False, indent=2)}"
        f"{feedback_part}"
    )

    thinking_mode = "auto" if retry_feedback else "minimal"
    success, output = _notify_agent(
        agent_id, message, project_id=project_id, deliver=False, thinking=thinking_mode, wait_response=True
    )
    if not success:
        return False, output

    resp_content = output.strip()
    import re
    json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', resp_content, re.DOTALL)
    if json_match:
        resp_content = json_match.group(1).strip()

    try:
        parsed = json.loads(resp_content)
        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
            parsed = parsed[0]
    except json.JSONDecodeError:
        if fallback and not resp_content.strip():
            parsed = fallback(req)
            logger.info(f"[{title}_FALLBACK] Agent 无回复，使用默认响应")
        else:
            logger.warning(f"[{title}] Agent 返回非 JSON: {resp_content[:200]}")
            parsed = {"raw_response": resp_content}

    resp_file.parent.mkdir(parents=True, exist_ok=True)
    with open(resp_file, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    logger.info(f"[{title}_SUCCESS] response written: {resp_file}")
    return True, f"{title} 已完成"


def notify_cycle_review(project_id, agent_id, cycle_id):
    stem = f"cycle_{int(cycle_id):03d}_review"
    return notify_json_response_request(
        project_id,
        agent_id,
        stem,
        "CYCLE_REVIEW",
    )


def notify_cycle_plan(project_id, agent_id, cycle_number):
    stem = f"cycle_{int(cycle_number):03d}_plan"

    def fallback(req):
        templates = req.get("templates") or req.get("expected_format", {}).get("tasks") or []
        if templates:
            return {"tasks": templates}
        return {"tasks": []}

    return notify_json_response_request(
        project_id,
        agent_id,
        stem,
        "CYCLE_PLAN",
        fallback=fallback,
    )


def main():
    parser = argparse.ArgumentParser(description="Agent 间消息通知")
    sub = parser.add_subparsers(dest="command", required=True)

    # team_config 命令（新增）
    p_team_config = sub.add_parser("team_config", help="通知 Main Agent 配置团队")
    p_team_config.add_argument("project_id")
    p_team_config.add_argument("agent_id")

    # task_plan 命令（新增）
    p_task_plan = sub.add_parser("task_plan", help="通知 Main Agent 规划任务")
    p_task_plan.add_argument("project_id")
    p_task_plan.add_argument("agent_id")

    p_cycle_review = sub.add_parser("cycle_review", help="通知 Deputy 评审上一轮业务效果")
    p_cycle_review.add_argument("project_id")
    p_cycle_review.add_argument("cycle_id")
    p_cycle_review.add_argument("agent_id")

    p_cycle_plan = sub.add_parser("cycle_plan", help="通知 Main Agent 规划本轮 recurring 任务")
    p_cycle_plan.add_argument("project_id")
    p_cycle_plan.add_argument("cycle_number")
    p_cycle_plan.add_argument("agent_id")

    # dispatch 命令
    p_dispatch = sub.add_parser("dispatch", help="通知 Agent 有新任务")
    p_dispatch.add_argument("project_id")
    p_dispatch.add_argument("task_id")
    p_dispatch.add_argument("agent_id")
    p_dispatch.add_argument("--require-valid-graph", action="store_true",
                            help="发送前执行 project-data check-cycle；图非法则非 0 退出")

    # complete 命令
    p_complete = sub.add_parser("complete", help="通知 Main Agent 任务完成")
    p_complete.add_argument("project_id")
    p_complete.add_argument("task_id")
    p_complete.add_argument("agent_id")
    p_complete.add_argument("--require-valid-graph", action="store_true",
                            help="发送前执行 project-data check-cycle；图非法则非 0 退出")

    # evaluate 命令
    p_evaluate = sub.add_parser("evaluate", help="通知 Agent 评估任务是否需要拆分")
    p_evaluate.add_argument("project_id")
    p_evaluate.add_argument("task_id")
    p_evaluate.add_argument("agent_id")
    p_evaluate.add_argument("--ack-timeout", type=int, default=None,
                            help="ACK 超时秒数，不等待完整响应")

    # execute 命令
    p_execute = sub.add_parser("execute", help="通知 Agent 执行任务")
    p_execute.add_argument("project_id")
    p_execute.add_argument("task_id")
    p_execute.add_argument("agent_id")
    p_execute.add_argument("--parent", default=None, help="父任务 ID")
    p_execute.add_argument("--index", default=None, help="子任务进度（如 1/3）")
    p_execute.add_argument("--ack-timeout", type=int, default=None,
                            help="ACK 超时秒数，不等待完整响应")

    args = parser.parse_args()

    if args.command == "team_config":
        success, msg = notify_team_config(args.project_id, args.agent_id)
        print(msg)
        sys.exit(0 if success else 1)

    elif args.command == "task_plan":
        success, msg = notify_task_plan(args.project_id, args.agent_id)
        print(msg)
        sys.exit(0 if success else 1)

    elif args.command == "cycle_review":
        success, msg = notify_cycle_review(args.project_id, args.agent_id, args.cycle_id)
        print(msg)
        sys.exit(0 if success else 1)

    elif args.command == "cycle_plan":
        success, msg = notify_cycle_plan(args.project_id, args.agent_id, args.cycle_number)
        print(msg)
        sys.exit(0 if success else 1)

    elif args.command == "dispatch":
        success, msg = notify_task_dispatch(
            args.project_id, args.task_id, args.agent_id,
            require_valid_graph=args.require_valid_graph,
        )
        print(msg)
        if not success:
            cid = normalize_project_id(args.project_id)
            log_skill_step_failure(
                cid, "AGENT_NOTIFY", "dispatch_notify_failed",
                (msg or "")[:500], f"task={args.task_id}, agent={args.agent_id}"
            )
        sys.exit(0 if success else 1)

    elif args.command == "complete":
        success, msg = notify_task_complete(
            args.project_id, args.task_id, args.agent_id,
            require_valid_graph=args.require_valid_graph,
        )
        print(msg)
        if not success:
            cid = normalize_project_id(args.project_id)
            log_skill_step_failure(
                cid, "AGENT_NOTIFY", "complete_notify_failed",
                (msg or "")[:500], f"task={args.task_id}, agent={args.agent_id}"
            )
        sys.exit(0 if success else 1)

    elif args.command == "evaluate":
        success, msg = notify_task_evaluate(
            args.project_id, args.task_id, args.agent_id,
            ack_timeout=args.ack_timeout
        )
        print(msg)
        if not success:
            cid = normalize_project_id(args.project_id)
            log_skill_step_failure(
                cid, "AGENT_NOTIFY", "evaluate_notify_failed",
                (msg or "")[:500], f"task={args.task_id}, agent={args.agent_id}"
            )
        sys.exit(0 if success else 1)

    elif args.command == "execute":
        success, msg = notify_task_execute(
            args.project_id, args.task_id, args.agent_id,
            parent_task=args.parent, sub_task_index=args.index,
            ack_timeout=args.ack_timeout
        )
        print(msg)
        if not success:
            cid = normalize_project_id(args.project_id)
            log_skill_step_failure(
                cid, "AGENT_NOTIFY", "execute_notify_failed",
                (msg or "")[:500], f"task={args.task_id}, agent={args.agent_id}"
            )
        sys.exit(0 if success else 1)

    parser.error(f"未知命令：{args.command}")


if __name__ == '__main__':
    main()
