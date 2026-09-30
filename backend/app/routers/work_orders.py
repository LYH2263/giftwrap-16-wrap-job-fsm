from fastapi import APIRouter, Query
from app.schemas.work_order import WorkOrderAttach, WorkOrderCreate, WorkOrderTransition
from app.services import work_order_service as svc

router = APIRouter()


@router.get("/work-orders")
def list_work_orders(status: str | None = Query(default=None)):
    return {"items": svc.list_work_orders(status)}


@router.post("/work-orders")
def create_work_order(body: WorkOrderCreate):
    return svc.create_work_order(body)


@router.get("/work-orders/{wo_id}")
def get_work_order(wo_id: int):
    return svc.get_work_order(wo_id)


@router.put("/work-orders/{wo_id}/run")
def attach_run(wo_id: int, body: WorkOrderAttach):
    return svc.attach_run(wo_id, body)


@router.post("/work-orders/{wo_id}/transition")
def transition(wo_id: int, body: WorkOrderTransition):
    return svc.transition(wo_id, body.action)
