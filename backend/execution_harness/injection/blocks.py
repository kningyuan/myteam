#!/usr/bin/env python3
"""prompt 注入块 — 统一标题格式。"""
from __future__ import annotations

import os

RUBRIC_SPEC_PATH = os.environ.get(
    "RUBRIC_SPEC_PATH",
    "docs/superpowers/specs/2026-06-23-agent-prd-quality-rubric.md",
)


def append_block(lines: list[str], title: str, body: str) -> None:
    text = (body or "").strip()
    if not text:
        return
    lines.append(title)
    lines.append(text)
    lines.append("")


def append_preference_block(lines: list[str], body: str) -> None:
    append_block(lines, "【用户偏好】", body)


def append_kb_top_k(lines: list[str], entries: list[dict], *, title: str = "【相关知识】") -> None:
    if not entries:
        lines.append(title)
        lines.append("- 暂无相关知识条目。")
        lines.append("")
        return
    lines.append(title)
    for e in entries:
        t = e.get("title") or "entry"
        content = (e.get("content") or "").strip().replace("\n", " ")
        if len(content) > 800:
            content = content[:799] + "…"
        lines.append(f"- {t}: {content}")
    lines.append("")


def append_rubric_block(lines: list[str], task_type: str = "") -> None:
    """【质量评分标准】注入块 — 仅产品类任务注入 rubric 片段。

    向 Agent 告知它将被按什么标准评估，让其有明确的质量目标。
    不是完整 rubric，而是精简版提示（完整版由 Gate/Rubric eval 执行）。
    """

    # 仅对产品类任务注入
    product_types = {"research", "product-research", "product-analysis", "competition", "prd"}
    if task_type and task_type not in product_types:
        return

    lines.append("【质量评分标准（重要 — 请仔细阅读）】")
    lines.append("你的交付物将被按以下维度自动评分（0/0.5/1 三档），达不到要求的会被标记为未通过：")
    lines.append("")
    lines.append("维度一（结果产出，权40%）：")
    lines.append("  ✅ 需求目标匹配 — 不擅自扩大/缩小范围，区分显性隐性需求")
    lines.append("  ✅ 交付物完整 — PRD须含：业务背景、用户角色、正常流程、异常分支、验收指标")
    lines.append("  ✅ 专业准确 — 竞品/行业数据必须有来源标注，禁止编造数据")
    lines.append("  ✅ 落地可行 — 须考虑技术/运营/现有系统限制，配套折中方案")
    lines.append("")
    lines.append("维度二（专业过程，权28%）：")
    lines.append("  ✅ 有分步拆解（调研→分析→方案→风险），标注 P0/P1/P2 优先级")
    lines.append("  ✅ 方案必须包含：①目标用户 ②核心痛点 ③解决方案 ④效果衡量指标")
    lines.append("  ✅ 每项设计附带推导依据（基于XX痛点/竞品/约束），不直接给结论")
    lines.append("")
    lines.append("维度三（效率，权12%）：")
    lines.append("  ✅ 简单任务1轮交付，复杂不超3轮，不输出无关科普")
    lines.append("")
    lines.append("维度四（鲁棒性，权10%）：")
    lines.append("  ✅ 必须覆盖异常场景（空数据/失败/无权限），不单设计正常流程")
    lines.append("")
    lines.append("维度五（合规风险，权7%）：")
    lines.append("  ✅ 涉及隐私数据采集时标注合规风险")
    lines.append("")
    lines.append("【红线 — 触发直接不及格】")
    lines.append("  🔴 编造行业数据/竞品规模且无来源标注")
    lines.append("  🔴 流程图仅用纯文字/ASCII 无结构化 DSL")
    lines.append("  🔴 仅设计正常流程，完全不覆盖异常场景")
    lines.append("  🔴 交付物缺失背景/用户/流程/验收等必备模块")
    lines.append("  🔴 连续 N 次雷同检索无新增信息")
    lines.append("")


def append_l1_block(lines: list[str], hint: str) -> None:
    append_block(lines, "【工作记忆（本 Agent）】", hint)


