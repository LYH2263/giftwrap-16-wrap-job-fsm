from fastapi import HTTPException
from app.repositories import history as history_repo
from app.repositories import work_orders as repo
from app.repositories.work_orders import (
    STATUS_DRAFT,
    STATUS_QUOTED,
    STATUS_WRAPPING,
    STATUS_DONE,
    STATUS_CANCELLED,
    TRANSITIONS,
)

# 对外动作 → 目标状态
ACTION_TARGET = {
    "quote": STATUS_QUOTED,
    "start": STATUS_WRAPPING,
    "complete": STATUS_DONE,
    "cancel": STATUS_CANCELLED,
    "revert": STATUS_DRAFT,
}


def _require_run(run_id):
    run = history_repo.get_run(run_id) if run_id is not None else None
    if run is None:
        raise HTTPException(422, "挂接的用纸档不存在")
    return run


def _snapshot_from_run(run):
    result = run["result"] or {}
    ribbon = result.get("ribbon") or {}
    return {
        "paper_m2": result.get("paper_m2"),
        "ribbon_m": ribbon.get("ribbon_m"),
        "wrap_style": ribbon.get("wrap_style"),
        "box_surface": result.get("box_surface"),
        "overlap": result.get("overlap"),
        "box_id": result.get("box_id") or run.get("box_id"),
        "box_name": run.get("box_name"),
    }


def _serialize(wo):
    """工单详情：固化快照为权威值；live 区仅展示挂接 run 的现场值与偏离标记。"""
    out = dict(wo)
    run = history_repo.get_run(wo["run_id"]) if wo.get("run_id") is not None else None
    out["run"] = _run_brief(run) if run else None
    if run and wo.get("paper_m2") is not None:
        snap = _snapshot_from_run(run)
        out["run"]["live_paper_m2"] = snap["paper_m2"]
        out["run"]["live_ribbon_m"] = snap["ribbon_m"]
        out["snapshot_drifted"] = (
            snap["paper_m2"] != wo.get("paper_m2")
            or snap["ribbon_m"] != wo.get("ribbon_m")
        )
    else:
        out["snapshot_drifted"] = False
    return out


def _run_brief(run):
    snap = _snapshot_from_run(run)
    return {
        "id": run["id"],
        "box_id": run.get("box_id"),
        "box_name": run.get("box_name"),
        "created_at": run.get("created_at"),
        "note": run.get("note"),
        "paper_m2": snap["paper_m2"],
        "ribbon_m": snap["ribbon_m"],
        "wrap_style": snap["wrap_style"],
    }


def list_work_orders(status=None):
    items = repo.list_work_orders(status)
    return [_serialize(w) for w in items]


def get_work_order(wo_id):
    wo = repo.get_work_order(wo_id)
    if not wo:
        raise HTTPException(404)
    return _serialize(wo)


def create_work_order(body):
    run_id = body.run_id
    if run_id is not None:
        _require_run(run_id)
    code = repo.next_code()
    wo = repo.create_work_order(run_id, code, body.note)
    return _serialize(wo)


def attach_run(wo_id, body):
    wo = repo.get_work_order(wo_id)
    if not wo:
        raise HTTPException(404)
    # quoted 之后禁止更换挂接 run，必须先退回 draft。
    if wo["status"] != STATUS_DRAFT:
        raise HTTPException(409, f"状态 {wo['status']} 下不能更换挂接用纸档，请先退回 draft")
    _require_run(body.run_id)
    return _serialize(repo.attach_run(wo_id, body.run_id))


def transition(wo_id, action):
    wo = repo.get_work_order(wo_id)
    if not wo:
        raise HTTPException(404)
    target = ACTION_TARGET.get(action)
    if target is None:
        raise HTTPException(422, f"未知动作 {action}")
    allowed = TRANSITIONS.get(wo["status"], set())
    if target not in allowed:
        # 非法跳转：失败且状态不变（此处不写库）。
        raise HTTPException(409, f"非法状态迁移：{wo['status']} → {target}")

    if action == "quote":
        if wo.get("run_id") is None:
            raise HTTPException(422, "报价前必须先挂接一条用纸档")
        run = _require_run(wo["run_id"])
        wo = repo.quote_work_order(wo_id, _snapshot_from_run(run), wo["run_id"])
    elif action == "revert":
        wo = repo.reset_to_draft(wo_id)
    else:
        wo = repo.set_status(wo_id, target)
    return _serialize(wo)
