from fastapi import APIRouter, HTTPException
from app.repositories import history as repo
from app.repositories import work_orders as wo_repo

router = APIRouter()


def _with_refs(items):
    refs = wo_repo.references_for_runs([r["id"] for r in items])
    for r in items:
        r["work_orders"] = refs.get(r["id"], [])
    return items


@router.get("/runs")
def runs(limit: int = 50):
    return {"items": _with_refs(repo.list_runs(limit))}


@router.get("/runs/{run_id}")
def get_run(run_id: int):
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(404)
    run["work_orders"] = wo_repo.references_for_runs([run_id]).get(run_id, [])
    return run
