from datetime import datetime, timezone
from app.db import connect


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_order(title, run_id=None):
    c = connect()
    try:
        now = _now()
        cur = c.execute(
            "INSERT INTO work_orders(title,run_id,status,created_at,updated_at) VALUES (?,?,?,?,?)",
            (title, run_id, "draft", now, now),
        )
        c.commit()
        return int(cur.lastrowid)
    finally:
        c.close()


def list_orders():
    c = connect()
    try:
        return [dict(r) for r in c.execute("SELECT * FROM work_orders ORDER BY id DESC").fetchall()]
    finally:
        c.close()


def get_order(oid):
    c = connect()
    try:
        r = c.execute("SELECT * FROM work_orders WHERE id=?", (oid,)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def attach_run(oid, run_id):
    c = connect()
    try:
        c.execute("UPDATE work_orders SET run_id=?,updated_at=? WHERE id=?", (run_id, _now(), oid))
        c.commit()
    finally:
        c.close()


def set_status(oid, status):
    c = connect()
    try:
        c.execute("UPDATE work_orders SET status=?,updated_at=? WHERE id=?", (status, _now(), oid))
        c.commit()
    finally:
        c.close()


def set_quoted(oid, paper_m2, ribbon_m):
    """draft→quoted：固化快照写入工单行，此后不再被任何路径覆盖。"""
    c = connect()
    try:
        c.execute(
            "UPDATE work_orders SET status='quoted',paper_m2=?,ribbon_m=?,quoted_at=?,updated_at=? WHERE id=?",
            (paper_m2, ribbon_m, _now(), _now(), oid),
        )
        c.commit()
    finally:
        c.close()


def set_draft(oid):
    """quoted→draft 退回：清掉固化快照，允许重新挂接 run 后再报价。"""
    c = connect()
    try:
        c.execute(
            "UPDATE work_orders SET status='draft',paper_m2=NULL,ribbon_m=NULL,quoted_at=NULL,updated_at=? WHERE id=?",
            (_now(), oid),
        )
        c.commit()
    finally:
        c.close()


def list_orders_for_run(run_id):
    c = connect()
    try:
        return [
            dict(r)
            for r in c.execute(
                "SELECT id,title,status FROM work_orders WHERE run_id=? ORDER BY id DESC", (run_id,)
            ).fetchall()
        ]
    finally:
        c.close()
