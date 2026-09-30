from pydantic import BaseModel


class OrderCreate(BaseModel):
    title: str = ""
    run_id: int | None = None


class OrderAttach(BaseModel):
    run_id: int


class OrderTransition(BaseModel):
    to: str