def _extract_sections(markdown: str, sections: list[str]) -> str:
    """从 markdown 中按 ## heading 截取指定章节正文。

    heading 匹配规则：``## 方法论`` 匹配名为"方法论"的二级标题。
    返回该 heading 到下一个同级（##）或更高级（#）heading 之间的正文。
    """
    import re as _re

    lines = markdown.splitlines()
    result: list[str] = []
    wanted = {s.strip().lower() for s in sections if s.strip()}
    in_target = False
    for line in lines:
        # 检测 heading
        m = _re.match(r"^(#{1,3})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip().lower()
            if level == 2 and title in wanted:
                in_target = True
                result.append(line)
                continue
            # 遇到同级或更高级 heading（## 或 #），结束当前目标章节
            if in_target and level <= 2:
                in_target = False
        if in_target:
            result.append(line)
    return "\n".join(result).strip()


def _extract_toc(markdown: str) -> list[str]:
    """提取 markdown 中的 ## 二级标题列表（章节目录）。"""
    import re as _re

    toc: list[str] = []
    for line in markdown.splitlines():
        m = _re.match(r"^##\s+(.+)$", line)
        if m:
            toc.append(m.group(1).strip())
    return toc


def append_umbrella_skill_block(
    lines: list[str],
    skill_id: str,
    skill_path: str,
    *,
    skill_sections: list[str] | None = None,
    max_chars: int = 800,
    store=None,
    project_id: str = "",
) -> None:
    """注入方法论 Skill（三层懒加载，节省上下文）。

    三层结构：
    - 层1（总是注入）：Skill ID + 章节目录 + 文件路径（~300字符）
    - 层2（skill_sections 配置时）：核心章节正文直接注入（~800字符）
    - 层3（其余章节）：仅路径，agent 按需 Read

    文件不存在时：记录 ``inject_failed`` run_event，降级为指针。
    """
    if not skill_id:
        return
    from pathlib import Path as _Path

    sp = _Path(skill_path)
    try:
        markdown = sp.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        if store is not None:
            try:
                store.append_run_event(
                    f"{project_id}:inject",
                    "inject_failed",
                    {"layer": "skill", "skill_id": skill_id, "error": str(e)},
                )
            except Exception:
                pass
        lines.append("【本任务方法论 Skill — 必读】")
        lines.append(f"- Skill：`{skill_id}`")
        lines.append(f"- 路径：`{skill_path}`")
        lines.append("- ⚠️ Skill 文件读取失败，请手动 Read 上述 SKILL.md。")
        lines.append("")
        return

    toc = _extract_toc(markdown)
    toc_str = "、".join(toc) if toc else "（无章节）"

    # 层1：总是注入摘要 + 目录 + 路径
    lines.append("【本任务方法论 Skill — 必读】")
    lines.append(f"- Skill：`{skill_id}`")
    lines.append(f"- 路径：`{skill_path}`")
    lines.append(f"- 章节目录：{toc_str}")

    # 层2：skill_sections 配置时注入核心章节正文
    if skill_sections:
        body = _extract_sections(markdown, skill_sections)
        if body:
            if len(body) > max_chars:
                body = body[: max_chars - 1] + "…"
            lines.append("")
            lines.append("【核心章节（直接注入）】")
            lines.append(body)
        else:
            # 指定章节不存在：记录告警
            if store is not None:
                try:
                    store.append_run_event(
                        f"{project_id}:inject",
                        "inject_failed",
                        {
                            "layer": "skill",
                            "skill_id": skill_id,
                            "error": f"指定章节 {skill_sections} 未找到",
                        },
                    )
                except Exception:
                    pass
            lines.append("- ⚠️ 指定章节未找到，请 Read上述 SKILL.md 获取完整内容。")
    else:
        lines.append("- 完整内容请按需 Read 上述 SKILL.md。")

    lines.append("")


def append_reference_pointers(lines: list[str], pointers: list[str]) -> None:
    if not pointers:
        return
    lines.append("【同类任务参考（references，按需 Read）】")
    for p in pointers:
        lines.append(f"- {p}")
    lines.append("")
