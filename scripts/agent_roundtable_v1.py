#!/usr/bin/env python3
"""多 Agent 圆桌讨论 — 依次调用 myteam agent，后发言者可见前文。"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("MYTEAM_ROOT", str(ROOT))

AGENDA = """
# myteam 战略圆桌（v1 稳定版 + 工作流 + Mac 产品化）

## 背景
- 目标：工业级团队协作框架，近期封板稳定，满足具体业务，短期内不再大改 Kernel。
- 目标 Mac App：用户自定义 agent / skill / workflow / CLI backend，框架必须稳定。
- 已有能力：Process + Gate + workflow loop + delivery_template + 461 tests；TDS 第三章 Work-Review 已跑通。

## 需讨论并给出可执行建议（每条不超过 5 条，要具体）

### 议题 1 — 框架 v1 稳定版应封板什么、不做什么？
- Kernel 必须冻结的 API/行为
- Strategy 层（workflow/template/skill）扩展边界
- 什么是 v2 才做的事

### 议题 2 — 四条业务工作流如何「稳定落地」？
A. **媒体持续运营**（知乎/小红书）：热点、写文、调研、引流、曝光 — agent 分工与 workflow 形态
B. **完整产品研发**：需求→架构→前后端→测试→可运行升级 — 与现有 PGD 如何对齐
C. **GEO 持续优化**：怎么做、怎么持续 — 与 seo/geo agent 关系
D. **产品经理 Skill 包**：方案/需求/设计/PPT — 与 product-planning、wps-deck 等如何组合

### 议题 3 — Mac App 产品化对框架的硬要求
- 用户可配置项应落在哪一层
- 哪些绝对不能让用户配坏（框架兜底）

请用中文，结构化输出（## 标题 + 列表），不要 JSON。
"""

ROUNDS = [
    ("product", "你是 **产品专家**。从需求、验收、PM Skill 包、Mac 产品化 UX 角度发言。先议题1再议题2D再议题3。"),
    ("arch", "你是 **架构师**。从前文产品专家观点出发，补充/质疑。重点：Kernel 封板边界、研发工作流、Mac App 架构分层。"),
    ("frontend", "你是 **前端架构师**。从前文出发，补充：Hub→Mac App、用户自定义配置的 UI/数据模型、前端研发工作流。"),
    ("geo", "你是 **GEO 专家**。从前文出发，专讲议题2C：GEO 工作流、与 content/seo 分工、持续运营机制。"),
    ("main", "你是 **项目经理**。综合以上所有人观点，输出：**v1 封板清单**、**4 条工作流优先级与 MVP 范围**、**90 天不做清单**、**需 owner 拍板的 3 个分歧**。"),
]


def collect_stream(agent_id: str, prompt: str, timeout_hint: str = "") -> tuple[bool, str]:
    from base.agent_chat import stream_chat
    from threading import Event
    import threading

    cancel = Event()
    timer = threading.Timer(600, cancel.set)
    timer.start()
    parts: list[str] = []
    err = ""
    try:
        for chunk in stream_chat(agent_id, prompt, cancel_event=cancel):
            try:
                evt = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if evt.get("event") == "error":
                err = (evt.get("data") or {}).get("message", "unknown")
            elif evt.get("event") == "thinking":
                d = evt.get("data") or {}
                if d.get("type") == "text" and d.get("content"):
                    parts.append(d["content"])
            elif evt.get("event") == "text":
                c = (evt.get("data") or {}).get("content", "")
                if c:
                    parts.append(c)
            elif evt.get("event") == "done":
                break
    finally:
        timer.cancel()

    text = "".join(parts).strip()
    if err:
        return False, err
    if not text:
        return False, "empty response"
    return True, text


def main() -> int:
    out_dir = ROOT / "business" / "tasks" / "project" / "roundtable-v1-stable" / "deliverables"
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = out_dir / "roundtable_transcript.md"

    lines = [f"# myteam Agent 圆桌记录\n\n生成时间：{datetime.now().isoformat(timespec='seconds')}\n"]
    context = AGENDA.strip()

    for agent_id, role_prompt in ROUNDS:
        print(f"\n{'='*60}\n▶ 正在调用 agent: {agent_id}\n{'='*60}", flush=True)
        prompt = (
            f"{role_prompt}\n\n"
            f"---\n\n"
            f"## 议程与此前讨论\n\n{context}\n\n"
            f"---\n\n请现在发言（仅你一人本轮输出，不要 @ 其他 agent）："
        )
        ok, reply = collect_stream(agent_id, prompt)
        block = f"\n\n---\n\n## @{agent_id}\n\n{reply if ok else f'**调用失败**: {reply}'}\n"
        lines.append(block)
        context = context + block
        transcript_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"✓ {agent_id}: {len(reply) if ok else 0} chars", flush=True)
        if not ok:
            print(f"  失败: {reply[:200]}", flush=True)

    print(f"\n完整记录: {transcript_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
