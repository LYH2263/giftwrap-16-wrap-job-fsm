def _act(client, wo_id, action):
    return client.post(
        f"/api/work-orders/{wo_id}/transition", json={"action": action}
    )


def _create(client, run_id=None):
    r = client.post("/api/work-orders", json={"run_id": run_id})
    assert r.status_code == 200, r.text
    return r.json()


def _get(client, wo_id):
    return client.get(f"/api/work-orders/{wo_id}").json()


def test_create_draft_with_run(client, saved_run):
    run = saved_run()
    wo = _create(client, run["run_id"])
    assert wo["status"] == "draft"
    assert wo["run_id"] == run["run_id"]
    assert wo["paper_m2"] is None
    assert wo["code"]


def test_create_with_unknown_run_rejected(client):
    r = client.post("/api/work-orders", json={"run_id": 9999})
    assert r.status_code == 422


def test_quote_freezes_paper_and_ribbon(client, saved_run):
    run = saved_run()
    wo = _create(client, run["run_id"])
    r = _act(client, wo["id"], "quote")
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["status"] == "quoted"
    assert q["paper_m2"] == run["paper_m2"]
    assert q["ribbon_m"] == run["ribbon"]["ribbon_m"]
    assert q["wrap_style"] == run["ribbon"]["wrap_style"]
    assert q["box_id"] == run["box"]["id"]
    assert q["box_name"] == run["box"]["name"]


def test_quote_without_run_rejected_and_unchanged(client):
    wo = _create(client)
    r = _act(client, wo["id"], "quote")
    assert r.status_code == 422
    assert _get(client, wo["id"])["status"] == "draft"


def test_legal_forward_path(client, saved_run):
    wo = _create(client, saved_run()["run_id"])
    assert _act(client, wo["id"], "quote").json()["status"] == "quoted"
    assert _act(client, wo["id"], "start").json()["status"] == "wrapping"
    assert _act(client, wo["id"], "complete").json()["status"] == "done"


def test_illegal_transitions_fail_and_keep_status(client, saved_run):
    wo = _create(client, saved_run()["run_id"])
    # draft 只能 quote / cancel
    for action in ("start", "complete"):
        assert _act(client, wo["id"], action).status_code == 409
    assert _get(client, wo["id"])["status"] == "draft"

    _act(client, wo["id"], "quote")
    # quoted 不能直接 complete
    assert _act(client, wo["id"], "complete").status_code == 409
    assert _get(client, wo["id"])["status"] == "quoted"

    _act(client, wo["id"], "start")
    # wrapping 不能 cancel / 不能回退
    for action in ("cancel", "revert", "quote"):
        assert _act(client, wo["id"], action).status_code == 409
    assert _get(client, wo["id"])["status"] == "wrapping"

    _act(client, wo["id"], "complete")
    # done 是终点：任何动作都拒绝
    for action in ("cancel", "revert", "start", "quote"):
        assert _act(client, wo["id"], action).status_code == 409
    assert _get(client, wo["id"])["status"] == "done"


def test_cancel_only_from_draft_or_quoted(client, saved_run):
    # draft -> cancelled
    wo1 = _create(client, saved_run()["run_id"])
    assert _act(client, wo1["id"], "cancel").json()["status"] == "cancelled"
    # cancelled 是终点
    assert _act(client, wo1["id"], "quote").status_code == 409

    # quoted -> cancelled
    wo2 = _create(client, saved_run()["run_id"])
    _act(client, wo2["id"], "quote")
    assert _act(client, wo2["id"], "cancel").json()["status"] == "cancelled"

    # wrapping -> cancelled 必须失败
    wo3 = _create(client, saved_run()["run_id"])
    _act(client, wo3["id"], "quote")
    _act(client, wo3["id"], "start")
    r = _act(client, wo3["id"], "cancel")
    assert r.status_code == 409
    assert _get(client, wo3["id"])["status"] == "wrapping"


def test_frozen_snapshot_not_overwritten_when_box_changes(client, saved_run):
    """quoted 固化后修改盒边并以新折边重算，工单快照保持不变（快照为唯一真相）。"""
    run = saved_run(box_id=1)
    wo = _create(client, run["run_id"])
    quoted = _act(client, wo["id"], "quote").json()
    frozen_paper, frozen_ribbon = quoted["paper_m2"], quoted["ribbon_m"]

    from app.db import connect
    con = connect()
    con.execute("UPDATE boxes SET height=0.25, length=0.40 WHERE id=1")
    con.commit()
    con.close()

    # 新折边系数下的新现场值，确认现场确实变了
    new_run = client.post(
        "/api/estimate",
        json={"box_id": 1, "overlap": 1.3, "save": True},
    ).json()
    assert new_run["paper_m2"] != frozen_paper

    detail = _get(client, wo["id"])
    assert detail["paper_m2"] == frozen_paper
    assert detail["ribbon_m"] == frozen_ribbon
    # 挂接的仍是原 run，其存档值与快照一致，无漂移
    assert detail["run"]["id"] == run["run_id"]
    assert detail["run"]["paper_m2"] == frozen_paper
    assert detail["snapshot_drifted"] is False


