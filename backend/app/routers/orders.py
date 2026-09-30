from fastapi import APIRouter
from app.schemas.order import OrderAttach, OrderCreate, OrderTransition
from app.services import order_service

router = APIRouter()


@router.get("/orders")
def list_orders():
    return order_service.list_orders()


@router.post("/orders", status_code=201)
def create_order(body: OrderCreate):
    return order_service.create_order(body.title, body.run_id)


@router.get("/orders/{oid}")
def get_order(oid: int):
    return order_service.get_order(oid)


@router.post("/orders/{oid}/attach")
def attach(oid: int, body: OrderAttach):
    return order_service.attach(oid, body.run_id)


@router.post("/orders/{oid}/transition")
def transition(oid: int, body: OrderTransition):
    return order_service.transition(oid, body.to)
