import os
import tempfile

# 必须在导入 app.config 之前指到临时目录，保证测试不碰开发库。
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="gw-test-")

import pytest
from fastapi.testclient import TestClient

from app import seed
from app.db import connect
from app.main import app


@pytest.fixture
def client():
    seed.init_db()
    c = connect()
    c.executescript(
        "DELETE FROM work_orders;"
        "DELETE FROM calc_runs;"
        "DELETE FROM boxes;"
        "DELETE FROM papers;"
        "DELETE FROM settings;"
    )
    c.commit()
    c.close()
    seed.init_db()
    return TestClient(app)


@pytest.fixture
def saved_run(client):
    def _make(box_id=1, wrap_style="cross"):
        r = client.post(
            "/api/estimate",
            json={"box_id": box_id, "wrap_style": wrap_style, "save": True},
        )
        assert r.status_code == 200, r.text
        return r.json()

    return _make
