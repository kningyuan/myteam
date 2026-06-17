"""团队通用 rules API — business/rules/*.md。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.shared_rules import (
    list_shared_rule_files,
    read_shared_rule,
    write_shared_rule,
)

router = APIRouter(prefix="/api/rules", tags=["rules"])


class SharedRuleBody(BaseModel):
    content: str


@router.get("/shared")
async def list_shared_rules():
    files = list_shared_rule_files()
    contents = {f["filename"]: read_shared_rule(f["filename"]) or "" for f in files}
    return {"files": files, "contents": contents}


@router.get("/shared/{filename}")
async def get_shared_rule(filename: str):
    text = read_shared_rule(filename)
    if text is None:
        raise HTTPException(status_code=404, detail=f"规则文件不存在：{filename}")
    return {"filename": filename, "content": text}


@router.put("/shared/{filename}")
async def put_shared_rule(filename: str, body: SharedRuleBody):
    try:
        write_shared_rule(filename, body.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    from common.hub_operation_meta import touch

    touch("rules", "shared")
    return {"success": True, "filename": filename}
