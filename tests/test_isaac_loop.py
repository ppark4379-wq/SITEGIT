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


def test_new_stage_scenario_replaces_the_published_map_baseline(manager_client):
    project_id = "SCENARIO-BASELINE-CUTOVER"

    def publish(scenario_id: str, target_path: str) -> None:
        response = manager_client.post(
            "/api/v1/isaac/stage-inventory",
            json={
                "project_id": project_id,
                "scenario_id": scenario_id,
                "stage_identifier": f"{scenario_id}.usd",
                "equipment": [],
                "diggable_targets": [
                    {
                        "path": target_path,
                        "name": target_path.rsplit("/", 1)[-1],
                        "type_name": "Mesh",
                        "role": "diggable",
                        "world_position": {"x": 0, "y": 0, "z": 1},
                        "bounds_size": {"x": 5, "y": 5, "z": 2},
                        "active": True,
                    }
                ],
                "scene_objects": [],
            },
        )
        assert response.status_code == 200, response.text

    publish("mud-map-v1", "/World/Diggable/OldMudPile")
    publish("pipeline-demolition-v1", "/World/Diggable/Pipeline/TrenchFill_01")

    published = manager_client.get(
        "/api/v1/isaac/map-objects", params={"project_id": project_id}
    )
    assert published.status_code == 200, published.text
    baseline = published.json()["baseline_diggable_targets"]
    assert [item["path"] for item in baseline] == [
        "/World/Diggable/Pipeline/TrenchFill_01"
    ]


def test_live_stage_change_waits_for_merge_and_rejection_becomes_conflict(manager_client):
    project_id = "MERGE-GATE-REJECT"
    target_path = "/World/Diggable/MergeGatePile"

    def publish(position, size, *, include_deposit=False):
        diggable = [
            {
                "path": target_path,
                "name": "MergeGatePile",
                "type_name": "Mesh",
                "role": "diggable",
                "world_position": position,
                "bounds_size": size,
                "active": True,
            }
        ]
        if include_deposit:
            diggable.append(
                {
                    "path": "/World/Diggable/MergeGatePile_MovedSoil_01",
                    "name": "Moved soil",
                    "type_name": "Mesh",
                    "role": "diggable",
                    "world_position": {"x": 8, "y": 4, "z": 0.8},
                    "bounds_size": {"x": 3, "y": 3, "z": 1.6},
                    "active": True,
                }
            )
        response = manager_client.post(
            "/api/v1/isaac/stage-inventory",
            json={
                "project_id": project_id,
                "stage_identifier": "merge-gate.usd",
                    "equipment": [
                        {
                            "path": "/World/Equipment/EXC_001",
                            "name": "EXC-001",
                            "type_name": "Xform",
                            "role": "equipment",
                            "world_position": {"x": 0, "y": -5, "z": 0},
                            "bounds_size": {"x": 8, "y": 4, "z": 5},
                            "active": True,
                        }
                    ],
                "diggable_targets": diggable,
                "scene_objects": [],
            },
        )
        assert response.status_code == 200, response.text

    original_position = {"x": 2, "y": 3, "z": 1.5}
    original_size = {"x": 6, "y": 5, "z": 3}
    publish(original_position, original_size)
    instruction_response = manager_client.post(
        "/api/v1/isaac/instructions",
        json={
            "project_id": project_id,
            "kind": "excavate_prim",
                "params": {
                    "equipment_prim_path": "/World/Equipment/EXC_001",
                    "equipment_name": "EXC-001",
                    "target_prim_path": target_path,
                    "target_name": "MergeGatePile",
                    "label": "Merge gate excavation",
                    "work_package_id": "WP-MERGE-REJECT",
                },
        },
    )
    assert instruction_response.status_code == 201, instruction_response.text
    instruction = instruction_response.json()
    changed_position = {"x": 2, "y": 3, "z": 0.7}
    changed_size = {"x": 6, "y": 5, "z": 1.4}
    commit = _commit(
        manager_client,
        instruction,
        result={
            "operation": "excavate_prim",
            "simulator": "isaac-sim",
            "source": "stage-readback",
            "target_prim_path": target_path,
            "target_bounds_size": original_size,
            "target_active_after": True,
            "terrain_deformation": {"available": True, "removed_volume_m3": 4.2},
            "map_changes": [
                {
                    "action": "upsert",
                    "type": "deformed_soil",
                    "label": "MergeGatePile",
                    "color": "#6B4F2A",
                    "prim_path": target_path,
                    "position": changed_position,
                    "size": changed_size,
                }
            ],
        },
    )

    # Even if the live Stage has already changed, the official map stays on
    # the immutable baseline while the commit is pending.
    publish(changed_position, changed_size, include_deposit=True)
    pending = manager_client.get(
        "/api/v1/isaac/map-objects", params={"project_id": project_id}
    ).json()
    assert pending["objects"] == []
    assert pending["baseline_diggable_targets"][0]["world_position"] == {
        "x": 2.0,
        "y": 3.0,
        "z": 1.5,
    }

    reviewed = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "rejected", "note": "작업 범위를 벗어난 굴착"},
    )
    assert reviewed.status_code == 200, reviewed.text
    rejected = manager_client.get(
        "/api/v1/isaac/map-objects", params={"project_id": project_id}
    ).json()
    assert rejected["objects"] == []
    assert rejected["conflicts"][0]["commit_id"] == commit["id"]
    assert rejected["conflicts"][0]["reason"] == "작업 범위를 벗어난 굴착"


