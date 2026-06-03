#!/usr/bin/env python3
"""Context Assembler (P0) — 把对话历史按预算 + 优先级组装成 prompt 上下文。

对抗注意力偏移（lost-in-the-middle）：不灌全量历史，而是分段按预算组装：
  1. 置顶事实 pins（用户/main 钉住的关键决策，永远在场）
  2. 对话摘要（更早轮次的滚动压缩）
  3. 相关历史片段（FTS 召回，与当前问题相关的旧消息）
  4. 最近对话（近窗逐字，放靠近末尾抓 recency）
输出顺序：稳定/摘要在上、最新在下；系统/身份由调用方拼在最顶。
预算用字符数近似 token（零依赖启发式）。

滚动摘要由「当前 agent 顺带生成」：summarize_fn 注入式，缺省/异常回退规则截断。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from common.store import Store


@dataclass
class AssemblerConfig:
    char_budget: int = 8000        # 总字符预算（≈ token×4 的粗略上界）
    recent_turns: int = 8          # 近窗逐字保留的消息条数
    retrieval_k: int = 4           # FTS 召回条数
    pin_reserve: int = 800         # pins 段上限
    summary_reserve: int = 1500    # 摘要段上限
    retrieval_reserve: int = 1500  # 召回段上限
    recent_floor: int = 1000       # 近窗最少保证的字符
    message_clip: int = 1200       # 单条消息渲染的截断长度
    summary_trigger: int = 8       # 近窗之外积压多少条才触发摘要


def _clip(text: str, n: int) -> str:
    text = text or ""
    return text if len(text) <= n else text[:n].rstrip() + "…"


def _label(msg: dict) -> str:
    role = msg.get("role")
    if role == "user":
        return "用户"
    if role == "tool":
        return "工具"
    return msg.get("author") or "助手"


def _render(msg: dict, clip: int) -> str:
    return f"{_label(msg)}：{_clip(msg.get('text', ''), clip)}"


def _citation(msg: dict, conversation_id: str) -> dict:
    """把一条被检索召回的历史消息转成引用条目（前端 message.parts 渲染卡片用）。"""
    return {
        "type": "citation",
        "source": "history",
        "ref": f"{conversation_id}#seq{msg['seq']}",
        "title": f"{_label(msg)} · #{msg['seq']}",
        "snippet": _clip(msg.get("text", ""), 160),
    }


def assemble_context(store: Store, conversation_id: str, query: str,
                     config: Optional[AssemblerConfig] = None) -> dict:
    """组装对话上下文，并暴露实际注入 prompt 的「检索召回」来源（引用闭环用）。

    返回 {"text": <上下文块字符串>, "citations": [<citation dict>, ...]}。
    citations 只含真正进入 prompt 的召回历史（被预算裁掉的不算），保证「引用 = 真实依据」。
    """
    cfg = config or AssemblerConfig()
    conv = store.get_conversation(conversation_id) or {}
    meta = conv.get("meta") or {}
    pins = meta.get("pins") or []
    summary = meta.get("summary") or ""

    recent = store.recent_messages(conversation_id, cfg.recent_turns)
    recent_ids = {m["id"] for m in recent}
    retrieved = [m for m in store.search_messages(
        query, conversation_id=conversation_id, limit=cfg.retrieval_k)
        if m["id"] not in recent_ids]

    blocks: list[str] = []
    citations: list[dict] = []
    used = 0

    if pins:
        body = _clip("\n".join(f"- {p}" for p in pins), cfg.pin_reserve)
        blocks.append(f"【置顶事实】\n{body}")
        used += len(body)

    if summary:
        body = _clip(summary, cfg.summary_reserve)
        blocks.append(f"【对话摘要（更早轮次）】\n{body}")
        used += len(body)

    if retrieved:
        lines, budget, cited = [], cfg.retrieval_reserve, []
        for m in retrieved:
            line = f"- [seq{m['seq']} {_label(m)}] {_clip(m.get('text', ''), 240)}"
            if budget - len(line) < 0:
                break
            lines.append(line)
            budget -= len(line)
            cited.append(m)
        if lines:
            body = "\n".join(lines)
            blocks.append(f"【相关历史片段（检索召回）】\n{body}")
            used += len(body)
            citations = [_citation(m, conversation_id) for m in cited]

    if recent:
        budget = max(cfg.recent_floor, cfg.char_budget - used)
        rendered = [_render(m, cfg.message_clip) for m in recent]
        # 预算不足则从最旧端丢弃（保 recency）
        while rendered and sum(len(x) for x in rendered) > budget and len(rendered) > 1:
            rendered.pop(0)
        blocks.append("【最近对话】\n" + "\n".join(rendered))

    return {"text": "\n\n".join(blocks), "citations": citations}


def assemble(store: Store, conversation_id: str, query: str,
             config: Optional[AssemblerConfig] = None) -> str:
    """仅取上下文文本（向后兼容旧调用）。"""
    return assemble_context(store, conversation_id, query, config)["text"]


def maybe_update_summary(store: Store, conversation_id: str, *,
                         summarize_fn: Optional[Callable[[list, str], str]] = None,
                         config: Optional[AssemblerConfig] = None) -> bool:
    """近窗之外积压超阈值时，把「未纳入摘要」的旧消息压成滚动摘要存 conversation.meta。

    summarize_fn(pending_messages, prev_summary)->str：注入式（用当前 agent 生成），
    缺省或抛错时回退规则截断。返回是否更新了摘要。
    """
    cfg = config or AssemblerConfig()
    conv = store.get_conversation(conversation_id)
    if not conv:
        return False
    meta = conv.get("meta") or {}
    through = int(meta.get("summarized_through_seq") or 0)

    recent = store.recent_messages(conversation_id, cfg.recent_turns)
    keep_from_seq = recent[0]["seq"] if recent else 0
    pending = [m for m in store.list_messages(conversation_id, after_seq=through)
               if m["seq"] < keep_from_seq]
    if len(pending) < cfg.summary_trigger:
        return False

    prev = meta.get("summary") or ""
    new_summary = None
    if summarize_fn is not None:
        try:
            new_summary = (summarize_fn(pending, prev) or "").strip()
        except Exception:
            new_summary = None
    if not new_summary:
        new_summary = _rule_summary(prev, pending, cfg)

    store.update_conversation_meta(
        conversation_id, summary=new_summary, summarized_through_seq=pending[-1]["seq"])
    return True


def _rule_summary(prev: str, pending: list[dict], cfg: AssemblerConfig) -> str:
    """回退摘要：上轮摘要 + 待摘要消息的逐条截断要点（保证 token 有界）。"""
    lines = [f"- {_label(m)}：{_clip(m.get('text', ''), 160)}" for m in pending]
    merged = ((prev + "\n") if prev else "") + "\n".join(lines)
    return _clip(merged, cfg.summary_reserve)
