from fastapi import HTTPException
from app.engines.wrap_math import paper_area, ribbon_estimate
from app.repositories import boxes as boxes_repo
from app.repositories import history as history_repo
from app.repositories import orders as orders_repo
from app.repositories import settings_repo

STATUSES = ("draft", "quoted", "wrapping", "done", "cancelled")

# 服务端强制的合法迁移表；quoted→draft 是退回，退回后才允许换挂接 run。
TRANSITIONS = {
    "draft": {"quoted", "cancelled"},
    "quoted": {"wrapping", "draft", "cancelled"},
    "wrapping": {"done"},
    "done": set(),
    "cancelled": set(),
}


def _summary(row):
    """列表与详情共用的序列化，保证状态/挂接编号/固化面积两处一致。"""
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "run_id": row["run_id"],
        "paper_m2": row["paper_m2"],
        "ribbon_m": row["ribbon_m"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _run_brief(run):
    return {
        "id": run["id"],
        "box_id": run["box_id"],
        "box_name": run.get("box_name"),
        "overlap": run["overlap"],
        "created_at": run["created_at"],
    }


def _live_recalc(run):
    """现场重算：按当前盒尺寸与当前折边系数现算，仅供对照，绝不回写固化值。"""
    box = boxes_repo.get_box(run["box_id"])
    if not box or box.get("data_quality") == "dirty":
        return None
    overlap = settings_repo.get_overlap()
    style = (run["result"].get("ribbon") or {}).get("wrap_style", "cross")
    calc = paper_area(box["length"], box["width"], box["height"], overlap)
    ribbon = ribbon_estimate(box["length"], box["width"], box["height"], style)
    return {
        "overlap": overlap,
        "wrap_style": style,
        "paper_m2": calc["paper_m2"],
        "ribbon_m": ribbon["ribbon_m"],
    }


def _detail(row):
    d = _summary(row)
    d["quoted_at"] = row["quoted_at"]
    run = history_repo.get_run(row["run_id"]) if row["run_id"] else None
    d["run"] = _run_brief(run) if run else None
    d["live"] = _live_recalc(run) if run else None
    d["allowed_transitions"] = sorted(TRANSITIONS[row["status"]])
    return d


def _must_get(oid):
    row = orders_repo.get_order(oid)
    if not row:
        raise HTTPException(404, "order not found")
    return row


def list_orders():
    return {"items": [_summary(r) for r in orders_repo.list_orders()]}


def get_order(oid):
    return _detail(_must_get(oid))


def create_order(title, run_id=None):
    title = (title or "").strip() or "未命名工单"
    if run_id is not None and not history_repo.get_run(run_id):
        raise HTTPException(404, "run not found")
    oid = orders_repo.create_order(title, run_id)
    return get_order(oid)


def attach(oid, run_id):
    row = _must_get(oid)
    if row["status"] != "draft":
        raise HTTPException(409, "only draft orders can change the attached run; return to draft first")
    if not history_repo.get_run(run_id):
        raise HTTPException(404, "run not found")
    orders_repo.attach_run(oid, run_id)
    return get_order(oid)


def transition(oid, to):
    row = _must_get(oid)
    if to not in STATUSES:
        raise HTTPException(422, f"unknown status: {to}")
    current = row["status"]
    if to not in TRANSITIONS[current]:
        raise HTTPException(409, f"illegal transition: {current} -> {to}")
    if current == "draft" and to == "quoted":
        if not row["run_id"]:
            raise HTTPException(409, "cannot quote without an attached run")
        run = history_repo.get_run(row["run_id"])
        if not run:
            raise HTTPException(409, "attached run is missing")
        result = run["result"]
        ribbon = (result.get("ribbon") or {}).get("ribbon_m")
        orders_repo.set_quoted(oid, result["paper_m2"], ribbon)
    elif current == "quoted" and to == "draft":
        orders_repo.set_draft(oid)
    else:
        orders_repo.set_status(oid, to)
    return get_order(oid)
