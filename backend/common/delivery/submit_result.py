#!/usr/bin/env python3
"""submit_result — Agent 侧回传工具（D11 / D12）。

职责：Agent 完成一次 Interaction 后，用本工具按契约**本地校验**结果，
校验通过才**原子写**入 `.response` 文件；校验失败直接报错（拒绝，而非抢救）。

编排派发门：仅当 AgentPort 已注入 MYTEAM_DISPATCH_TOKEN 且存在匹配 .request 时才允许写入；
私聊/群聊交互任务不得调用本工具（框架硬拒绝）。

用法（函数）：
    from common.delivery.submit_result import submit
    submit(response_dict, response_path)

用法（CLI，供 agent 在 shell 中调用）：
    python submit_result.py --out /path/to/x.response < response.json
    python submit_result.py --out /path/to/x.response --file response.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# 允许独立运行（agent 侧）时找到 common 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.contracts import validate_response_dict  # noqa: E402

DISPATCH_TOKEN_ENV = "MYTEAM_DISPATCH_TOKEN"


class SubmitError(ValueError):
    """契约校验失败：结果被拒绝，不写回。"""


def _verify_dispatch_gate(response: dict, response_path: Path) -> None:
    """编排派发门：无有效 AgentPort 派发时拒绝写入 .response。"""
    iid = str(response.get("interaction_id") or "").strip()
    if not iid:
        raise SubmitError("结果缺少 interaction_id，拒绝写入")

    token = os.environ.get(DISPATCH_TOKEN_ENV, "").strip()
    if not token or token != iid:
        raise SubmitError(
            "无有效编排派发令牌（MYTEAM_DISPATCH_TOKEN），拒绝写入。"
            "私聊/群聊交互任务请用对话回复，勿调用 submit_result。"
        )

    resp_path = Path(response_path).resolve()
    expected_name = f"{iid}.response"
    if resp_path.name != expected_name:
        raise SubmitError(
            f"响应路径须为 .response/{expected_name}，当前为 {resp_path.name}"
        )

    trigger_parent = resp_path.parent.parent / ".trigger"
    req_path = trigger_parent / f"{iid}.request"
    if not req_path.is_file():
        raise SubmitError(f"未找到编排派发请求文件：{req_path}")


def submit(
    response: dict,
    response_path: str | os.PathLike,
    *,
    require_dispatch: bool = True,
) -> Path:
    """校验 response 契约 → 通过则原子写入 response_path。

    require_dispatch=False：框架内代采纳（deliverable_guarantee 等），跳过派发门。
    """
    if require_dispatch:
        _verify_dispatch_gate(response, Path(response_path))

    ok, _model, errors = validate_response_dict(response)
    if not ok:
        raise SubmitError("结果未通过契约校验，已拒绝：\n- " + "\n- ".join(errors))
    return _atomic_write_json(response, Path(response_path))


def _atomic_write_json(data: dict, path: Path) -> Path:
    """原子写（临时文件 + rename），避免半截写（D8/D12）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="提交并校验 Interaction 结果")
    parser.add_argument("--out", required=True, help="目标 .response 路径")
    parser.add_argument("--file", help="结果 JSON 文件（缺省读 stdin）")
    args = parser.parse_args(argv)

    raw = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[submit_result] 输入不是合法 JSON：{e}", file=sys.stderr)
        return 2

    try:
        out = submit(data, args.out, require_dispatch=True)
    except SubmitError as e:
        print(f"[submit_result] {e}", file=sys.stderr)
        return 1
    print(f"[submit_result] 已写入：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