def test_approved_mesh_deformation_is_merged_into_official_map(manager_client):
    project_id = "MERGE-GATE-APPROVE"
    target_path = "/World/Diggable/ApprovedPile"
    inventory = manager_client.post(
        "/api/v1/isaac/stage-inventory",
        json={
            "project_id": project_id,
            "stage_identifier": "merge-approve.usd",
                "equipment": [
                    {
                        "path": "/World/Equipment/EXC_001",
                        "name": "EXC-001",
                        "type_name": "Xform",
                        "role": "equipment",
                        "world_position": {"x": 0, "y": -5, "z": 0},
                        "bounds_size": {"x": 8, "y": 4, "z": 5},
                        "active": True,
                    }
                ],
            "diggable_targets": [
                {
                    "path": target_path,
                    "name": "ApprovedPile",
                    "type_name": "Mesh",
                    "role": "diggable",
                    "world_position": {"x": 0, "y": 0, "z": 1.5},
                    "bounds_size": {"x": 6, "y": 5, "z": 3},
                    "active": True,
                }
            ],
            "scene_objects": [],
        },
    )
    assert inventory.status_code == 200, inventory.text
    instruction = manager_client.post(
        "/api/v1/isaac/instructions",
        json={
            "project_id": project_id,
            "kind": "excavate_prim",
                "params": {
                    "equipment_prim_path": "/World/Equipment/EXC_001",
                    "equipment_name": "EXC-001",
                    "target_prim_path": target_path,
                    "target_name": "ApprovedPile",
                    "label": "Approved excavation",
                    "work_package_id": "WP-MERGE-APPROVE",
                },
        },
    ).json()
    geometry = {
        "format": "sitegit-triangle-mesh-v1",
        "points": [[0, 0, 0], [1, 0, 0], [0, 1, 0.2]],
        "face_vertex_counts": [3],
        "face_vertex_indices": [0, 1, 2],
    }
    commit = _commit(
        manager_client,
        instruction,
        result={
            "operation": "excavate_prim",
            "simulator": "isaac-sim",
            "source": "stage-readback",
            "target_prim_path": target_path,
            "target_bounds_size": {"x": 6, "y": 5, "z": 3},
            "target_active_after": True,
            "terrain_deformation": {"available": True, "removed_volume_m3": 4.2},
            "map_changes": [
                {
                    "action": "upsert",
                    "type": "deformed_soil",
                    "label": "ApprovedPile",
                    "color": "#6B4F2A",
                    "prim_path": target_path,
                    "position": {"x": 0, "y": 0, "z": 0.7},
                    "size": {"x": 6, "y": 5, "z": 1.4},
                    "geometry": geometry,
                }
            ],
        },
    )
    assert manager_client.get(
        "/api/v1/isaac/map-objects", params={"project_id": project_id}
    ).json()["objects"] == []

    approved = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "approved", "note": "전후 증거 확인"},
    )
    assert approved.status_code == 200, approved.text
    published = manager_client.get(
        "/api/v1/isaac/map-objects", params={"project_id": project_id}
    ).json()
    assert published["conflicts"] == []
    assert published["objects"][0]["type"] == "deformed_soil"
    assert published["objects"][0]["geometry"] == geometry


