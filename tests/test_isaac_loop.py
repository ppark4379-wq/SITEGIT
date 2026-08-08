"""Isaac 폐루프 검증: 웹 지시 → Isaac 실행 → Commit → 관리자 승인 → 맵 반영.

이 파일이 지키는 핵심 불변식은 하나입니다.
**승인되지 않은 결과는 절대 맵에 나타나지 않는다.**
"""

from __future__ import annotations

PROJECT_ID = "SASANG-001"


def _create_instruction(client, *, label="테스트 큐브", position=None, color="#f0b429"):
    response = client.post(
        "/api/v1/isaac/instructions",
        json={
            "project_id": PROJECT_ID,
            "kind": "place_cube",
            "params": {
                "position": position or {"x": 10, "y": 6, "z": -20},
                "size": {"x": 8, "y": 8, "z": 8},
                "label": label,
                "color": color,
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _commit(client, instruction, *, status="succeeded", result=None):
    response = client.post(
        f"/api/v1/isaac/instructions/{instruction['id']}/commit",
        json={
            "status": status,
            "result": result
            if result is not None
            else {
                "placed_position": instruction["params"]["position"],
                "placed_size": instruction["params"]["size"],
                "prim_path": "/World/SiteGit/cube_test",
            },
            "evidence": {"sensors": [], "storage_keys": []},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _map_objects(client):
    response = client.get("/api/v1/isaac/map-objects", params={"project_id": PROJECT_ID})
    assert response.status_code == 200, response.text
    return response.json()["objects"]


def _labels(client):
    return {item["label"] for item in _map_objects(client)}


def test_full_loop_puts_cube_on_map_only_after_approval(manager_client):
    instruction = _create_instruction(manager_client, label="승인 큐브")
    assert instruction["status"] == "pending"
    assert "승인 큐브" not in _labels(manager_client)

    commit = _commit(manager_client, instruction)
    assert commit["review_status"] == "pending"
    # 여기가 핵심입니다. Commit만으로는 맵에 올라오지 않습니다.
    assert "승인 큐브" not in _labels(manager_client)

    response = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "approved", "note": "형상 확인"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["review_status"] == "approved"

    placed = next(o for o in _map_objects(manager_client) if o["label"] == "승인 큐브")
    assert placed["position"] == {"x": 10.0, "y": 6.0, "z": -20.0}
    assert placed["type"] == "cube"
    assert placed["approved_by"]


def test_rejected_commit_never_reaches_the_map(manager_client):
    instruction = _create_instruction(manager_client, label="반려 큐브")
    commit = _commit(manager_client, instruction)

    response = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "rejected", "note": "지형과 겹침"},
    )
    assert response.status_code == 200, response.text
    assert "반려 큐브" not in _labels(manager_client)


def test_claim_marks_dispatched_so_the_same_work_is_not_run_twice(manager_client):
    _create_instruction(manager_client, label="중복 방지 큐브")

    first = manager_client.post("/api/v1/isaac/instructions/claim", params={"project_id": PROJECT_ID})
    assert first.status_code == 200
    claimed_ids = {item["id"] for item in first.json()}
    assert claimed_ids
    assert all(item["status"] == "dispatched" for item in first.json())

    second = manager_client.post("/api/v1/isaac/instructions/claim", params={"project_id": PROJECT_ID})
    assert second.status_code == 200
    assert not (claimed_ids & {item["id"] for item in second.json()})


def test_double_review_is_rejected(manager_client):
    instruction = _create_instruction(manager_client, label="이중 판정 큐브")
    commit = _commit(manager_client, instruction)
    path = f"/api/v1/isaac/commits/{commit['id']}/review"

    assert manager_client.post(path, json={"decision": "approved"}).status_code == 200
    assert manager_client.post(path, json={"decision": "rejected"}).status_code == 409


def test_failed_execution_cannot_be_approved(manager_client):
    instruction = _create_instruction(manager_client, label="실패 큐브")
    commit = _commit(
        manager_client, instruction, status="failed", result={"error": "Isaac stage not ready"}
    )

    response = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review", json={"decision": "approved"}
    )
    assert response.status_code == 422
    assert "실패 큐브" not in _labels(manager_client)


def test_map_uses_placed_position_not_the_instructed_one(manager_client):
    """지형 스냅·충돌 회피로 실제 위치가 달라지면 맵은 실제 위치를 그려야 합니다."""
    instruction = _create_instruction(
        manager_client, label="스냅 큐브", position={"x": 0, "y": 50, "z": 0}
    )
    commit = _commit(
        manager_client,
        instruction,
        result={
            "placed_position": {"x": 0, "y": 3, "z": 0},
            "placed_size": instruction["params"]["size"],
        },
    )
    manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review", json={"decision": "approved"}
    )

    placed = next(o for o in _map_objects(manager_client) if o["label"] == "스냅 큐브")
    assert placed["position"]["y"] == 3.0


def test_invalid_color_is_rejected(manager_client):
    response = manager_client.post(
        "/api/v1/isaac/instructions",
        json={
            "project_id": PROJECT_ID,
            "kind": "place_cube",
            "params": {"position": {"x": 0, "y": 0, "z": 0}, "color": "red"},
        },
    )
    assert response.status_code == 422


def test_viewer_cannot_issue_or_approve(viewer_client):
    create = viewer_client.post(
        "/api/v1/isaac/instructions",
        json={
            "project_id": PROJECT_ID,
            "kind": "place_cube",
            "params": {"position": {"x": 0, "y": 0, "z": 0}},
        },
    )
    assert create.status_code == 403
    # 조회는 허용됩니다.
    assert viewer_client.get(
        "/api/v1/isaac/map-objects", params={"project_id": PROJECT_ID}
    ).status_code == 200


def test_map_objects_require_authentication(client):
    client.post("/api/v1/auth/logout", json={})
    assert client.get("/api/v1/isaac/map-objects").status_code == 401


def test_isaac_mesh_requires_authentication(client):
    """지형 Mesh는 고정 URL로 공개되므로 무인증 다운로드를 막아야 합니다."""
    client.post("/api/v1/auth/logout", json={})
    assert client.get("/isaac-data/site-work-map/manifest.json").status_code == 401


def test_isaac_mesh_blocks_path_traversal(manager_client):
    """storage_path로 isaac 폴더 밖을 읽을 수 없어야 합니다."""
    for attack in (
        "../database/sitegit.db",
        "..%2Fdatabase%2Fsitegit.db",
        "site-work-map/../../database/sitegit.db",
    ):
        assert manager_client.get(f"/isaac-data/{attack}").status_code in (401, 404), attack