def test_attach_run_only_in_draft(client, saved_run):
    run1 = saved_run(box_id=1)
    run2 = saved_run(box_id=2)
    wo = _create(client, run1["run_id"])

    # draft 允许换
    r = client.put(f"/api/work-orders/{wo['id']}/run", json={"run_id": run2["run_id"]})
    assert r.status_code == 200
    assert r.json()["run_id"] == run2["run_id"]

    # quoted 之后禁止换
    _act(client, wo["id"], "quote")
    r = client.put(f"/api/work-orders/{wo['id']}/run", json={"run_id": run1["run_id"]})
    assert r.status_code == 409
    assert _get(client, wo["id"])["run_id"] == run2["run_id"]

    # wrapping / done 同样禁止
    _act(client, wo["id"], "start")
    assert client.put(
        f"/api/work-orders/{wo['id']}/run", json={"run_id": run1["run_id"]}
    ).status_code == 409
    _act(client, wo["id"], "complete")
    assert client.put(
        f"/api/work-orders/{wo['id']}/run", json={"run_id": run1["run_id"]}
    ).status_code == 409


def test_revert_quoted_to_draft_then_reattach(client, saved_run):
    run1 = saved_run(box_id=1)
    run2 = saved_run(box_id=2)
    wo = _create(client, run1["run_id"])
    quoted = _act(client, wo["id"], "quote").json()
    assert quoted["paper_m2"] is not None

    # 只有 quoted 能退回 draft
    r = _act(client, wo["id"], "revert")
    assert r.status_code == 200
    rev = r.json()
    assert rev["status"] == "draft"
    assert rev["paper_m2"] is None
    assert rev["ribbon_m"] is None
    assert rev["quoted_at"] is None
    assert rev["run_id"] == run1["run_id"]

    # 退回后可换 run，再报价则按新 run 固化
    att = client.put(f"/api/work-orders/{wo['id']}/run", json={"run_id": run2["run_id"]})
    assert att.status_code == 200
    q2 = _act(client, wo["id"], "quote").json()
    assert q2["paper_m2"] == run2["paper_m2"]
    assert q2["ribbon_m"] == run2["ribbon"]["ribbon_m"]


def test_revert_only_from_quoted(client, saved_run):
    wo = _create(client, saved_run()["run_id"])
    assert _act(client, wo["id"], "revert").status_code == 409  # draft 无需退
    _act(client, wo["id"], "quote")
    _act(client, wo["id"], "start")
    assert _act(client, wo["id"], "revert").status_code == 409  # wrapping 不能退


def test_list_summary_matches_detail(client, saved_run):
    run = saved_run()
    wo = _create(client, run["run_id"])
    _act(client, wo["id"], "quote")

    listing = client.get("/api/work-orders").json()["items"]
    row = next(w for w in listing if w["id"] == wo["id"])
    detail = _get(client, wo["id"])
    for key in ("status", "run_id", "paper_m2", "ribbon_m", "code"):
        assert row[key] == detail[key]
    assert row["run"]["id"] == detail["run"]["id"] == run["run_id"]


def test_list_filter_by_status(client, saved_run):
    wo = _create(client, saved_run()["run_id"])
    _act(client, wo["id"], "quote")
    _create(client, saved_run()["run_id"])  # 另一个 draft

    quoted = client.get("/api/work-orders?status=quoted").json()["items"]
    drafts = client.get("/api/work-orders?status=draft").json()["items"]
    assert all(w["status"] == "quoted" for w in quoted)
    assert all(w["status"] == "draft" for w in drafts)
    assert {w["id"] for w in quoted} == {wo["id"]}


def test_run_detail_shows_work_order_reference(client, saved_run):
    run = saved_run()
    wo = _create(client, run["run_id"])
    _act(client, wo["id"], "quote")

    detail = client.get(f"/api/runs/{run['run_id']}").json()
    refs = detail["work_orders"]
    assert len(refs) == 1
    assert refs[0]["id"] == wo["id"]
    assert refs[0]["code"] == wo["code"]
    assert refs[0]["status"] == "quoted"
    assert refs[0]["paper_m2"] == run["paper_m2"]

    # 列表也能看到引用标记
    rows = client.get("/api/runs").json()["items"]
    row = next(r for r in rows if r["id"] == run["run_id"])
    assert row["work_orders"][0]["id"] == wo["id"]

    # 未被引用的 run 为空列表
    other = saved_run(box_id=2)
    row = next(r for r in client.get("/api/runs").json()["items"] if r["id"] == other["run_id"])
    assert row["work_orders"] == []


def test_run_reference_navigation_both_ways(client, saved_run):
    """工单能进用纸档（run_id），用纸档能回看工单。"""
    run = saved_run()
    wo = _create(client, run["run_id"])
    detail = _get(client, wo["id"])
    run_ref = client.get(f"/api/runs/{detail['run_id']}").json()
    assert any(w["id"] == wo["id"] for w in run_ref["work_orders"])


def test_unknown_work_order_and_action(client):
    assert client.get("/api/work-orders/424242").status_code == 404
    assert client.post(
        "/api/work-orders/424242/transition", json={"action": "quote"}
    ).status_code == 404

    run = client.post("/api/estimate", json={"box_id": 1, "save": True}).json()
    wo = _create(client, run["run_id"])
    assert _act(client, wo["id"], "teleport").status_code == 422
    assert _get(client, wo["id"])["status"] == "draft"