def test_timeline_keeps_every_approved_change_to_the_same_prim(manager_client):
    project_id = "TIMELINE-SAME-PRIM"
    target_path = "/World/Diggable/TimelinePile"
    inventory = manager_client.post(
        "/api/v1/isaac/stage-inventory",
        json={
            "project_id": project_id,
            "stage_identifier": "timeline.usd",
            "equipment": [
                {
                    "path": "/World/Equipment/EXC_001",
                    "name": "EXC-001",
                    "type_name": "Xform",
                    "role": "equipment",
                    "world_position": {"x": 0, "y": -5, "z": 0},
                    "bounds_size": {"x": 8, "y": 4, "z": 5},
                    "active": True,
                }
            ],
            "diggable_targets": [
                {
                    "path": target_path,
                    "name": "TimelinePile",
                    "type_name": "Mesh",
                    "role": "diggable",
                    "world_position": {"x": 1, "y": 2, "z": 1.5},
                    "bounds_size": {"x": 6, "y": 5, "z": 3},
                    "active": True,
                }
            ],
            "scene_objects": [],
        },
    )
    assert inventory.status_code == 200, inventory.text

    commit_ids = []
    expected_heights = [2.0, 1.0]
    for index, height in enumerate(expected_heights, start=1):
        instruction_response = manager_client.post(
            "/api/v1/isaac/instructions",
            json={
                "project_id": project_id,
                "kind": "excavate_prim",
                "params": {
                    "equipment_prim_path": "/World/Equipment/EXC_001",
                    "equipment_name": "EXC-001",
                    "target_prim_path": target_path,
                    "target_name": "TimelinePile",
                    "label": f"Timeline excavation {index}",
                    "work_package_id": f"WP-TIMELINE-{index}",
                },
            },
        )
        assert instruction_response.status_code == 201, instruction_response.text
        instruction = instruction_response.json()
        commit = _commit(
            manager_client,
            instruction,
            result={
                "operation": "excavate_prim",
                "simulator": "isaac-sim",
                "source": "stage-readback",
                "target_prim_path": target_path,
                "target_position": {"x": 1, "y": 2, "z": 1.5},
                "target_bounds_size": {"x": 6, "y": 5, "z": 3},
                "target_active_before": True,
                "target_active_after": True,
                "terrain_deformation": {
                    "available": True,
                    "removed_volume_m3": float(index),
                },
                "map_changes": [
                    {
                        "action": "upsert",
                        "type": "deformed_soil",
                        "label": "TimelinePile",
                        "color": "#6B4F2A",
                        "prim_path": target_path,
                        "position": {"x": 1, "y": 2, "z": height / 2},
                        "size": {"x": 6, "y": 5, "z": height},
                    }
                ],
            },
        )
        reviewed = manager_client.post(
            f"/api/v1/isaac/commits/{commit['id']}/review",
            json={"decision": "approved", "note": f"step {index}"},
        )
        assert reviewed.status_code == 200, reviewed.text
        commit_ids.append(commit["id"])

    response = manager_client.get(
        "/api/v1/isaac/map-objects", params={"project_id": project_id}
    )
    assert response.status_code == 200, response.text
    published = response.json()
    assert [step["commit_id"] for step in published["timeline"]] == commit_ids
    assert [step["objects"][0]["size"]["z"] for step in published["timeline"]] == expected_heights
    assert len(published["objects"]) == 1
    assert published["objects"][0]["size"]["z"] == expected_heights[-1]


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


