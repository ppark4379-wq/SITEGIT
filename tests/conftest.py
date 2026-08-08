"""테스트 공통 설정.

실제 외장 SSD의 운영 DB를 건드리면 안 되므로, app 모듈이 import 되기 전에
DATABASE_URL을 임시 파일로 돌려놓습니다. backend/app/db/session.py가 import
시점에 엔진을 만들기 때문에 fixture가 아니라 모듈 최상단에서 설정합니다.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

_TEST_DB = Path(tempfile.mkdtemp(prefix="sitegit-tests-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ["SITEGIT_DATA_ROOT"] = str(_TEST_DB.parent)

import pytest  # noqa: E402  (환경 변수 설정 후에 import 해야 합니다)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    # COOKIE_SECURE=true인 운영 설정을 그대로 검증하려면 https로 요청해야 합니다.
    # http면 브라우저와 마찬가지로 Secure 쿠키가 저장되지 않아 전부 401이 됩니다.
    # with 블록에 들어갈 때 startup 이벤트가 돌면서 테이블 생성과 seed가 끝납니다.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture(scope="session")
def settings():
    from app.core.config import get_settings

    return get_settings()


@pytest.fixture
def manager_client(client, settings):
    """관리 권한으로 로그인한 클라이언트."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.initial_manager_username,
            "password": settings.initial_manager_password,
        },
    )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def viewer_client(client, settings):
    """조회 전용 계정. 지시 발행과 승인이 막혀야 합니다."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.initial_viewer_username,
            "password": settings.initial_viewer_password,
        },
    )
    assert response.status_code == 200, response.text
    yield client
    # 다음 테스트가 viewer 쿠키를 물려받지 않도록 되돌립니다.
    client.post("/api/v1/auth/logout", json={})
