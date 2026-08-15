from __future__ import annotations

from uuid import uuid4


def _create(manager_client, *, title: str, predecessor_wp_id: str | None = None):
    marker = uuid4().hex[:8].upper()
    response = manager_client.post(
        "/api/v1/work-packages",
        json={
            "id": f"WP-TEST-{marker}",
            "project_id": "WP-FLOW-TEST",
            "work_type": "EXCAVATION",
            "zone_id": f"ZONE-{marker}",
            "title": title,
            "target": {"volume_m3": 642},
            "predecessor_wp_id": predecessor_wp_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _finish(manager_client, work_package_id: str):
    started = manager_client.post(f"/api/v1/work-packages/{work_package_id}/start")
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "RUNNING"
    finished = manager_client.post(f"/api/v1/work-packages/{work_package_id}/finish")
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "REVIEW"


def _evaluate(manager_client, work_package_id: str, *, failed: bool):
    criteria = [
        {"code": "TARGET_SURFACE", "label": "목표 형상", "status": "FAIL" if failed else "PASS",
         "reason": "동측 경계 편차" if failed else None},
        {"code": "TOLERANCE", "label": "허용 오차", "status": "PASS"},
        {"code": "EXCLUSION_ZONE", "label": "보호구역", "status": "PASS"},
        {"code": "EVIDENCE_COMPLETE", "label": "결과 데이터", "status": "PASS"},
    ]
    response = manager_client.post(
        f"/api/v1/work-packages/{work_package_id}/evaluation",
        json={
            "progress": {"completed": 642, "target": 642, "unit": "m3", "percentage": 100},
            "criteria": criteria,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_progress_complete_can_still_require_rework(manager_client):
    item = _create(manager_client, title="진행률과 완료조건 분리")
    _finish(manager_client, item["id"])

    evaluation = _evaluate(manager_client, item["id"], failed=True)

    assert evaluation["progress"]["percentage"] == 100
    assert evaluation["overall"] == "FAIL"
    assert evaluation["recommended_action"] == "REWORK"
    current = manager_client.get(f"/api/v1/work-packages/{item['id']}").json()
    assert current["status"] == "REWORK"
    assert current["failed_criteria_json"][0]["code"] == "TARGET_SURFACE"


def test_rework_release_unlocks_successor_and_records_versions(manager_client):
    excavation = _create(manager_client, title="굴착")
    bedding = _create(manager_client, title="관로 기초", predecessor_wp_id=excavation["id"])
    assert bedding["status"] == "DRAFT"
    assert bedding["release_gate"] == "LOCKED"
    assert manager_client.post(f"/api/v1/work-packages/{bedding['id']}/start").status_code == 409

    _finish(manager_client, excavation["id"])
    assert _evaluate(manager_client, excavation["id"], failed=True)["overall"] == "FAIL"

    created = manager_client.post(
        f"/api/v1/work-packages/{excavation['id']}/rework",
        json={"reason": "동측 경계를 다시 정형", "target_area": {"zone": "east-edge"}},
    )
    assert created.status_code == 201, created.text
    rework = created.json()
    assert rework["status"] == "READY"
    assert rework["parent_wp_id"] == excavation["id"]

    _finish(manager_client, rework["id"])
    assert _evaluate(manager_client, rework["id"], failed=False)["recommended_action"] == "RELEASE_READY"
    released = manager_client.post(f"/api/v1/work-packages/{rework['id']}/release")
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "RELEASED"

    original = manager_client.get(f"/api/v1/work-packages/{excavation['id']}").json()
    successor = manager_client.get(f"/api/v1/work-packages/{excavation['id']}/successor").json()["successor"]
    assert original["status"] == "RELEASED"
    assert successor["id"] == bedding["id"]
    assert successor["status"] == "READY"
    assert successor["release_gate"] == "OPEN"

    events = manager_client.get(f"/api/v1/work-packages/{excavation['id']}/versions").json()
    event_types = {event["event_type"] for event in events}
    assert {"WP_CREATED", "WP_READY", "EXECUTION_FINISHED", "CRITERIA_FAILED", "REWORK_CREATED", "RELEASED"} <= event_types