def test_versioned_execution_commit_rejects_invalid_evidence_quality(manager_client):
    instruction = _create_instruction(manager_client, label="Evidence contract")
    timestamp = "2026-08-16T00:00:00+00:00"
    response = manager_client.post(
        f"/api/v1/isaac/instructions/{instruction['id']}/commit",
        json={
            "status": "succeeded",
            "result": {
                "schema_version": "1.0",
                "operation": "place_cube",
                "execution_id": "exec-test",
                "duration_seconds": 1.25,
                "geometry_change": {"available": False},
            },
            "evidence": {
                "schema_version": "1.0",
                "evidence_id": "ev-test",
                "instruction_id": instruction["id"],
                "execution_id": "exec-test",
                "source": "isaac-sim",
                "started_at": timestamp,
                "finished_at": timestamp,
                "duration_seconds": 1.25,
                "events": [],
                "artifacts": [],
                "before": {},
                "after": {},
                "quality": {
                    "required_sensor_types": ["camera", "lidar", "imu"],
                    "available_sensor_types": [],
                    "missing_sensor_types": ["camera", "lidar", "imu"],
                    "completeness_ratio": 2.0,
                },
            },
        },
    )

    assert response.status_code == 422


def test_versioned_execution_commit_preserves_sensor_and_work_metrics(manager_client):
    instruction = _create_instruction(manager_client, label="Evidence metrics")
    timestamp = "2026-08-16T00:00:00+00:00"
    response = manager_client.post(
        f"/api/v1/isaac/instructions/{instruction['id']}/commit",
        json={
            "status": "succeeded",
            "result": {
                "schema_version": "1.0",
                "operation": "excavate",
                "execution_id": "exec-metrics",
                "duration_seconds": 4.5,
                "performed_quantity": {
                    "value": 2.25,
                    "unit": "m3",
                    "method": "lidar_height_grid_max_z",
                    "estimated": True,
                },
                "geometry_change": {
                    "available": True,
                    "method": "lidar_height_grid_max_z",
                    "compared_cell_count": 12,
                    "changed_cell_count": 3,
                    "cell_size_m": 0.5,
                    "removed_volume_m3": 2.25,
                    "added_volume_m3": 0.5,
                    "net_volume_change_m3": -1.75,
                },
            },
            "evidence": {
                "schema_version": "1.0",
                "evidence_id": "ev-metrics",
                "instruction_id": instruction["id"],
                "execution_id": "exec-metrics",
                "source": "isaac-sim",
                "started_at": timestamp,
                "finished_at": "2026-08-16T00:00:04.500000+00:00",
                "duration_seconds": 4.5,
                "events": [],
                "artifacts": [],
                "before": {},
                "after": {},
                "quality": {
                    "required_sensor_types": ["camera", "lidar", "imu"],
                    "available_sensor_types": ["camera", "lidar"],
                    "missing_sensor_types": ["imu"],
                    "completeness_ratio": 0.666667,
                },
            },
        },
    )

    assert response.status_code == 201, response.text
    commit = response.json()
    assert commit["result"]["duration_seconds"] == 4.5
    assert commit["result"]["geometry_change"]["removed_volume_m3"] == 2.25
    assert commit["evidence"]["quality"]["missing_sensor_types"] == ["imu"]


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


