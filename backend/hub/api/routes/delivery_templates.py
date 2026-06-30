"""Delivery templates 域路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/delivery-templates", tags=["delivery-templates"])


@router.get("")
async def api_list_delivery_templates():
    """列出交付模板（含 task_types 绑定；按 Hub 操作时间排序）。"""
    from common.delivery.delivery_template_store import list_templates_for_api

    return {"templates": list_templates_for_api()}


@router.get("/{template_id}")
async def api_get_delivery_template(template_id: str):
    from common.delivery.delivery_template_store import format_template_api, read_template_raw
    from common.delivery.delivery_templates import load_delivery_template

    import yaml

    try:
        tpl = load_delivery_template(template_id)
        raw = read_template_raw(template_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "template": format_template_api(tpl, raw),
        "yaml": yaml.dump(raw, allow_unicode=True, default_flow_style=False, sort_keys=False),
    }


@router.post("")
async def api_create_delivery_template(body: dict):
    from common.delivery.delivery_template_store import save_template, validate_template_id
    from common.delivery.delivery_templates import DeliveryTemplateError, load_delivery_template
    from common.observability.hub_operation_meta import touch

    import yaml

    tid = str(body.get("id") or body.get("template_id") or "").strip()
    if not tid and body.get("yaml"):
        parsed = yaml.safe_load(body.get("yaml") or "")
        if isinstance(parsed, dict):
            tid = str(parsed.get("id") or "").strip()
    tid = validate_template_id(tid)
    try:
        load_delivery_template(tid)
    except DeliveryTemplateError:
        pass
    else:
        raise HTTPException(status_code=409, detail=f"模板「{tid}」已存在")
    try:
        item = save_template(tid, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    touch("delivery_template", tid)
    return {"success": True, "template": item}


@router.put("/{template_id}")
async def api_update_delivery_template(template_id: str, body: dict):
    from common.delivery.delivery_template_store import read_template_raw, save_template
    from common.observability.hub_operation_meta import touch

    try:
        read_template_raw(template_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到模板「{template_id}」")
    new_id = str(body.get("id") or template_id).strip()
    try:
        item = save_template(new_id, body, update=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    touch("delivery_template", new_id)
    if new_id != template_id:
        from common.observability.hub_operation_meta import remove

        remove("delivery_template", template_id)
    return {"success": True, "template": item}


@router.delete("/{template_id}")
async def api_delete_delivery_template(template_id: str):
    from common.delivery.delivery_template_store import delete_template
    from common.observability.hub_operation_meta import remove

    try:
        delete_template(template_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    remove("delivery_template", template_id)
    return {"success": True}