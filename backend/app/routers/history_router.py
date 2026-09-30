from fastapi import APIRouter, HTTPException
from app.repositories import history as repo
from app.repositories import orders as orders_repo

router = APIRouter()


@router.get("/runs")
def runs(limit: int = 50):
    return {"items": repo.list_runs(limit)}


@router.get("/runs/{rid}")
def run_detail(rid: int):
    run = repo.get_run(rid)
    if not run:
        raise HTTPException(404, "run not found")
    run["orders"] = orders_repo.list_orders_for_run(rid)
    return run