def test_ai_work_package_dispatch_uses_the_real_isaac_approval_loop(
    manager_client, monkeypatch, settings
):
    """LLM은 구조화만 하고 Zone 좌표·Instruction·맵 반영은 서버가 담당합니다."""
    from app.api.routes import work_packages as work_package_routes
    from app.schemas.work_package_ai import CubeDimensions, LLMWorkPackagePlan

    parsed = LLMWorkPackagePlan(
        ready=True,
        operation="place_cube",
        zone_id="A",
        location="center",
        label="Zone A 노란 큐브",
        color="#FFD700",
        size=CubeDimensions(x=5, y=5, z=5),
        summary="Zone A 중앙에 5m 노란 큐브를 배치합니다.",
        clarification_question="",
    )
    monkeypatch.setattr(
        work_package_routes,
        "compile_natural_language",
        lambda _message, _settings: parsed,
    )
    site_frame = settings.sitegit_data_root / "isaac" / "site_frame.json"
    site_frame.parent.mkdir(parents=True, exist_ok=True)
    site_frame.write_text(
        '{"bounds":{"min":[-106,-114,0],"max":[106,114,24]}}',
        encoding="utf-8",
    )

    source_text = "Zone A 중앙에 노란색 큐브를 5m x 5m x 5m로 배치해줘"
    interpreted = manager_client.post(
        "/api/v1/work-packages/ai/interpret",
        json={"project_id": PROJECT_ID, "message": source_text},
    )
    assert interpreted.status_code == 200, interpreted.text
    draft = interpreted.json()
    assert draft["plan"]["color"] == "#FFD700"
    assert draft["plan"]["size"] == {"x": 5.0, "y": 5.0, "z": 5.0}
    assert draft["position"]["x"] < 0
    assert draft["position"]["y"] > 0
    assert draft["position"]["z"] == 2.5
    assert all(check["ok"] for check in draft["checks"])

    dispatched = manager_client.post(
        "/api/v1/work-packages/ai/dispatch",
        json={"project_id": PROJECT_ID, "source_text": source_text, "plan": draft["plan"]},
    )
    assert dispatched.status_code == 201, dispatched.text
    payload = dispatched.json()
    instruction = payload["instruction"]
    work_package = payload["work_package"]
    assert work_package["id"].startswith("WP-AI-A-")
    assert instruction["params"]["work_package_id"] == work_package["id"]
    assert instruction["params"]["position"] == draft["position"]
    assert "Zone A 노란 큐브" not in _labels(manager_client)

    commit = _commit(
        manager_client,
        instruction,
        result={
            "placed_position": instruction["params"]["position"],
            "placed_size": instruction["params"]["size"],
            "prim_path": "/World/SiteGit/cube_ai_demo",
            "simulator": "isaac-sim",
            "source": "stage-readback",
        },
    )
    assert "Zone A 노란 큐브" not in _labels(manager_client)

    approved = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "approved", "note": "Isaac Stage 확인"},
    )
    assert approved.status_code == 200, approved.text
    placed = next(
        item for item in _map_objects(manager_client) if item["label"] == "Zone A 노란 큐브"
    )
    assert placed["position"] == draft["position"]
    assert placed["size"] == {"x": 5.0, "y": 5.0, "z": 5.0}


def test_local_ollama_compiler_uses_json_schema(monkeypatch, settings):
    """로컬 Ollama 호출은 thinking 없이 기존 Work Package 스키마를 강제합니다."""
    import json

    import httpx

    from app.domains.work_packages import ai_compiler

    captured = {}
    model_output = {
        "ready": True,
        "operation": "place_cube",
        "zone_id": "A",
        "location": "center",
        "label": "Zone A 빨간 큐브",
        "color": "#FF0000",
        "size": {"x": 5, "y": 5, "z": 5},
        "summary": "Zone A 중앙에 빨간 큐브를 배치합니다.",
        "clarification_question": "",
    }

    def fake_post(_client, url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps(model_output, ensure_ascii=False)}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(ai_compiler.httpx.Client, "post", fake_post)
    plan = ai_compiler.compile_natural_language(
        "Zone A 중앙에 빨간색 큐브를 5m x 5m x 5m로 배치해줘",
        settings,
    )

    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["json"]["model"] == "qwen3:8b"
    assert captured["json"]["stream"] is False
    assert captured["json"]["think"] is False
    assert captured["json"]["format"]["additionalProperties"] is False
    assert plan.color == "#FF0000"
    assert plan.size.model_dump() == {"x": 5.0, "y": 5.0, "z": 5.0}


