#!/usr/bin/env python3
"""圆桌 prompt 上下文压缩 — 保留结构与要点，非粗暴截断。"""
from __future__ import annotations

import re

_SECTION_SPLIT_RE = re.compile(r"\n(?=#{1,3}\s+)")
_BULLET_RE = re.compile(r"^[\s]*[-*•]\d*[.)]?\s+(.+)$", re.MULTILINE)
_GOAL_MARKER = "## Goal"
_TURN_HEADING_RE = re.compile(
    r"^## \[(?P<label>[^\]]+)\]\s+(?P<name>.+?)\s+\(@(?P<agent_id>\w+)\)\s*$",
    re.MULTILINE,
)

# 优先保留的章节（对齐/立论关键信息）
_PRIORITY_SECTION_MARKERS = (
    "不同看法",
    "我不能接受的点",
    "分歧",
    "待对齐的差异",
    "不能理解",
    "理解分歧",
    "对齐回应",
    "交叉验证",
    "最佳实践",
    "问题界定",
    "反模式",
    "不能接受",
    "反对",
    "底线",
    "建议",
    "workflow",
    "Workflow",
    "共识",
    "观点",
    "立论",
    "对齐",
    "待用户",
    "保守方案",
)

# 英文工具独白（thinking 阶段常见），压缩为简短标注
_TOOL_NARRATION_RE = re.compile(
    r"^(?:Let me|Now let me|I'll |I will |I need to ).*$",
    re.MULTILINE | re.IGNORECASE,
)


def _first_paragraph(text: str, max_len: int) -> str:
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if block and not block.startswith("#"):
            one = " ".join(block.split())
            if len(one) > max_len:
                return one[: max_len - 1] + "…"
            return one
    compact = " ".join(text.split())
    if len(compact) > max_len:
        return compact[: max_len - 1] + "…"
    return compact


def extract_key_bullets(
    text: str,
    *,
    max_points: int = 8,
    max_line_len: int = 200,
    min_line_len: int = 8,
) -> list[str]:
    points: list[str] = []
    seen: set[str] = set()
    for m in _BULLET_RE.finditer(text):
        line = " ".join(m.group(1).split())
        if len(line) < min_line_len or line in seen:
            continue
        seen.add(line)
        if len(line) > max_line_len:
            line = line[: max_line_len - 1] + "…"
        points.append(line)
        if len(points) >= max_points:
            break
    return points


def _compress_tool_narration(text: str) -> str:
    """将连续英文工具过程句折叠为一行标注，保留后续中文正文。"""
    if not _TOOL_NARRATION_RE.search(text):
        return text
    lines = text.splitlines()
    narration = 0
    kept: list[str] = []
    for line in lines:
        if _TOOL_NARRATION_RE.match(line.strip()):
            narration += 1
            continue
        kept.append(line)
    if narration > 0:
        kept.insert(0, f"（已进行 {narration} 步调研/阅读，过程略）")
    return "\n".join(kept).strip()


def compress_goal_section(goal_text: str, *, max_chars: int = 320) -> str:
    """提取 Goal 块要点，不丢弃语义。"""
    body = goal_text.strip()
    if not body:
        return ""
    if len(body) <= max_chars:
        return body
    bullets = extract_key_bullets(body, max_points=5)
    if bullets:
        summary = "；".join(bullets)
    else:
        summary = _first_paragraph(body, max_chars)
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1] + "…"
    return summary


