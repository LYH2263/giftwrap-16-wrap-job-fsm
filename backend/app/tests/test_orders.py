import pytest
from fastapi.testclient import TestClient

from app import seed
from app.db import connect
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.db.DB_PATH", tmp_path / "test.db")
    seed.init_db()
    with TestClient(app) as c:
        yield c


def _make_run(client, box_id=1):
    r = client.post("/api/estimate", json={"box_id": box_id, "save": True})
    assert r.status_code == 200
    return r.json()["run_id"]


def _make_order(client, title="测试工单", run_id=None):
    body = {"title": title}
    if run_id is not None:
        body["run_id"] = run_id
    r = client.post("/api/orders", json=body)
    assert r.status_code == 201
    return r.json()


def _status(client, oid):
    return client.get(f"/api/orders/{oid}").json()["status"]


def _go(client, oid, to):
    return client.post(f"/api/orders/{oid}/transition", json={"to": to})


def _update_box(box_id, **fields):
    c = connect()
    try:
        sets = ",".join(f"{k}=?" for k in fields)
        c.execute(f"UPDATE boxes SET {sets} WHERE id=?", (*fields.values(), box_id))
        c.commit()
    finally:
        c.close()


def test_happy_path_freezes_snapshot(client):
    run_id = _make_run(client)
    o = _make_order(client, run_id=run_id)
    oid = o["id"]
    assert o["status"] == "draft" and o["paper_m2"] is None

    q = _go(client, oid, "quoted")
    assert q.status_code == 200
    d = q.json()
    assert d["status"] == "quoted"
    assert d["paper_m2"] == 0.31  # 盒1 0.3x0.2x0.15 折边1.15
    assert d["ribbon_m"] == 2.2
    assert d["quoted_at"]

    assert _go(client, oid, "wrapping").json()["status"] == "wrapping"
    done = _go(client, oid, "done").json()
    assert done["status"] == "done"
    assert done["paper_m2"] == 0.31  # 固化值全程不变
    assert done["allowed_transitions"] == []


def test_illegal_transitions_fail_and_state_unchanged(client):
    run_id = _make_run(client)
    oid = _make_order(client, run_id=run_id)["id"]

    for bad in ("wrapping", "done", "draft"):
        r = _go(client, oid, bad)
        assert r.status_code == 409
        assert _status(client, oid) == "draft"

    assert _go(client, oid, "quoted").status_code == 200
    assert _go(client, oid, "done").status_code == 409
    assert _status(client, oid) == "quoted"

    assert _go(client, oid, "wrapping").status_code == 200
    for bad in ("quoted", "draft", "cancelled"):
        assert _go(client, oid, bad).status_code == 409
        assert _status(client, oid) == "wrapping"

    assert _go(client, oid, "done").status_code == 200
    for bad in ("quoted", "wrapping", "draft", "cancelled"):
        assert _go(client, oid, bad).status_code == 409
        assert _status(client, oid) == "done"


def test_unknown_status_rejected(client):
    oid = _make_order(client)["id"]
    assert _go(client, oid, "flying").status_code == 422
    assert _status(client, oid) == "draft"


def test_cancel_only_from_draft_or_quoted(client):
    run_id = _make_run(client)
    o1 = _make_order(client, "单1", run_id)
    assert _go(client, o1["id"], "cancelled").status_code == 200
    assert _go(client, o1["id"], "quoted").status_code == 409  # 终态不可再跳

    o2 = _make_order(client, "单2", run_id)
    _go(client, o2["id"], "quoted")
    assert _go(client, o2["id"], "cancelled").status_code == 200

    o3 = _make_order(client, "单3", run_id)
    _go(client, o3["id"], "quoted")
    _go(client, o3["id"], "wrapping")
    assert _go(client, o3["id"], "cancelled").status_code == 409
    assert _status(client, o3["id"]) == "wrapping"


def test_quote_requires_attached_run(client):
    oid = _make_order(client)["id"]
    r = _go(client, oid, "quoted")
    assert r.status_code == 409
    assert _status(client, oid) == "draft"


def test_frozen_values_survive_box_and_overlap_changes(client):
    run_id = _make_run(client)
    oid = _make_order(client, run_id=run_id)["id"]
    _go(client, oid, "quoted")

    _update_box(1, length=2.0)  # 报价后改盒边
    c = connect()
    try:
        c.execute("UPDATE settings SET value='2.0' WHERE key='overlap'")  # 改折边系数
        c.commit()
    finally:
        c.close()

    d = client.get(f"/api/orders/{oid}").json()
    assert d["paper_m2"] == 0.31 and d["ribbon_m"] == 2.2  # 快照为准
    assert d["live"]["paper_m2"] != 0.31  # 现场重算只作对照
    assert d["live"]["overlap"] == 2.0

    items = client.get("/api/orders").json()["items"]  # 列表与详情一致
    row = next(i for i in items if i["id"] == oid)
    assert row["paper_m2"] == 0.31 and row["status"] == "quoted" and row["run_id"] == run_id


def test_reattach_only_after_returning_to_draft(client):
    run1 = _make_run(client)
    run2 = _make_run(client, box_id=2)
    oid = _make_order(client, run_id=run1)["id"]
    _go(client, oid, "quoted")

    r = client.post(f"/api/orders/{oid}/attach", json={"run_id": run2})
    assert r.status_code == 409  # quoted 后禁止直接换挂

    back = _go(client, oid, "draft").json()  # 退回草稿
    assert back["paper_m2"] is None and back["ribbon_m"] is None
    assert back["quoted_at"] is None

    ok = client.post(f"/api/orders/{oid}/attach", json={"run_id": run2})
    assert ok.status_code == 200 and ok.json()["run_id"] == run2

    q = _go(client, oid, "quoted").json()  # 重新报价固化新 run 的值
    assert q["run_id"] == run2
    assert q["paper_m2"] == client.get(f"/api/runs/{run2}").json()["result"]["paper_m2"]


def test_attach_validation(client):
    oid = _make_order(client)["id"]
    assert client.post(f"/api/orders/{oid}/attach", json={"run_id": 999}).status_code == 404
    assert client.get("/api/orders/999").status_code == 404
    assert _go(client, 999, "quoted").status_code == 404
    assert client.post("/api/orders", json={"title": "x", "run_id": 999}).status_code == 404


def test_list_and_detail_consistent(client):
    run_id = _make_run(client)
    a = _make_order(client, "甲", run_id)
    b = _make_order(client, "乙")
    _go(client, a["id"], "quoted")

    items = {i["id"]: i for i in client.get("/api/orders").json()["items"]}
    for oid in (a["id"], b["id"]):
        d = client.get(f"/api/orders/{oid}").json()
        for key in ("id", "title", "status", "run_id", "paper_m2", "ribbon_m"):
            assert items[oid][key] == d[key]


def test_run_detail_shows_referencing_orders(client):
    run_id = _make_run(client)
    o = _make_order(client, "引用单", run_id)
    _go(client, o["id"], "quoted")

    run = client.get(f"/api/runs/{run_id}").json()
    assert run["orders"] == [{"id": o["id"], "title": "引用单", "status": "quoted"}]

    listed = client.get("/api/runs").json()["items"]
    assert next(r for r in listed if r["id"] == run_id)["order_count"] == 1

    free_run = _make_run(client)
    assert client.get(f"/api/runs/{free_run}").json()["orders"] == []
    assert client.get("/api/runs/999").status_code == 404