def _publish_test_stage_inventory(
    client,
    *,
    target_path="/World/construction_site_mud/soil_pile_A",
    target_name="soil_pile_A",
    target_size=None,
    target_active=True,
):
    target_size = target_size or {"x": 6, "y": 5, "z": 3}
    response = client.post(
        "/api/v1/isaac/stage-inventory",
        json={
            "project_id": PROJECT_ID,
            "stage_identifier": "test-stage.usd",
            "equipment": [
                {
                    "path": "/World/Armature",
                    "name": "EXC-001",
                    "type_name": "SkelRoot",
                    "role": "equipment",
                    "world_position": {"x": 0, "y": 0, "z": 0},
                    "bounds_size": {"x": 8, "y": 4, "z": 5},
                    "active": True,
                }
            ],
            "diggable_targets": [
                {
                    "path": target_path,
                    "name": target_name,
                    "type_name": "Mesh",
                    "role": "diggable",
                    "world_position": {"x": 10, "y": 4, "z": 1},
                    "bounds_size": target_size,
                    "active": target_active,
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["connected"] is True


def test_real_prim_work_package_uses_live_inventory_and_only_masks_map_after_approval(
    manager_client, monkeypatch
):
    from app.api.routes import work_packages as work_package_routes
    from app.schemas.work_package_ai import LLMExcavationPlan

    _publish_test_stage_inventory(manager_client)
    parsed = LLMExcavationPlan(
        ready=True,
        operation="excavate_prim",
        equipment_ref="EXC-001",
        target_ref="soil_pile_A",
        zone_id="A",
        summary="EXC-001로 Zone A 흙더미를 굴착합니다.",
        clarification_question="",
    )
    monkeypatch.setattr(
        work_package_routes,
        "compile_excavation_language",
        lambda _message, _inventory, _settings: parsed,
    )
    message = "EXC-001로 Zone A의 soil_pile_A Prim을 굴착해줘"
    interpreted = manager_client.post(
        "/api/v1/work-packages/ai/excavation/interpret",
        json={
            "project_id": PROJECT_ID,
            "message": message,
            "equipment_prim_path": "/World/Armature",
            "target_prim_path": "/World/construction_site_mud/soil_pile_A",
        },
    )
    assert interpreted.status_code == 200, interpreted.text
    draft = interpreted.json()
    assert all(check["ok"] for check in draft["checks"])
    assert draft["equipment"]["path"] == "/World/Armature"
    assert draft["target"]["path"].endswith("soil_pile_A")

    dispatched = manager_client.post(
        "/api/v1/work-packages/ai/excavation/dispatch",
        json={
            "project_id": PROJECT_ID,
            "message": message,
            "plan": draft["plan"],
            "equipment_prim_path": draft["equipment"]["path"],
            "target_prim_path": draft["target"]["path"],
        },
    )
    assert dispatched.status_code == 201, dispatched.text
    instruction = dispatched.json()["instruction"]
    assert instruction["kind"] == "excavate_prim"
    assert instruction["params"]["target_prim_path"].endswith("soil_pile_A")

    result = {
        "operation": "excavate_prim",
        "equipment_prim_path": "/World/Armature",
        "target_prim_path": "/World/construction_site_mud/soil_pile_A",
        "target_position": {"x": 10, "y": 4, "z": 1},
        "target_bounds_size": {"x": 6, "y": 5, "z": 3},
        "target_active_before": True,
        "target_active_after": False,
        "simulator": "isaac-sim",
        "source": "stage-readback",
    }
    commit = _commit(manager_client, instruction, result=result)
    assert not any(
        item["type"] == "removed_prim"
        and item["prim_path"] == result["target_prim_path"]
        for item in _map_objects(manager_client)
    )

    approved = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "approved", "note": "전후 증거 확인"},
    )
    assert approved.status_code == 200, approved.text
    removed = next(
        item
        for item in _map_objects(manager_client)
        if item["type"] == "removed_prim"
        and item["prim_path"] == result["target_prim_path"]
    )
    assert removed["prim_path"].endswith("soil_pile_A")
    assert removed["size"] == {"x": 6.0, "y": 5.0, "z": 3.0}


def test_parallel_excavation_legacy_delta_replays_cut_and_deposited_soil(manager_client):
    """Already-approved parallel jobs remain replayable after the delta schema fix."""

    target_path = "/World/Diggable/Pipeline/TrenchFill_01"
    deposit_path = "/World/Diggable/TrenchFill_01_MovedSoil_05"
    _publish_test_stage_inventory(
        manager_client,
        target_path=target_path,
        target_name="TrenchFill_01",
        target_size={"x": 8, "y": 7, "z": 1.6},
    )
    instruction_response = manager_client.post(
        "/api/v1/isaac/instructions",
        json={
            "project_id": PROJECT_ID,
            "kind": "excavate_prim",
            "params": {
                "label": "Zone A 터파기 작업전선 1",
                "equipment_prim_path": "/World/Armature",
                "equipment_name": "EXC-001",
                "target_name": "TrenchFill_01",
                "target_prim_path": target_path,
                "work_package_id": "WP-PIPELINE-LEGACY-01",
            },
        },
    )
    assert instruction_response.status_code == 201, instruction_response.text
    instruction = instruction_response.json()
    target_position = {"x": -20, "y": -30, "z": 0.8}
    target_size = {"x": 8, "y": 7, "z": 1.6}
    deposit_position = {"x": -14, "y": -31, "z": 1.2}
    deposit_size = {"x": 4, "y": 3, "z": 2.4}
    geometry = {
        "format": "sitegit-triangle-mesh-v1",
        "points": [[-16, -32, 0], [-12, -32, 0], [-14, -29, 2.4]],
        "face_vertex_counts": [3],
        "face_vertex_indices": [0, 1, 2],
    }
    commit = _commit(
        manager_client,
        instruction,
        result={
            "operation": "pipeline_excavation",
            "simulator": "isaac-sim",
            "source": "stage-readback",
            "target_prim_path": target_path,
            "target_position": target_position,
            "target_bounds_size": target_size,
            "target_active_after": False,
            "terrain_deformation": {"available": True},
            # This is the format emitted by the first parallel-excavation run.
            "map_changes": [
                {"prim_path": target_path, "active": False, "operation": "excavate"}
            ],
            "scoops": [
                {
                    "terrain_deformation": {
                        "targets": [
                            {
                                "target_prim_path": target_path,
                                "position": target_position,
                                "size": target_size,
                            }
                        ]
                    },
                    "moved_soil": {
                        "prim_path": deposit_path,
                        "position": deposit_position,
                        "size": deposit_size,
                        "geometry": geometry,
                    },
                }
            ],
        },
    )

    approved = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "approved", "note": "병렬 터파기 증거 확인"},
    )
    assert approved.status_code == 200, approved.text

    objects = _map_objects(manager_client)
    removed = next(item for item in objects if item["prim_path"] == target_path)
    deposit = next(item for item in objects if item["prim_path"] == deposit_path)
    assert removed["type"] == "removed_prim"
    assert removed["position"] == {key: float(value) for key, value in target_position.items()}
    assert deposit["type"] == "soil_deposit"
    assert deposit["position"] == {key: float(value) for key, value in deposit_position.items()}
    assert deposit["geometry"] == geometry


