from datetime import datetime, timezone
from app.db import connect

STATUS_DRAFT = "draft"
STATUS_QUOTED = "quoted"
STATUS_WRAPPING = "wrapping"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"

# 服务端唯一合法的状态迁移表。
# 正向：draft→quoted→wrapping→done；cancelled 仅能从 draft/quoted 进入；
# 只有 quoted 可退回 draft（为更换挂接 run），其余跳转一律拒绝。
TRANSITIONS = {
    STATUS_DRAFT: {STATUS_QUOTED, STATUS_CANCELLED},
    STATUS_QUOTED: {STATUS_WRAPPING, STATUS_CANCELLED, STATUS_DRAFT},
    STATUS_WRAPPING: {STATUS_DONE},
    STATUS_DONE: set(),
    STATUS_CANCELLED: set(),
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row):
    return dict(row) if row else None


def get_work_order(wo_id):
    c = connect()
    try:
        row = c.execute("SELECT * FROM work_orders WHERE id=?", (wo_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        c.close()


def get_by_code(code):
    c = connect()
    try:
        row = c.execute("SELECT * FROM work_orders WHERE code=?", (code,)).fetchone()
        return _row_to_dict(row)
    finally:
        c.close()


def list_work_orders(status=None):
    c = connect()
    try:
        if status:
            rows = c.execute(
                "SELECT * FROM work_orders WHERE status=? ORDER BY id DESC", (status,)
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM work_orders ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def create_work_order(run_id, code, note=""):
    c = connect()
    try:
        now = _now()
        cur = c.execute(
            """INSERT INTO work_orders(code,run_id,status,note,created_at,updated_at)
               VALUES (?,?,?,?,?,?)""",
            (code, run_id, STATUS_DRAFT, note, now, now),
        )
        c.commit()
        return get_work_order(int(cur.lastrowid))
    finally:
        c.close()


def attach_run(wo_id, run_id):
    """仅在 draft 下允许更换挂接 run；调用方负责状态校验。"""
    c = connect()
    try:
        c.execute(
            "UPDATE work_orders SET run_id=?, updated_at=? WHERE id=?",
            (run_id, _now(), wo_id),
        )
        c.commit()
    finally:
        c.close()
    return get_work_order(wo_id)


def quote_work_order(wo_id, snapshot, run_id):
    """quoted 成功时把挂接 run 的用料固化进工单，此后不再被现场值覆盖。"""
    c = connect()
    try:
        now = _now()
        c.execute(
            """UPDATE work_orders
               SET status=?, run_id=?, paper_m2=?, ribbon_m=?, wrap_style=?,
                   box_surface=?, overlap=?, box_id=?, box_name=?, quoted_at=?, updated_at=?
               WHERE id=?""",
            (
                STATUS_QUOTED,
                run_id,
                snapshot["paper_m2"],
                snapshot["ribbon_m"],
                snapshot["wrap_style"],
                snapshot.get("box_surface"),
                snapshot.get("overlap"),
                snapshot.get("box_id"),
                snapshot.get("box_name"),
                now,
                now,
                wo_id,
            ),
        )
        c.commit()
    finally:
        c.close()
    return get_work_order(wo_id)


def set_status(wo_id, status):
    c = connect()
    try:
        c.execute(
            "UPDATE work_orders SET status=?, updated_at=? WHERE id=?",
            (status, _now(), wo_id),
        )
        c.commit()
    finally:
        c.close()
    return get_work_order(wo_id)


def reset_to_draft(wo_id):
    """退回 draft：解除报价承诺，固化值清空，可重新挂接 run。"""
    c = connect()
    try:
        c.execute(
            """UPDATE work_orders
               SET status=?, paper_m2=NULL, ribbon_m=NULL, wrap_style=NULL,
                   box_surface=NULL, overlap=NULL, box_id=NULL, box_name=NULL,
                   quoted_at=NULL, updated_at=?
               WHERE id=?""",
            (STATUS_DRAFT, _now(), wo_id),
        )
        c.commit()
    finally:
        c.close()
    return get_work_order(wo_id)


def references_for_runs(run_ids):
    """返回 {run_id: [work_order 摘要]}，供用纸档列表/详情显示引用。"""
    if not run_ids:
        return {}
    c = connect()
    try:
        marks = ",".join("?" for _ in run_ids)
        rows = c.execute(
            f"SELECT id, code, status, run_id, paper_m2 FROM work_orders WHERE run_id IN ({marks}) ORDER BY id",
            tuple(run_ids),
        ).fetchall()
        out = {rid: [] for rid in run_ids}
        for r in rows:
            out[r["run_id"]].append(
                {"id": r["id"], "code": r["code"], "status": r["status"], "paper_m2": r["paper_m2"]}
            )
        return out
    finally:
        c.close()


def next_code():
    c = connect()
    try:
        n = c.execute("SELECT COUNT(*) c FROM work_orders").fetchone()["c"] + 1
        return f"WO-{n:04d}"
    finally:
        c.close()