def compress_message_for_prompt(text: str, *, max_chars: int = 1200) -> str:
    """单条群消息/发言压缩：保留章节标题与要点列表。"""
    raw = (text or "").strip()
    if not raw:
        return ""
    if len(raw) <= max_chars:
        return raw

    main, goal_summary = raw, ""
    if _GOAL_MARKER in raw:
        main_part, goal_part = raw.split(_GOAL_MARKER, 1)
        main = main_part.strip()
        goal_summary = compress_goal_section(goal_part)
        goal_budget = min(360, max(120, max_chars // 4))
        if goal_summary:
            goal_summary = goal_summary[:goal_budget]
        main_budget = max_chars - len(goal_summary) - len("[项目目标摘要] ") - 4
    else:
        main_budget = max_chars

    main = _compress_tool_narration(main)
    compressed_main = compress_markdown_text(main, max_chars=max(main_budget, 400))
    if goal_summary:
        return f"{compressed_main}\n[项目目标摘要] {goal_summary}"
    return compressed_main


def compress_markdown_text(text: str, *, max_chars: int) -> str:
    """结构化压缩 Markdown：每节保留标题 + 要点/首段。"""
    body = (text or "").strip()
    if not body:
        return ""
    if len(body) <= max_chars:
        return body

    sections = _SECTION_SPLIT_RE.split(body)
    if len(sections) <= 1:
        bullets = extract_key_bullets(body, max_points=10)
        head_len = max(200, max_chars // 2)
        head = body[:head_len].rstrip()
        if bullets:
            tail = "\n…[要点]\n" + "\n".join(f"- {b}" for b in bullets)
        else:
            tail = "\n…[摘要] " + _first_paragraph(body[head_len:], max(120, max_chars - head_len - 20))
        out = (head + tail).strip()
        return out[:max_chars] if len(out) > max_chars else out

    per_section = max(180, max_chars // max(len(sections), 1))
    parts: list[str] = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.splitlines()
        title = lines[0].strip()
        bullets = extract_key_bullets(sec, max_points=5)
        if bullets:
            body_part = "\n".join(f"- {b}" for b in bullets)
        else:
            rest = "\n".join(lines[1:]).strip()
            body_part = _first_paragraph(rest, per_section - len(title) - 2)
        chunk = f"{title}\n{body_part}".strip()
        if len(chunk) > per_section:
            chunk = chunk[: per_section - 12] + "\n…[节内压缩]"
        parts.append(chunk)

    out = "\n\n".join(parts)
    if len(out) > max_chars:
        out = out[: max_chars - 16] + "\n…[全文已压缩]"
    return out


def extract_turn_digest(text: str, *, max_chars: int = 480) -> str:
    """单轮发言 → 要点 digest，供下一 Agent 引用，不传递全文。"""
    body = (text or "").strip()
    if not body:
        return "（空）"
    if len(body) <= min(max_chars, 280):
        return body

    sections = _SECTION_SPLIT_RE.split(body)
    if len(sections) <= 1:
        bullets = extract_key_bullets(body, max_points=6, min_line_len=4)
        if bullets:
            title = body.splitlines()[0].strip() if body.lstrip().startswith("#") else ""
            if title:
                out = f"{title}\n" + "\n".join(f"- {b}" for b in bullets)
            else:
                out = "\n".join(f"- {b}" for b in bullets)
        else:
            out = compress_markdown_text(body, max_chars=max_chars)
        suffix = " …[要点摘要]" if len(body) > len(out) + 40 else ""
        combined = (out + suffix).strip()
        return combined[:max_chars]

    priority_parts: list[str] = []
    other_parts: list[str] = []

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.splitlines()
        title = lines[0].strip()
        is_priority = any(m in title for m in _PRIORITY_SECTION_MARKERS)
        bullets = extract_key_bullets(sec, max_points=4 if is_priority else 3, min_line_len=4)
        if bullets:
            chunk = f"{title}\n" + "\n".join(f"- {b}" for b in bullets)
        else:
            rest = "\n".join(lines[1:]).strip()
            chunk = f"{title}\n{_first_paragraph(rest, 220)}"
        chunk = chunk.strip()
        if is_priority:
            priority_parts.append(chunk)
        else:
            other_parts.append(chunk)

    parts: list[str] = []
    budget_left = max_chars
    for chunk in priority_parts + other_parts:
        if budget_left < 60:
            break
        if len(chunk) > budget_left:
            chunk = chunk[: budget_left - 1] + "…"
        parts.append(chunk)
        budget_left -= len(chunk) + 2

    if not parts:
        bullets = extract_key_bullets(body, max_points=6)
        out = "\n".join(f"- {b}" for b in bullets) if bullets else _first_paragraph(body, max_chars)
        return out[:max_chars]

    out = "\n\n".join(parts).strip()
    if len(body) > len(out) + 80:
        note = "…[要点摘要，全文见 transcript 文件]"
        if len(out) + len(note) + 1 <= max_chars:
            out = f"{out}\n{note}"
    return out[:max_chars]


def _split_transcript_turns(text: str) -> list[tuple[str, str]]:
    """拆分为 (header_line, body) 列表。"""
    raw = (text or "").strip()
    if not raw:
        return []
    chunks = re.split(r"(?=\n## \[)", raw)
    turns: list[tuple[str, str]] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        if lines and lines[0].startswith("## ["):
            turns.append((lines[0].strip(), "\n".join(lines[1:]).strip()))
        else:
            turns.append(("## [前文]", chunk))
    return turns


def summarize_transcript_for_prompt(
    raw: str,
    *,
    max_chars: int = 12000,
    per_turn_max: int = 450,
) -> str:
    """将 transcript 各轮全文转为要点 digest，避免下一 Agent 加载上一 Agent 全文。"""
    text = (raw or "").strip()
    if not text:
        return "（暂无）"

    turns = _split_transcript_turns(text)
    if not turns:
        return compress_markdown_text(text, max_chars=max_chars)

    n = len(turns)
    recent_n = max(2, min(n, int(n * 0.4) + 1))
    digests: list[str] = []

    for i, (header, body) in enumerate(turns):
        is_recent = i >= n - recent_n
        turn_budget = int(per_turn_max * 1.35) if is_recent else per_turn_max
        digests.append(f"{header}\n{extract_turn_digest(body, max_chars=turn_budget)}")

    out = "\n\n".join(digests)
    if len(out) <= max_chars:
        return out

    while len(out) > max_chars and len(digests) > recent_n:
        digests.pop(0)
        out = "…[较早发言要点已折叠]\n\n" + "\n\n".join(digests)
    if len(out) > max_chars:
        out = "…[前文要点已截断]\n" + out[-max_chars:]
    return out.strip()


def digest_for_prompt(text: str, *, max_chars: int = 900) -> str:
    """主持汇总 / 独立思考等单块文本的 prompt 用 digest。"""
    body = (text or "").strip()
    if not body:
        return "（暂无）"
    if len(body) <= max_chars:
        return body
    return extract_turn_digest(body, max_chars=max_chars)


def extract_conflict_digest_from_transcript(raw: str, *, max_chars: int = 3200) -> str:
    """从 transcript 提取各轮「我不能接受的点」等冲突摘要，供对齐轮使用。"""
    turns = _split_transcript_turns(raw)
    if not turns:
        return "（暂无未解冲突摘要）"

    parts: list[str] = []
    for header, body in turns:
        if not body:
            continue
        conflict_chunks: list[str] = []
        for sec in _SECTION_SPLIT_RE.split(body):
            sec = sec.strip()
            if not sec:
                continue
            title = sec.splitlines()[0].strip() if sec.splitlines() else ""
            if not any(m in title for m in (
                "不同看法", "我不能接受的点", "不能接受", "分歧", "反对", "底线",
                "待对齐的差异", "对齐回应", "理解分歧", "交叉验证", "最佳实践",
            )):
                continue
            chunk = extract_turn_digest(sec, max_chars=480)
            if chunk and chunk != "（空）":
                conflict_chunks.append(chunk)
        if conflict_chunks:
            parts.append(f"{header}\n" + "\n".join(conflict_chunks))

    if not parts:
        return "（立论轮未标注明确冲突；请主要依据主持人「## 分歧点」回应）"

    out = "\n\n".join(parts)
    if len(out) > max_chars:
        out = out[: max_chars - 1] + "…"
    return out


def compress_group_context_text(
    context: str,
    *,
    total_budget: int = 14000,
    per_message_budget: int = 1200,
) -> str:
    """压缩 format_group_context 输出：近期消息保留更多预算。"""
    lines = [ln for ln in (context or "").splitlines() if ln.strip()]
    if not lines:
        return context or "（暂无群聊历史）"
    joined = "\n".join(lines)
    if len(joined) <= total_budget:
        return joined

    # 近期 40% 行给更高预算，远期更低
    n = len(lines)
    recent_cut = max(1, int(n * 0.4))
    recent_lines = lines[-recent_cut:]
    older_lines = lines[:-recent_cut]

    recent_budget = int(total_budget * 0.65)
    older_budget = total_budget - recent_budget

    def _compress_lines(items: list[str], budget: int) -> list[str]:
        if not items:
            return []
        each = max(280, budget // max(len(items), 1))
        out: list[str] = []
        for ln in items:
            if ": " not in ln:
                out.append(ln[:each])
                continue
            prefix, _, body = ln.partition(": ")
            compressed = compress_message_for_prompt(body, max_chars=min(each, per_message_budget))
            out.append(f"{prefix}: {compressed}")
        return out

    compressed = _compress_lines(older_lines, older_budget) + _compress_lines(
        recent_lines, recent_budget,
    )
    result = "\n".join(compressed)
    if len(result) > total_budget:
        result = result[-total_budget:]
        result = "…[较早上下文已折叠]\n" + result
    return result


def compress_transcript_prior(prior: str, *, max_chars: int = 12000) -> str:
    """压缩圆桌 transcript 前文：各轮仅保留要点 digest，不传全文。"""
    text = (prior or "").strip()
    if not text:
        return text
    return summarize_transcript_for_prompt(text, max_chars=max_chars)
