"""Phase 4 Configuration API — KB Templates, task_type_skills, preference sections,
workflow profiles, and agent_task_type_rules.

All endpoints are organized into sub-routers and aggregated into a single
config_api router for clean inclusion in server.py.
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException

from common.paths import MYTEAM_ROOT

# ──────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────

_KB_TEMPLATES_FILE = MYTEAM_ROOT / "business" / "templates" / "knowledge_templates.yaml"
_PREFERENCE_SECTIONS_FILE = MYTEAM_ROOT / "config" / "preference_sections.json"
_WORKFLOW_PROFILES_DIR = MYTEAM_ROOT / "business" / "workflows"
_AGENT_TASK_TYPE_RULES_FILE = MYTEAM_ROOT / "business" / "templates" / "agent_task_type_rules.yaml"

_TASK_TYPE_ID_RE = re.compile(r"^[\w][\w-]*$", re.UNICODE)


def _validate_id(raw: str) -> str:
    tid = (raw or "").strip()
    if not tid:
        raise ValueError("ID cannot be empty")
    if not _TASK_TYPE_ID_RE.match(tid):
        raise ValueError(f"ID format invalid: {tid}")
    return tid


# ──────────────────────────────────────────────────────────────────
# 1. KB Templates — CRUD over knowledge_templates.yaml
# ──────────────────────────────────────────────────────────────────

kb_router = APIRouter(prefix="/api/knowledge/templates", tags=["kb-templates"])


def _load_kb() -> dict:
    if not _KB_TEMPLATES_FILE.exists():
        return {"version": "1.0", "templates": {}}
    try:
        import yaml
    except ImportError:
        return {"version": "1.0", "templates": {}}
    text = _KB_TEMPLATES_FILE.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {"version": "1.0", "templates": {}}


def _save_kb(data: dict) -> None:
    _KB_TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except ImportError:
        raise HTTPException(status_code=500, detail="YAML library unavailable")
    with open(_KB_TEMPLATES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


@kb_router.get("/")
def list_kb_templates():
    """List all KB templates."""
    data = _load_kb()
    templates = data.get("templates") or {}
    result = {}
    for tid, val in templates.items():
        if isinstance(val, dict):
            result[tid] = val
        else:
            result[tid] = {"content": str(val)}
    return {"templates": result, "count": len(result)}


@kb_router.get("/{template_id}")
def get_kb_template(template_id: str):
    """Get a specific KB template."""
    data = _load_kb()
    templates = data.get("templates") or {}
    if template_id not in templates:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    val = templates[template_id]
    if isinstance(val, dict):
        content = val
    else:
        content = {"content": str(val)}
    return {"id": template_id, **content}


@kb_router.post("/")
def create_kb_template(body: dict):
    """Create a new KB template."""
    tid = (body.get("id") or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail="Template ID cannot be empty")
    if "." in tid or "/" in tid:
        raise HTTPException(status_code=400, detail="Template ID cannot contain . or /")

    data = _load_kb()
    templates = data.get("templates") or {}
    if tid in templates:
        raise HTTPException(status_code=409, detail=f"Template already exists: {tid}")

    content = body.get("content", {})
    if not isinstance(content, dict):
        content = {"content": str(content)}
    templates[tid] = content
    data["templates"] = templates
    _save_kb(data)
    return {"success": True, "id": tid}


@kb_router.put("/{template_id}")
def update_kb_template(template_id: str, body: dict):
    """Update an existing KB template."""
    data = _load_kb()
    templates = data.get("templates") or {}
    if template_id not in templates:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")

    content = body.get("content")
    if content is not None:
        if not isinstance(content, dict):
            content = {"content": str(content)}
        templates[template_id] = content
        data["templates"] = templates
        _save_kb(data)
    return {"success": True, "id": template_id}


@kb_router.delete("/{template_id}")
def delete_kb_template(template_id: str):
    """Delete a KB template."""
    data = _load_kb()
    templates = data.get("templates") or {}
    if template_id not in templates:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    del templates[template_id]
    data["templates"] = templates
    _save_kb(data)
    return {"success": True, "id": template_id}


# ──────────────────────────────────────────────────────────────────
# 2. task_type_skills mapping — CRUD over business/config/task_type_skills.json
# ──────────────────────────────────────────────────────────────────

tt_skills_router = APIRouter(prefix="/api/task-types", tags=["task-type-skills"])


@tt_skills_router.get("/{task_type}/skills")
def get_task_type_skills(task_type: str):
    """Get skill mappings for a task type."""
    tid = _validate_id(task_type)
    skills_file = MYTEAM_ROOT / "business" / "config" / "task_type_skills.json"
    if not skills_file.exists():
        return {"task_type": tid, "skills": []}
    try:
        data = json.loads(skills_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"task_type": tid, "skills": []}
    mapping = data.get("mapping") or {}
    skills = mapping.get(tid, [])
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    return {"task_type": tid, "skills": skills}


@tt_skills_router.put("/{task_type}/skills")
def put_task_type_skills(task_type: str, body: dict):
    """Set (overwrite) skill mappings for a task type."""
    tid = _validate_id(task_type)
    skills = body.get("skills", [])
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.replace("，", ",").split(",") if s.strip()]
    skills = [str(s).strip() for s in skills if s]

    skills_file = MYTEAM_ROOT / "business" / "config" / "task_type_skills.json"
    skills_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(skills_file.read_text(encoding="utf-8")) if skills_file.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    mapping = data.get("mapping") or {}
    mapping[tid] = skills
    data["mapping"] = mapping
    with open(skills_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"success": True, "task_type": tid, "skills": skills}


@tt_skills_router.put("/{task_type}/skills/add")
def add_task_type_skill(task_type: str, body: dict):
    """Add a single skill to a task type mapping."""
    tid = _validate_id(task_type)
    skill_id = (body.get("skill_id") or "").strip()
    if not skill_id:
        raise HTTPException(status_code=400, detail="skill_id cannot be empty")

    skills_file = MYTEAM_ROOT / "business" / "config" / "task_type_skills.json"
    skills_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(skills_file.read_text(encoding="utf-8")) if skills_file.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    mapping = data.get("mapping") or {}
    current = mapping.get(tid, [])
    if isinstance(current, str):
        current = [s.strip() for s in current.split(",") if s.strip()]
    if skill_id not in current:
        current.append(skill_id)
    mapping[tid] = current
    data["mapping"] = mapping
    with open(skills_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"success": True, "task_type": tid, "skills": current}


@tt_skills_router.put("/{task_type}/skills/remove")
def remove_task_type_skill(task_type: str, body: dict):
    """Remove a single skill from a task type mapping."""
    tid = _validate_id(task_type)
    skill_id = (body.get("skill_id") or "").strip()
    if not skill_id:
        raise HTTPException(status_code=400, detail="skill_id cannot be empty")

    skills_file = MYTEAM_ROOT / "business" / "config" / "task_type_skills.json"
    try:
        data = json.loads(skills_file.read_text(encoding="utf-8")) if skills_file.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    mapping = data.get("mapping") or {}
    current = mapping.get(tid, [])
    if isinstance(current, str):
        current = [s.strip() for s in current.split(",") if s.strip()]
    if skill_id in current:
        current.remove(skill_id)
    mapping[tid] = current
    data["mapping"] = mapping
    with open(skills_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"success": True, "task_type": tid, "skills": current}


# ──────────────────────────────────────────────────────────────────
# 3. Preference sections management — CRUD over preference_sections.json
# ──────────────────────────────────────────────────────────────────

pref_router = APIRouter(prefix="/api/preferences", tags=["preference-sections"])


@pref_router.get("/sections")
def list_preference_sections():
    """List all preference sections."""
    if not _PREFERENCE_SECTIONS_FILE.exists():
        return {"sections": [], "count": 0}
    try:
        data = json.loads(_PREFERENCE_SECTIONS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"sections": [], "count": 0}
    sections = data.get("sections") or []
    if isinstance(sections, dict):
        sections = [{"id": k, **v} if isinstance(v, dict) else {"id": k, "content": str(v)}
                     for k, v in sections.items()]
    return {"sections": sections, "count": len(sections)}


@pref_router.put("/sections")
def put_preference_sections(body: dict):
    """Overwrite all preference sections."""
    sections = body.get("sections", [])
    if not isinstance(sections, list):
        raise HTTPException(status_code=400, detail="sections must be a list")

    _PREFERENCE_SECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"sections": sections}
    with open(_PREFERENCE_SECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"success": True, "sections": sections, "count": len(sections)}


@pref_router.post("/sections")
def create_preference_section(body: dict):
    """Add a new preference section."""
    sid = (body.get("id") or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="Section ID cannot be empty")

    if not _PREFERENCE_SECTIONS_FILE.exists():
        data = {"sections": []}
    else:
        try:
            data = json.loads(_PREFERENCE_SECTIONS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"sections": []}

    sections = data.get("sections") or []
    if isinstance(sections, dict):
        if sid in sections:
            raise HTTPException(status_code=409, detail=f"Section already exists: {sid}")
        sections = [{"id": k, **v} if isinstance(v, dict) else {"id": k, "content": str(v)}
                     for k, v in sections.items()]
    else:
        ids = {s.get("id") for s in sections if isinstance(s, dict)}
        if sid in ids:
            raise HTTPException(status_code=409, detail=f"Section already exists: {sid}")

    section = {"id": sid}
    for key in ("name", "description", "content", "order", "visible"):
        if key in body:
            section[key] = body[key]
    sections.append(section)
    data["sections"] = sections
    with open(_PREFERENCE_SECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"success": True, "section": section}


@pref_router.put("/sections/{section_id}")
def update_preference_section(section_id: str, body: dict):
    """Update an existing preference section."""
    sid = _validate_id(section_id)
    if not _PREFERENCE_SECTIONS_FILE.exists():
        raise HTTPException(status_code=404, detail=f"Section not found: {sid}")

    try:
        data = json.loads(_PREFERENCE_SECTIONS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise HTTPException(status_code=404, detail=f"Section not found: {sid}")

    sections = data.get("sections") or []
    if isinstance(sections, dict):
        if sid not in sections:
            raise HTTPException(status_code=404, detail=f"Section not found: {sid}")
        for key in ("name", "description", "content", "order", "visible"):
            if key in body:
                sections[sid][key] = body[key]
        data["sections"] = sections
    else:
        found = None
        for s in sections:
            if isinstance(s, dict) and s.get("id") == sid:
                found = s
                break
        if found is None:
            raise HTTPException(status_code=404, detail=f"Section not found: {sid}")
        for key in ("name", "description", "content", "order", "visible"):
            if key in body:
                found[key] = body[key]
        data["sections"] = sections

    with open(_PREFERENCE_SECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"success": True, "section": found}


@pref_router.delete("/sections/{section_id}")
def delete_preference_section(section_id: str):
    """Delete a preference section."""
    sid = _validate_id(section_id)
    if not _PREFERENCE_SECTIONS_FILE.exists():
        raise HTTPException(status_code=404, detail=f"Section not found: {sid}")

    try:
        data = json.loads(_PREFERENCE_SECTIONS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise HTTPException(status_code=404, detail=f"Section not found: {sid}")

    sections = data.get("sections") or []
    if isinstance(sections, dict):
        if sid not in sections:
            raise HTTPException(status_code=404, detail=f"Section not found: {sid}")
        del sections[sid]
        data["sections"] = sections
    else:
        new_sections = [s for s in sections if not (isinstance(s, dict) and s.get("id") == sid)]
        if len(new_sections) == len(sections):
            raise HTTPException(status_code=404, detail=f"Section not found: {sid}")
        data["sections"] = new_sections

    with open(_PREFERENCE_SECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"success": True, "id": sid}


# ──────────────────────────────────────────────────────────────────
# 4. Workflow Profiles — CRUD over business/workflows/<id>/profile.json
# ──────────────────────────────────────────────────────────────────

wf_router = APIRouter(prefix="/api/workflows", tags=["workflow-profiles"])


@wf_router.get("/{workflow_id}/profile")
def get_workflow_profile(workflow_id: str):
    """Get profile for a workflow."""
    wid = _validate_id(workflow_id)
    profile_file = _WORKFLOW_PROFILES_DIR / wid / "profile.json"
    if not profile_file.exists():
        raise HTTPException(status_code=404, detail=f"Profile not found: {wid}")
    try:
        data = json.loads(profile_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise HTTPException(status_code=500, detail="Failed to read profile")
    return {"workflow_id": wid, **data}


@wf_router.put("/{workflow_id}/profile")
def put_workflow_profile(workflow_id: str, body: dict):
    """Create or overwrite workflow profile."""
    wid = _validate_id(workflow_id)
    profile_dir = _WORKFLOW_PROFILES_DIR / wid
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_file = profile_dir / "profile.json"
    with open(profile_file, "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2, ensure_ascii=False)
    return {"success": True, "workflow_id": wid}


@wf_router.patch("/{workflow_id}/profile")
def patch_workflow_profile(workflow_id: str, body: dict):
    """Merge fields into an existing workflow profile."""
    wid = _validate_id(workflow_id)
    profile_file = _WORKFLOW_PROFILES_DIR / wid / "profile.json"
    if not profile_file.exists():
        raise HTTPException(status_code=404, detail=f"Profile not found: {wid}")
    try:
        data = json.loads(profile_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    if isinstance(body, dict):
        data.update(body)
    with open(profile_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"success": True, "workflow_id": wid, "profile": data}


# ──────────────────────────────────────────────────────────────────
# 5. agent_task_type_rules — CRUD over agent_task_type_rules.yaml
# ──────────────────────────────────────────────────────────────────

rules_router = APIRouter(prefix="/api/task-types/rules", tags=["agent-task-type-rules"])


def _load_rules() -> dict:
    if not _AGENT_TASK_TYPE_RULES_FILE.exists():
        return {"version": "1.0", "rules": {}}
    try:
        import yaml
    except ImportError:
        return {"version": "1.0", "rules": {}}
    text = _AGENT_TASK_TYPE_RULES_FILE.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {"version": "1.0", "rules": {}}


def _save_rules(data: dict) -> None:
    _AGENT_TASK_TYPE_RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except ImportError:
        raise HTTPException(status_code=500, detail="YAML library unavailable")
    with open(_AGENT_TASK_TYPE_RULES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


@rules_router.get("/")
def list_rules():
    """List all agent task type rules."""
    data = _load_rules()
    rules = data.get("rules") or {}
    result = {}
    for rid, val in rules.items():
        if isinstance(val, dict):
            result[rid] = val
        else:
            result[rid] = {"content": str(val)}
    return {"rules": result, "count": len(result)}


@rules_router.get("/{rule_id}")
def get_rule(rule_id: str):
    """Get a specific agent task type rule."""
    data = _load_rules()
    rules = data.get("rules") or {}
    if rule_id not in rules:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")
    val = rules[rule_id]
    if isinstance(val, dict):
        content = val
    else:
        content = {"content": str(val)}
    return {"id": rule_id, **content}


@rules_router.post("/")
def create_rule(body: dict):
    """Create a new agent task type rule."""
    rid = (body.get("id") or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="Rule ID cannot be empty")
    if "." in rid or "/" in rid:
        raise HTTPException(status_code=400, detail="Rule ID cannot contain . or /")

    data = _load_rules()
    rules = data.get("rules") or {}
    if rid in rules:
        raise HTTPException(status_code=409, detail=f"Rule already exists: {rid}")

    content = body.get("content", {})
    if not isinstance(content, dict):
        content = {"content": str(content)}
    rules[rid] = content
    data["rules"] = rules
    _save_rules(data)
    return {"success": True, "id": rid}


@rules_router.put("/{rule_id}")
def update_rule(rule_id: str, body: dict):
    """Update an existing agent task type rule."""
    data = _load_rules()
    rules = data.get("rules") or {}
    if rule_id not in rules:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")

    content = body.get("content")
    if content is not None:
        if not isinstance(content, dict):
            content = {"content": str(content)}
        rules[rule_id] = content
        data["rules"] = rules
        _save_rules(data)
    return {"success": True, "id": rule_id}


@rules_router.delete("/{rule_id}")
def delete_rule(rule_id: str):
    """Delete an agent task type rule."""
    data = _load_rules()
    rules = data.get("rules") or {}
    if rule_id not in rules:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")
    del rules[rule_id]
    data["rules"] = rules
    _save_rules(data)
    return {"success": True, "id": rule_id}


# ──────────────────────────────────────────────────────────────────
# Aggregate all sub-routers into one
# ──────────────────────────────────────────────────────────────────

router = APIRouter()
router.include_router(kb_router)
router.include_router(tt_skills_router)
router.include_router(pref_router)
router.include_router(wf_router)
router.include_router(rules_router)
