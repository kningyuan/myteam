"""APIError 单元测试 — Hub API 统一错误类型。

覆盖：构造（全部字段）、可选字段默认值、to_dict() 产统一 error 信封
{error:{code,message,hint,doc_url}}、status_code 默认 400、Exception 继承。
"""

import pytest

from hub.api.errors import APIError


def test_construction_sets_all_fields():
    err = APIError(
        code="AGENT_NOT_FOUND",
        message="agent xxx not found",
        hint="check agents_config.json",
        doc_url="https://docs.example.com/errors#agent-not-found",
        status_code=404,
    )
    assert err.code == "AGENT_NOT_FOUND"
    assert err.message == "agent xxx not found"
    assert err.hint == "check agents_config.json"
    assert err.doc_url == "https://docs.example.com/errors#agent-not-found"
    assert err.status_code == 404


def test_defaults_for_optional_fields():
    err = APIError(code="BAD_REQUEST", message="nope")
    assert err.hint == ""
    assert err.doc_url == ""
    assert err.status_code == 400  # 默认 400


def test_to_dict_produces_unified_envelope():
    err = APIError(
        code="VALIDATION_FAILED",
        message="field x required",
        hint="provide x",
        doc_url="https://docs.example.com/errors#validation",
        status_code=422,
    )
    envelope = err.to_dict()

    assert set(envelope.keys()) == {"error"}
    assert envelope["error"] == {
        "code": "VALIDATION_FAILED",
        "message": "field x required",
        "hint": "provide x",
        "doc_url": "https://docs.example.com/errors#validation",
    }


def test_to_dict_with_defaults():
    err = APIError(code="E1", message="m")
    assert err.to_dict() == {
        "error": {
            "code": "E1",
            "message": "m",
            "hint": "",
            "doc_url": "",
        }
    }


def test_is_exception_subclass():
    err = APIError(code="E", message="something broke")
    assert isinstance(err, Exception)
    # message 透传到 Exception 基类
    assert str(err) == "something broke"


def test_status_code_custom():
    assert APIError("E", "m", status_code=500).status_code == 500
    assert APIError("E", "m", status_code=403).status_code == 403


def test_to_dict_envelope_has_no_status_code():
    """统一 error 信封只含 code/message/hint/doc_url，不含 status_code（status 由 HTTP 层带）。"""
    err = APIError("E", "m", status_code=418)
    assert "status_code" not in err.to_dict()["error"]


def test_can_be_raised_and_caught():
    with pytest.raises(APIError) as exc_info:
        raise APIError(code="BOOM", message="exploded", status_code=500)
    assert exc_info.value.code == "BOOM"
    assert exc_info.value.status_code == 500
