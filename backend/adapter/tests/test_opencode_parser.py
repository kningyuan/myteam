import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapter.opencode.parser import parse_line  # noqa: E402


def test_tool_use_captures_input_and_cli_output():
    """opencode 把工具返回放在同一个 tool_use 事件的 state.output，需一并捕获。"""
    line = json.dumps({
        "type": "tool_use", "sessionID": "ses_x",
        "part": {"type": "tool", "tool": "write", "state": {
            "status": "completed",
            "input": {"content": "HELLO", "filePath": "/tmp/hello.txt"},
            "output": "Wrote file successfully.",
        }},
    })
    evs = [e for e in parse_line(line) if e.kind.value == "tool_use"]
    assert len(evs) == 1
    d = evs[0].data
    assert d["name"] == "write"
    assert "hello.txt" in d["input"] and "HELLO" in d["input"]
    assert d["output"] == "Wrote file successfully."   # cli 返回被记下
    assert d["status"] == "completed"


def test_tool_use_without_output_still_parses():
    line = json.dumps({
        "type": "tool_use", "sessionID": "s",
        "part": {"type": "tool", "tool": "bash", "state": {
            "status": "running", "input": {"command": "ls"}}},
    })
    evs = [e for e in parse_line(line) if e.kind.value == "tool_use"]
    assert len(evs) == 1
    assert "output" not in evs[0].data
    assert evs[0].data["status"] == "running"


def test_error_event_parsed():
    line = json.dumps({
        "type": "error",
        "sessionID": "ses_x",
        "error": {
            "name": "APIError",
            "data": {"message": "Open WebUI: Server Connection Error", "statusCode": 400},
        },
    })
    evs = [e for e in parse_line(line) if e.kind.value == "error"]
    assert len(evs) == 1
    assert "Server Connection Error" in evs[0].data["message"]