def test_excavation_cannot_be_approved_without_real_stage_readback(manager_client):
    _publish_test_stage_inventory(manager_client)
    instruction = manager_client.post(
        "/api/v1/isaac/instructions",
        json={
            "project_id": PROJECT_ID,
            "kind": "excavate_prim",
            "params": {
                "equipment_prim_path": "/World/Armature",
                "target_prim_path": "/World/construction_site_mud/soil_pile_A",
                "equipment_name": "EXC-001",
                "target_name": "soil_pile_A",
                "label": "검증 없는 굴착",
                "work_package_id": "WP-UNVERIFIED",
            },
        },
    ).json()
    commit = _commit(
        manager_client,
        instruction,
        result={"target_active_after": False, "simulator": "mock", "source": "echo"},
    )
    response = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "approved"},
    )
    assert response.status_code == 422


def test_fill_request_is_never_compiled_as_an_excavation(
    manager_client, monkeypatch, settings
):
    """A restore/fill request must not silently deactivate another Stage Prim."""
    from app.domains.work_packages import ai_compiler

    _publish_test_stage_inventory(manager_client)

    def fail_if_llm_is_called(*_args, **_kwargs):
        raise AssertionError("A fill request should be rejected before calling the LLM")

    monkeypatch.setattr(ai_compiler.httpx.Client, "post", fail_if_llm_is_called)
    from app.domains.executions.stage_inventory import load_stage_inventory

    plan = ai_compiler.compile_excavation_language(
        "Object_9를 다시 메워줘",
        load_stage_inventory(PROJECT_ID),
        settings,
    )

    assert plan.ready is False
    assert plan.operation == "unsupported"


