"""Job supervisor API routes (P3.1 Wave 4)."""

from __future__ import annotations

from fastapi import APIRouter

from hub.api.deps import we_store
from hub.api.errors import APIError

router = APIRouter(tags=["jobs"])


@router.get("/api/jobs")
async def api_list_jobs(status: str = ""):
    store = we_store()
    jobs = store.list_jobs(status=status)
    return {"jobs": jobs}


@router.get("/api/jobs/{job_id}")
async def api_get_job(job_id: str):
    store = we_store()
    job = store.get_job(job_id)
    if not job:
        raise APIError("JOB_NOT_FOUND", f"Job {job_id} 不存在", status_code=404)
    return job
