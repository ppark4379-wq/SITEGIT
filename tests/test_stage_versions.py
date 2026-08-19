"""Approved Isaac Stage snapshots behave like a branch HEAD."""

from __future__ import annotations

import hashlib


def _create_cube_instruction(client, project_id: str, label: str) -> dict:
    response = client.post(
        "/api/v1/isaac/instructions",
        json={
            "project_id": project_id,
            "kind": "place_cube",
            "params": {
                "position": {"x": 1, "y": 2, "z": 3},
                "size": {"x": 2, "y": 2, "z": 2},
                "label": label,
                "color": "#6B4F2A",
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _commit_with_snapshot(
    client,
    settings,
    instruction: dict,
    branch: str = "main",
    base_commit_id: str | None = None,
    scenario_id: str | None = None,
) -> dict:
    relative = (
        f"isaac/pending/{instruction['project_id']}/{branch}/"
        f"{instruction['id']}/execution-test/stage.usda"
    )
    source = settings.sitegit_data_root / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("#usda 1.0\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    response = client.post(
        f"/api/v1/isaac/instructions/{instruction['id']}/commit",
        json={
            "status": "succeeded",
            "result": {
                "placed_position": instruction["params"]["position"],
                "placed_size": instruction["params"]["size"],
                "prim_path": "/World/SiteGit/versioned_cube",
                "stage_snapshot": {
                    "schema_version": "1.0",
                    "status": "pending",
                    "project_id": instruction["project_id"],
                    "branch": branch,
                    "base_commit_id": base_commit_id,
                    "storage_key": relative,
                    "format": "usda",
                    "sha256": digest,
                    "size_bytes": source.stat().st_size,
                    **({"scenario_id": scenario_id} if scenario_id else {}),
                },
            },
            "evidence": {},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_approved_stage_snapshot_advances_branch_head(manager_client, settings):
    project_id = "STAGE-HEAD-APPROVE"
    instruction = _create_cube_instruction(manager_client, project_id, "승인 Stage")
    commit = _commit_with_snapshot(manager_client, settings, instruction)

    reviewed = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "approved", "note": "Stage 확인"},
    )
    assert reviewed.status_code == 200, reviewed.text
    snapshot = reviewed.json()["result"]["stage_snapshot"]
    assert snapshot["status"] == "approved"
    assert snapshot["commit_id"] == commit["id"]
    assert snapshot["parent_commit_id"] is None
    assert (settings.sitegit_data_root / snapshot["storage_key"]).is_file()

    response = manager_client.get(
        "/api/v1/isaac/branches/main/head",
        params={"project_id": project_id},
    )
    assert response.status_code == 200, response.text
    head = response.json()
    assert head["commit_id"] == commit["id"]
    assert head["storage_key"] == snapshot["storage_key"]


def test_new_stage_scenario_starts_a_new_head_lineage(manager_client, settings):
    project_id = "STAGE-SCENARIO-SWITCH"
    old_instruction = _create_cube_instruction(manager_client, project_id, "old map")
    old_commit = _commit_with_snapshot(
        manager_client,
        settings,
        old_instruction,
        scenario_id="mud-map-v1",
    )
    old_review = manager_client.post(
        f"/api/v1/isaac/commits/{old_commit['id']}/review",
        json={"decision": "approved", "note": "old scenario"},
    )
    assert old_review.status_code == 200, old_review.text

    new_instruction = _create_cube_instruction(manager_client, project_id, "pipeline map")
    new_commit = _commit_with_snapshot(
        manager_client,
        settings,
        new_instruction,
        base_commit_id=None,
        scenario_id="pipeline-demolition-v1",
    )
    new_review = manager_client.post(
        f"/api/v1/isaac/commits/{new_commit['id']}/review",
        json={"decision": "approved", "note": "new scenario"},
    )
    assert new_review.status_code == 200, new_review.text
    head = new_review.json()["result"]["stage_snapshot"]
    assert head["parent_commit_id"] is None
    assert head["scenario_id"] == "pipeline-demolition-v1"
    response = manager_client.get(
        "/api/v1/isaac/branches/main/head",
        params={"project_id": project_id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["scenario_id"] == "pipeline-demolition-v1"


def test_rejected_stage_snapshot_does_not_advance_branch_head(manager_client, settings):
    project_id = "STAGE-HEAD-REJECT"
    instruction = _create_cube_instruction(manager_client, project_id, "반려 Stage")
    commit = _commit_with_snapshot(manager_client, settings, instruction)

    reviewed = manager_client.post(
        f"/api/v1/isaac/commits/{commit['id']}/review",
        json={"decision": "rejected", "note": "작업 결과 반려"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["result"]["stage_snapshot"]["status"] == "rejected"
    response = manager_client.get(
        "/api/v1/isaac/branches/main/head",
        params={"project_id": project_id},
    )
    assert response.status_code == 404


def test_stale_stage_snapshot_cannot_replace_a_newer_head(manager_client, settings):
    project_id = "STAGE-HEAD-STALE"
    first_instruction = _create_cube_instruction(manager_client, project_id, "첫 Stage")
    first_commit = _commit_with_snapshot(manager_client, settings, first_instruction)
    first_review = manager_client.post(
        f"/api/v1/isaac/commits/{first_commit['id']}/review",
        json={"decision": "approved", "note": "첫 HEAD"},
    )
    assert first_review.status_code == 200, first_review.text

    stale_instruction = _create_cube_instruction(manager_client, project_id, "오래된 Stage")
    stale_commit = _commit_with_snapshot(
        manager_client,
        settings,
        stale_instruction,
        base_commit_id=None,
    )
    stale_review = manager_client.post(
        f"/api/v1/isaac/commits/{stale_commit['id']}/review",
        json={"decision": "approved", "note": "stale"},
    )
    assert stale_review.status_code == 409

    head = manager_client.get(
        "/api/v1/isaac/branches/main/head",
        params={"project_id": project_id},
    ).json()
    assert head["commit_id"] == first_commit["id"]