def test_oversized_stage_mesh_cannot_be_dispatched(manager_client, monkeypatch):
    """Material-batch meshes that span the site are not valid excavation targets."""
    from app.api.routes import work_packages as work_package_routes
    from app.schemas.work_package_ai import LLMExcavationPlan

    target_path = "/World/construction_site_mud/Object_11/Object_9"
    _publish_test_stage_inventory(
        manager_client,
        target_path=target_path,
        target_name="Object_9",
        target_size={"x": 186.5, "y": 141.5, "z": 6.5},
    )
    plan = LLMExcavationPlan(
        ready=True,
        operation="excavate_prim",
        equipment_ref="EXC-001",
        target_ref="Object_9",
        zone_id="A",
        summary="Excavate Object_9",
        clarification_question="",
    )
    monkeypatch.setattr(
        work_package_routes,
        "compile_excavation_language",
        lambda _message, _inventory, _settings: plan,
    )
    interpreted = manager_client.post(
        "/api/v1/work-packages/ai/excavation/interpret",
        json={
            "project_id": PROJECT_ID,
            "message": "EXC-001로 Object_9를 굴착해줘",
            "equipment_prim_path": "/World/Armature",
            "target_prim_path": target_path,
        },
    )
    assert interpreted.status_code == 200, interpreted.text
    scope_check = next(
        check for check in interpreted.json()["checks"] if check["code"] == "target_scope"
    )
    assert scope_check["ok"] is False

    dispatched = manager_client.post(
        "/api/v1/work-packages/ai/excavation/dispatch",
        json={
            "project_id": PROJECT_ID,
            "message": "EXC-001로 Object_9를 굴착해줘",
            "plan": plan.model_dump(),
            "equipment_prim_path": "/World/Armature",
            "target_prim_path": target_path,
        },
    )
    assert dispatched.status_code == 422


def test_oversized_excavation_commit_cannot_be_approved(manager_client):
    """The trust gate independently blocks an oversized target at approval time."""
    instruction = manager_client.post(
        "/api/v1/isaac/instructions",
        json={
            "project_id": PROJECT_ID,
            "kind": "excavate_prim",
            "params": {
                "equipment_prim_path": "/World/Armature",
                "target_prim_path": "/World/construction_site_mud/Object_11/Object_9",
                "equipment_name": "EXC-001",
                "target_name": "Object_9",
                "label": "Unsafe whole-map excavation",
                "work_package_id": "WP-OVERSIZED",
            },
        },
    ).json()
    commit = _commit(
        manager_client,
        instruction,
        result={
            "operation": "excavate_prim",
            "target_active_after": False,
            "target_bounds_size": {"x": 186.5, "y": 141.5, "z": 6.5},
            "simulator": "isaac-sim",
            "source": "stage-readback",
        },
    )

    response = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "approved"},
    )
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Excavation target span is 186.5m")


def test_inactive_semantic_soil_prim_cannot_be_dispatched(manager_client, monkeypatch):
    """A previously excavated semantic target stays visible but is not executable."""
    from app.api.routes import work_packages as work_package_routes
    from app.schemas.work_package_ai import LLMExcavationPlan

    target_path = "/World/Diggable/ZoneA_SoilPile_01"
    _publish_test_stage_inventory(
        manager_client,
        target_path=target_path,
        target_name="ZoneA-SoilPile-01",
        target_active=False,
    )
    plan = LLMExcavationPlan(
        ready=True,
        operation="excavate_prim",
        equipment_ref="EXC-001",
        target_ref="ZoneA-SoilPile-01",
        zone_id="A",
        summary="Excavate the semantic soil pile",
        clarification_question="",
    )
    monkeypatch.setattr(
        work_package_routes,
        "compile_excavation_language",
        lambda _message, _inventory, _settings: plan,
    )
    response = manager_client.post(
        "/api/v1/work-packages/ai/excavation/interpret",
        json={
            "project_id": PROJECT_ID,
            "message": "선택한 토사 더미를 굴착해줘",
            "equipment_prim_path": "/World/Armature",
            "target_prim_path": target_path,
        },
    )

    assert response.status_code == 200, response.text
    active_check = next(
        check for check in response.json()["checks"] if check["code"] == "target_active"
    )
    assert active_check["ok"] is False
