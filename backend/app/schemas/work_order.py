from pydantic import BaseModel


class WorkOrderCreate(BaseModel):
    run_id: int | None = None
    note: str = ""


class WorkOrderAttach(BaseModel):
    run_id: int


class WorkOrderTransition(BaseModel):
    action: str
