"""Claude stream-json parser — assistant.usage 与 step_finish 计量。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.claude.parser import parse_line  # noqa: E402
from common.agent_port import _apply_step_finish_tokens, _extract_tokens  # noqa: E402


def _step_finishes(line: str):
    return [e for e in parse_line(line) if e.kind.value == "step_finish"]


def test_assistant_usage_emits_incremental_step_finish():
    line = json.dumps({
        "type": "assistant",
        "message": {
            "content": [{"type": "text", "text": "hi"}],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        },
    })
    evs = _step_finishes(line)
    assert len(evs) == 1
    assert evs[0].data["cumulative"] is False
    assert evs[0].data["tokens"]["input"] == 100
    assert evs[0].data["tokens"]["output"] == 20


def test_result_emits_cumulative_step_finish():
    line = json.dumps({
        "type": "result",
        "subtype": "success",
        "usage": {"input_tokens": 500, "output_tokens": 80, "total_tokens": 580},
    })
    evs = _step_finishes(line)
    assert len(evs) == 1
    assert evs[0].data["cumulative"] is True
    assert evs[0].data["tokens"]["total"] == 580


def test_incremental_token_accumulation_formula_b():
    """Σ input + Σ output across per-message step_finish events."""
    acc = {"running": 0}
    lines = [
        json.dumps({
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "a"}],
                "usage": {"input_tokens": 100, "output_tokens": 10},
            },
        }),
        json.dumps({
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "b"}],
                "usage": {"input_tokens": 200, "output_tokens": 15},
            },
        }),
    ]
    for line in lines:
        for ev in _step_finishes(line):
            _apply_step_finish_tokens(ev.data, acc)
    assert acc["running"] == 100 + 10 + 200 + 15


def test_result_emits_text_when_final_answer_only_on_result_line():
    line = json.dumps({
        "type": "result",
        "subtype": "success",
        "result": "这是最终答复",
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    })
    kinds = [e.kind.value for e in parse_line(line)]
    texts = [e for e in parse_line(line) if e.kind.value == "text"]
    assert "text" in kinds
    assert texts[0].data["content"] == "这是最终答复"
    assert texts[0].data.get("source") == "result"


def test_result_without_total_tokens_uses_input_plus_output():
    """真实 Claude result 行可能无 total_tokens，parser 与 _extract_tokens 均应回退。"""
    line = json.dumps({
        "type": "result",
        "subtype": "success",
        "usage": {"input_tokens": 500, "output_tokens": 80},
    })
    evs = _step_finishes(line)
    assert evs[0].data["tokens"]["total"] == 580
    assert _extract_tokens(evs[0].data) == 580


def test_cumulative_max_wins_over_incremental():
    acc = {"running": 0}
    _apply_step_finish_tokens({
        "cumulative": False,
        "tokens": {"input": 50, "output": 5, "total": 55},
    }, acc)
    _apply_step_finish_tokens({
        "cumulative": True,
        "tokens": {"total": 580},
    }, acc)
    assert acc["running"] == 580
